import base64
import json
import logging
import uuid
from pathlib import Path

import requests

from robot.core.exceptions import TTSError
from robot.providers.tts.base import TTSProvider


LOGGER = logging.getLogger(__name__)
TTS_URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse"


# 沿用现有 SSE 地址、Resource ID、Speaker 和 24 kHz PCM 格式。
class DoubaoTTSProvider(TTSProvider):
    def __init__(self, settings, session=None, timeout_seconds=60):
        self._settings = settings
        self._session = session or requests
        self._timeout = timeout_seconds

    def synthesize(self, text, output_file):
        if not self._settings.doubao_api_key:
            raise TTSError("DOUBAO_API_KEY is not configured")
        if not text or not text.strip():
            raise TTSError("TTS text is empty")

        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        request_id = str(uuid.uuid4())
        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": self._settings.doubao_api_key,
            "X-Api-Resource-Id": self._settings.doubao_tts_resource_id,
            "X-Api-Request-Id": request_id,
        }
        payload = {
            "user": {"uid": "rk3566_robot"},
            "req_params": {
                "text": text,
                "speaker": self._settings.doubao_tts_speaker,
                "audio_params": {
                    "format": "pcm",
                    "sample_rate": self._settings.audio_output_rate,
                    "speech_rate": 0,
                    "loudness_rate": 0,
                },
            },
        }

        try:
            response = self._session.post(
                TTS_URL,
                headers=headers,
                json=payload,
                stream=True,
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            LOGGER.warning("Doubao TTS request failed: %s", type(exc).__name__)
            raise TTSError(
                "Doubao TTS request failed: {}".format(type(exc).__name__)
            )

        total_bytes = 0
        try:
            response.raise_for_status()
            with output_file.open("wb") as audio_file:
                for raw_line in response.iter_lines():
                    if not raw_line:
                        continue
                    if isinstance(raw_line, bytes):
                        line = raw_line.decode("utf-8", errors="replace")
                    else:
                        line = str(raw_line)
                    if not line.startswith("data:"):
                        continue
                    try:
                        result = json.loads(line[5:].strip())
                    except ValueError:
                        continue

                    code = result.get("code", 0)
                    if code not in (0, 20000000):
                        raise TTSError(
                            "Doubao TTS failed with code {}".format(code)
                        )

                    data = result.get("data")
                    if data:
                        try:
                            audio_chunk = base64.b64decode(data)
                        except (ValueError, TypeError):
                            raise TTSError("Doubao TTS returned invalid audio data")
                        audio_file.write(audio_chunk)
                        total_bytes += len(audio_chunk)
        except requests.RequestException as exc:
            LOGGER.warning("Doubao TTS HTTP request failed: %s", type(exc).__name__)
            raise TTSError(
                "Doubao TTS HTTP request failed: {}".format(type(exc).__name__)
            )
        finally:
            close = getattr(response, "close", None)
            if close:
                close()

        if total_bytes == 0:
            raise TTSError("Doubao TTS returned no audio data")

        log_id = response.headers.get("X-Tt-Logid")
        LOGGER.info(
            "Doubao TTS completed request_id=%s log_id=%s bytes=%s",
            request_id,
            log_id or "-",
            total_bytes,
        )
        return output_file
