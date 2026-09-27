import asyncio
import gzip
import json
import os
import struct
import sys
import uuid
import wave
from pathlib import Path

import websockets
from dotenv import load_dotenv


# ============================================================
# 1. 工程路径
# ============================================================

VOICE_ROOT = Path(__file__).resolve().parent.parent

ENV_FILE = VOICE_ROOT / ".env"
SAMPLES_DIR = VOICE_ROOT / "samples"

load_dotenv(ENV_FILE)


# ============================================================
# 2. 豆包配置
# ============================================================

API_KEY = os.getenv("DOUBAO_API_KEY")

RESOURCE_ID = os.getenv(
    "DOUBAO_ASR_RESOURCE_ID",
    "volc.seedasr.sauc.duration",
)

ASR_URL = (
    "wss://openspeech.bytedance.com"
    "/api/v3/sauc/bigmodel_nostream"
)


# 每个音频包 200ms
SEGMENT_MS = 200


# ============================================================
# 3. 豆包 WebSocket 二进制协议常量
# ============================================================

# 客户端发送完整请求
CLIENT_FULL_REQUEST = 0x1

# 客户端发送音频数据
CLIENT_AUDIO_REQUEST = 0x2

# 服务端返回识别结果
SERVER_FULL_RESPONSE = 0x9

# 服务端 ACK
SERVER_ACK = 0xB

# 服务端错误
SERVER_ERROR_RESPONSE = 0xF


# 消息标志
NO_SEQUENCE = 0x0

# 最后一个包，没有 sequence
LAST_NO_SEQUENCE = 0x2


# 序列化方式
SERIALIZATION_NONE = 0x0
SERIALIZATION_JSON = 0x1


# 压缩方式
COMPRESSION_NONE = 0x0
COMPRESSION_GZIP = 0x1


# ============================================================
# 4. 创建协议头
# ============================================================

def make_header(
    message_type,
    flags=NO_SEQUENCE,
    serialization=SERIALIZATION_NONE,
    compression=COMPRESSION_NONE,
):
    """
    豆包二进制协议头一共 4 字节。

    byte 0:
        高4位 = protocol version
        低4位 = header size

    byte 1:
        高4位 = message type
        低4位 = flags

    byte 2:
        高4位 = serialization
        低4位 = compression

    byte 3:
        reserved
    """

    protocol_version = 0x1
    header_size = 0x1

    byte0 = (protocol_version << 4) | header_size
    byte1 = (message_type << 4) | flags
    byte2 = (serialization << 4) | compression
    byte3 = 0x00

    return bytes(
        [
            byte0,
            byte1,
            byte2,
            byte3,
        ]
    )


# ============================================================
# 5. 给 payload 加长度
# ============================================================

def pack_payload(header, payload):
    """
    数据格式：

        header
          +
        4字节 payload长度
          +
        payload
    """

    payload_size = struct.pack(
        ">I",
        len(payload),
    )

    return header + payload_size + payload


# ============================================================
# 6. 创建第一次请求
# ============================================================

def build_full_request():
    """
    第一次发送给服务器的不是音频，
    而是告诉服务器：

    - 音频是什么格式
    - 使用什么模型
    - 是否开启标点等功能
    """

    request_json = {
        "audio": {
            "format": "pcm",
            "codec": "raw",
            "rate": 16000,
            "bits": 16,
            "channel": 1,
        },
        "request": {
            "model_name": "bigmodel",
            "enable_itn": True,
            "enable_punc": True,
            "enable_ddc": True,
            "show_utterances": True,
        },
    }

    json_data = json.dumps(
        request_json,
        ensure_ascii=False,
    ).encode("utf-8")

    compressed = gzip.compress(json_data)

    header = make_header(
        message_type=CLIENT_FULL_REQUEST,
        serialization=SERIALIZATION_JSON,
        compression=COMPRESSION_GZIP,
    )

    return pack_payload(
        header,
        compressed,
    )


# ============================================================
# 7. 创建音频包
# ============================================================

def build_audio_request(pcm_data, is_last):
    """
    把 PCM 音频压缩后封装成豆包协议的数据包。
    """

    compressed = gzip.compress(pcm_data)

    flags = (
        LAST_NO_SEQUENCE
        if is_last
        else NO_SEQUENCE
    )

    header = make_header(
        message_type=CLIENT_AUDIO_REQUEST,
        flags=flags,
        serialization=SERIALIZATION_NONE,
        compression=COMPRESSION_GZIP,
    )

    return pack_payload(
        header,
        compressed,
    )


# ============================================================
# 8. 解析服务器返回的数据
# ============================================================

def parse_server_message(data):
    """
    解析豆包服务器二进制响应。
    """

    if not isinstance(data, bytes):
        return {
            "type": None,
            "body": None,
            "raw": data,
        }

    if len(data) < 4:
        raise RuntimeError(
            "收到异常 WebSocket 数据包"
        )

    header_size = (
        data[0] & 0x0F
    ) * 4

    message_type = (
        data[1] >> 4
    )

    flags = (
        data[1] & 0x0F
    )

    serialization = (
        data[2] >> 4
    )

    compression = (
        data[2] & 0x0F
    )

    payload = data[header_size:]

    sequence = None

    # flags最低位为1表示带sequence
    if flags & 0x01:
        if len(payload) < 4:
            raise RuntimeError(
                "响应中缺少 sequence"
            )

        sequence = struct.unpack(
            ">i",
            payload[:4],
        )[0]

        payload = payload[4:]

    error_code = None

    # 错误响应前面带 error code
    if message_type == SERVER_ERROR_RESPONSE:

        if len(payload) < 8:
            raise RuntimeError(
                "服务器错误响应格式异常"
            )

        error_code = struct.unpack(
            ">I",
            payload[:4],
        )[0]

        payload = payload[4:]

    # 后面通常是：
    # 4字节payload长度 + payload
    if len(payload) >= 4:

        payload_size = struct.unpack(
            ">I",
            payload[:4],
        )[0]

        payload = payload[
            4:4 + payload_size
        ]

    # 根据协议解压
    if (
        compression == COMPRESSION_GZIP
        and payload
    ):
        payload = gzip.decompress(payload)

    body = None

    if payload:

        if serialization == SERIALIZATION_JSON:

            body = json.loads(
                payload.decode("utf-8")
            )

        else:

            body = payload

    is_last = (
        flags in (0x2, 0x3)
        or (
            sequence is not None
            and sequence < 0
        )
    )

    return {
        "type": message_type,
        "flags": flags,
        "sequence": sequence,
        "error_code": error_code,
        "is_last": is_last,
        "body": body,
    }


# ============================================================
# 9. 从服务器响应中提取文字
# ============================================================

def extract_text(body):

    if not isinstance(body, dict):
        return ""

    result = body.get("result")

    if not isinstance(result, dict):
        return ""

    text = result.get("text")

    if text:
        return text

    utterances = result.get(
        "utterances",
        []
    )

    texts = []

    for item in utterances:

        if isinstance(item, dict):

            value = item.get("text")

            if value:
                texts.append(value)

    return "".join(texts)


# ============================================================
# 10. 检查 WAV 文件
# ============================================================

def check_wav(wav_file):

    with wave.open(
        str(wav_file),
        "rb",
    ) as wav:

        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        frames = wav.getnframes()

    print("========== WAV 信息 ==========")
    print("文件:", wav_file)
    print("采样率:", sample_rate, "Hz")
    print("位深:", sample_width * 8, "bit")
    print("声道:", channels)
    print("采样点:", frames)

    if sample_rate != 16000:
        raise RuntimeError(
            "STT测试要求采样率为16000Hz"
        )

    if sample_width != 2:
        raise RuntimeError(
            "STT测试要求16bit音频"
        )

    if channels != 1:
        raise RuntimeError(
            "STT测试要求单声道音频"
        )


# ============================================================
# 11. STT 主逻辑
# ============================================================

async def speech_to_text(wav_file):

    if not API_KEY:
        raise RuntimeError(
            "没有找到 DOUBAO_API_KEY"
        )

    if not wav_file.exists():
        raise RuntimeError(
            f"找不到录音文件: {wav_file}"
        )

    check_wav(wav_file)

    request_id = str(
        uuid.uuid4()
    )

    headers = {
        "X-Api-Key": API_KEY,
        "X-Api-Resource-Id": RESOURCE_ID,
        "X-Api-Request-Id": request_id,
    }

    print()
    print("========== Doubao STT ==========")
    print("Resource ID:", RESOURCE_ID)
    print("Request ID:", request_id)
    print("正在连接豆包 ASR...")

    async with websockets.connect(
        ASR_URL,
        extra_headers=headers,
        max_size=None,
        ping_interval=20,
        ping_timeout=20,
    ) as websocket:

        print("WebSocket连接成功")

        try:
            log_id = websocket.response_headers.get(
                "X-Tt-Logid"
            )

            print("Log ID:", log_id)

        except Exception:
            pass

        # ------------------------------------------
        # 第一个包：请求参数
        # ------------------------------------------

        await websocket.send(
            build_full_request()
        )

        print("已发送识别参数")

        # ------------------------------------------
        # 打开 WAV
        # ------------------------------------------

        with wave.open(
            str(wav_file),
            "rb",
        ) as wav:

            sample_rate = wav.getframerate()

            frames_per_packet = int(
                sample_rate
                * SEGMENT_MS
                / 1000
            )

            current_chunk = wav.readframes(
                frames_per_packet
            )

            packet_count = 0

            while current_chunk:

                next_chunk = wav.readframes(
                    frames_per_packet
                )

                is_last = (
                    len(next_chunk) == 0
                )

                packet = build_audio_request(
                    current_chunk,
                    is_last,
                )

                await websocket.send(
                    packet
                )

                packet_count += 1

                print(
                    f"\r发送音频包: {packet_count}",
                    end="",
                    flush=True,
                )

                current_chunk = next_chunk

                # 模拟实时麦克风流
                if not is_last:
                    await asyncio.sleep(
                        SEGMENT_MS / 1000
                    )

        print()
        print("音频发送完成")
        print("等待识别结果...")

        # ------------------------------------------
        # 接收响应
        # ------------------------------------------

        while True:

            raw_response = await asyncio.wait_for(
                websocket.recv(),
                timeout=30,
            )

            response = parse_server_message(
                raw_response
            )

            message_type = response[
                "type"
            ]

            # 服务端错误
            if (
                message_type
                == SERVER_ERROR_RESPONSE
            ):

                raise RuntimeError(
                    "豆包ASR错误："
                    f"code="
                    f"{response['error_code']}, "
                    f"body="
                    f"{response['body']}"
                )

            body = response.get("body")

            text = extract_text(body)

            if text:

                print()
                print(
                    "========== 识别结果 =========="
                )

                print(text)

                return text


# ============================================================
# 12. 程序入口
# ============================================================

async def main():

    if len(sys.argv) > 1:

        wav_file = Path(
            sys.argv[1]
        )

    else:

        wav_file = (
            SAMPLES_DIR
            / "mic_test.wav"
        )

    await speech_to_text(
        wav_file
    )


if __name__ == "__main__":

    asyncio.run(
        main()
    )