import asyncio
import gzip
import json
import logging
import struct
import uuid

import websockets
from websockets.exceptions import ConnectionClosed
from websockets.legacy.client import connect as websocket_connect

from robot.core.exceptions import STTError
from robot.providers.stt.base import STTProvider


LOGGER = logging.getLogger(__name__)
ASR_URL = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async"

CLIENT_FULL_REQUEST = 0x1
CLIENT_AUDIO_REQUEST = 0x2
SERVER_FULL_RESPONSE = 0x9
SERVER_ERROR_RESPONSE = 0xF
SERIALIZATION_NONE = 0x0
SERIALIZATION_JSON = 0x1
COMPRESSION_NONE = 0x0
COMPRESSION_GZIP = 0x1


def make_header(message_type, flags=0, serialization=0, compression=0):
    return bytes((
        0x11,
        (message_type << 4) | flags,
        (serialization << 4) | compression,
        0,
    ))


def pack_payload(header, payload):
    return header + struct.pack(">I", len(payload)) + payload


def build_full_request(end_window_ms=800):
    request = {
        "audio": {
            "format": "pcm",
            "codec": "raw",
            "rate": 16000,
            "bits": 16,
            "channel": 1,
        },
        "request": {
            "model_name": "bigmodel",
            "enable_nonstream": True,
            "enable_itn": True,
            "enable_punc": True,
            "enable_ddc": True,
            "show_utterances": True,
            "result_type": "full",
            "end_window_size": end_window_ms,
        },
    }
    encoded = gzip.compress(
        json.dumps(request, ensure_ascii=False).encode("utf-8")
    )
    # 实时双向链路把初始化请求也纳入序号，后续音频帧从 2 开始。
    return (
        make_header(
            CLIENT_FULL_REQUEST,
            flags=0x1,
            serialization=SERIALIZATION_JSON,
            compression=COMPRESSION_GZIP,
        )
        + struct.pack(">i", 1)
        + struct.pack(">I", len(encoded))
        + encoded
    )


def build_audio_request(pcm_data, sequence, is_last=False):
    if sequence < 1:
        raise ValueError("sequence must be a positive packet number")
    flags = 0x3 if is_last else 0x1
    signed_sequence = -sequence if is_last else sequence
    compressed = gzip.compress(pcm_data)
    return (
        make_header(
            CLIENT_AUDIO_REQUEST,
            flags=flags,
            serialization=SERIALIZATION_NONE,
            compression=COMPRESSION_GZIP,
        )
        + struct.pack(">i", signed_sequence)
        + struct.pack(">I", len(compressed))
        + compressed
    )


def parse_server_message(data):
    if not isinstance(data, bytes) or len(data) < 4:
        raise STTError("Doubao returned an invalid WebSocket frame")

    header_size = (data[0] & 0x0F) * 4
    if header_size < 4 or len(data) < header_size:
        raise STTError("Doubao returned an invalid WebSocket header")

    message_type = data[1] >> 4
    flags = data[1] & 0x0F
    serialization = data[2] >> 4
    compression = data[2] & 0x0F
    offset = header_size
    sequence = None
    error_code = None

    if flags & 0x1:
        if len(data) < offset + 4:
            raise STTError("Doubao response is missing its sequence number")
        sequence = struct.unpack(">i", data[offset:offset + 4])[0]
        offset += 4

    if message_type == SERVER_ERROR_RESPONSE:
        if len(data) < offset + 4:
            raise STTError("Doubao returned an invalid error frame")
        error_code = struct.unpack(">I", data[offset:offset + 4])[0]
        offset += 4

    if len(data) < offset + 4:
        raise STTError("Doubao response is missing its payload size")
    payload_size = struct.unpack(">I", data[offset:offset + 4])[0]
    offset += 4
    payload = data[offset:offset + payload_size]
    if len(payload) != payload_size:
        raise STTError("Doubao response payload is incomplete")

    if compression == COMPRESSION_GZIP and payload:
        try:
            payload = gzip.decompress(payload)
        except (OSError, EOFError):
            raise STTError("Doubao response could not be decompressed")

    body = None
    if payload:
        if serialization == SERIALIZATION_JSON:
            try:
                body = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                raise STTError("Doubao returned invalid JSON")
        else:
            body = payload

    return {
        "type": message_type,
        "flags": flags,
        "sequence": sequence,
        "error_code": error_code,
        "is_last_package": bool(
            isinstance(body, dict) and body.get("is_last_package")
        ),
        "body": body,
    }


def _payload_body(body):
    if isinstance(body, dict) and isinstance(body.get("payload_msg"), dict):
        return body["payload_msg"]
    return body


def extract_text(body):
    payload = _payload_body(body)
    if not isinstance(payload, dict):
        return ""

    result = payload.get("result")
    if isinstance(result, dict):
        text = result.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
        utterances = result.get("utterances", [])
    elif isinstance(result, list):
        utterances = result
    else:
        utterances = payload.get("utterances", [])

    pieces = []
    for item in utterances:
        if isinstance(item, dict):
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                pieces.append(text.strip())
    return "".join(pieces).strip()


def has_definite_result(body):
    payload = _payload_body(body)
    if not isinstance(payload, dict):
        return False
    result = payload.get("result")
    if isinstance(result, dict) and result.get("definite") is True:
        return True
    utterances = result.get("utterances", []) if isinstance(result, dict) else []
    if isinstance(result, list):
        utterances = result
    return any(
        isinstance(item, dict) and item.get("definite") is True
        for item in utterances
    )


# 实时边采集边上传 PCM，并与识别结果接收任务并行运行。
class DoubaoSTTProvider(STTProvider):
    def __init__(self, settings, audio_driver, connect_func=None):
        self._settings = settings
        self._audio_driver = audio_driver
        self._connect = connect_func or websocket_connect

    def _service_error(self, body):
        payload = _payload_body(body)
        if not isinstance(payload, dict):
            return None
        code = payload.get("code")
        if code in (None, 0, 20000000):
            return None
        message = payload.get("message")
        if not isinstance(message, str):
            message = ""
        message = message[:160]
        if self._settings.doubao_api_key:
            message = message.replace(
                self._settings.doubao_api_key,
                "[redacted]",
            )
        detail = ": {}".format(message) if message else ""
        return STTError(
            "Doubao STT failed with code {}{}".format(code, detail)
        )

    async def listen(self, audio_source=None, on_partial=None):
        if not self._settings.doubao_api_key:
            raise STTError("DOUBAO_API_KEY is not configured")
        if audio_source is None:
            if self._audio_driver is None:
                raise STTError("Audio capture is not configured")
            audio_source = self._audio_driver.capture_pcm()

        request_id = str(uuid.uuid4())
        headers = {
            "X-Api-Key": self._settings.doubao_api_key,
            "X-Api-Resource-Id": self._settings.doubao_asr_resource_id,
            "X-Api-Request-Id": request_id,
        }
        current_text = ""
        endpoint_detected = asyncio.Event()

        try:
            async with self._connect(
                ASR_URL,
                extra_headers=headers,
                max_size=None,
                ping_interval=20,
                ping_timeout=20,
                open_timeout=15,
            ) as websocket:
                await websocket.send(
                    build_full_request(self._settings.asr_end_window_ms)
                )
                init_raw = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=min(self._settings.asr_timeout_seconds, 15),
                )
                init_message = parse_server_message(init_raw)
                if init_message["type"] == SERVER_ERROR_RESPONSE:
                    raise STTError(
                        "Doubao STT initialization failed with code {}".format(
                            init_message["error_code"]
                        )
                    )
                init_error = self._service_error(init_message["body"])
                if init_error:
                    raise init_error
                if init_message["is_last_package"]:
                    return ""
                init_text = extract_text(init_message["body"])
                if init_text:
                    current_text = init_text
                    if on_partial:
                        on_partial(init_text)
                log_id = websocket.response_headers.get("X-Tt-Logid")
                LOGGER.info(
                    "Doubao STT connected request_id=%s log_id=%s",
                    request_id,
                    log_id or "-",
                )

                # 发送端独占 WebSocket 写入，保证帧序号按顺序递增。
                async def send_audio():
                    sequence = 2
                    iterator = audio_source.__aiter__()
                    deadline = (
                        asyncio.get_running_loop().time()
                        + self._settings.asr_no_speech_timeout_seconds
                    )
                    try:
                        while not endpoint_detected.is_set():
                            if current_text:
                                chunk = await iterator.__anext__()
                            else:
                                remaining = (
                                    deadline - asyncio.get_running_loop().time()
                                )
                                if remaining <= 0:
                                    break
                                try:
                                    chunk = await asyncio.wait_for(
                                        iterator.__anext__(),
                                        timeout=remaining,
                                    )
                                except asyncio.TimeoutError:
                                    LOGGER.info(
                                        "Doubao STT ended after no-speech timeout"
                                    )
                                    break
                            if not chunk:
                                continue
                            await websocket.send(
                                build_audio_request(chunk, sequence)
                            )
                            sequence += 1

                        await websocket.send(
                            build_audio_request(
                                b"",
                                sequence,
                                is_last=True,
                            )
                        )
                    except StopAsyncIteration:
                        await websocket.send(
                            build_audio_request(
                                b"",
                                sequence,
                                is_last=True,
                            )
                        )
                    finally:
                        close = getattr(iterator, "aclose", None)
                        if close:
                            try:
                                await close()
                            except (RuntimeError, GeneratorExit):
                                pass

                # 接收端持续显示临时文本，稳定分句后通知发送端收尾。
                async def receive_results():
                    nonlocal current_text
                    while True:
                        raw = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=self._settings.asr_timeout_seconds,
                        )
                        message = parse_server_message(raw)
                        if message["type"] == SERVER_ERROR_RESPONSE:
                            error_body = _payload_body(message["body"])
                            detail = ""
                            if isinstance(error_body, dict):
                                detail = (
                                    error_body.get("message")
                                    or error_body.get("error")
                                    or ""
                                )
                            elif isinstance(error_body, bytes):
                                detail = error_body.decode(
                                    "utf-8",
                                    errors="replace",
                                )
                            if not isinstance(detail, str):
                                detail = str(detail)
                            detail = detail[:160]
                            if self._settings.doubao_api_key:
                                detail = detail.replace(
                                    self._settings.doubao_api_key,
                                    "[redacted]",
                                )
                            suffix = ": {}".format(detail) if detail else ""
                            raise STTError(
                                "Doubao STT returned error code {}{}".format(
                                    message["error_code"],
                                    suffix,
                                )
                            )

                        body = message["body"]
                        service_error = self._service_error(body)
                        if service_error:
                            raise service_error

                        text = extract_text(body)
                        if text:
                            changed = text != current_text
                            current_text = text
                            if changed and on_partial:
                                on_partial(text)

                        if has_definite_result(body):
                            endpoint_detected.set()

                        if message["is_last_package"]:
                            return

                sender = asyncio.create_task(send_audio())
                receiver = asyncio.create_task(receive_results())
                try:
                    await asyncio.wait_for(
                        asyncio.gather(sender, receiver),
                        timeout=self._settings.asr_timeout_seconds,
                    )
                finally:
                    for task in (sender, receiver):
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(sender, receiver, return_exceptions=True)
        except asyncio.CancelledError:
            raise
        except ConnectionClosed:
            LOGGER.info("Doubao STT WebSocket closed request_id=%s", request_id)
        except STTError:
            raise
        except Exception as exc:
            LOGGER.warning("Doubao STT request failed: %s", type(exc).__name__)
            raise STTError(
                "Doubao STT request failed: {}".format(type(exc).__name__)
            )

        return current_text.strip()
