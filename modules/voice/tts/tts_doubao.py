import os
import sys
import json
import uuid
import base64
from pathlib import Path

import requests
from dotenv import load_dotenv


# --------------------------------------------------
# 1. 计算 voice 模块根目录
# --------------------------------------------------

VOICE_ROOT = Path(__file__).resolve().parent.parent

ENV_FILE = VOICE_ROOT / ".env"
OUTPUT_DIR = VOICE_ROOT / "output"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# 2. 加载 .env
# --------------------------------------------------

load_dotenv(ENV_FILE)

API_KEY = os.getenv("DOUBAO_API_KEY")
RESOURCE_ID = os.getenv(
    "DOUBAO_TTS_RESOURCE_ID",
    "seed-tts-2.0"
)
SPEAKER = os.getenv(
    "DOUBAO_TTS_SPEAKER",
    "zh_female_vv_uranus_bigtts"
)


# --------------------------------------------------
# 3. 豆包 TTS 地址
# --------------------------------------------------

TTS_URL = (
    "https://openspeech.bytedance.com"
    "/api/v3/tts/unidirectional/sse"
)


# --------------------------------------------------
# 4. 文本转语音
# --------------------------------------------------

def text_to_speech(text, output_file):

    if not API_KEY:
        raise RuntimeError(
            "没有找到 DOUBAO_API_KEY，请检查 modules/voice/.env"
        )

    request_id = str(uuid.uuid4())

    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": API_KEY,
        "X-Api-Resource-Id": RESOURCE_ID,
        "X-Api-Request-Id": request_id,
    }

    payload = {
        "user": {
            "uid": "rk3566_robot"
        },
        "req_params": {
            "text": text,
            "speaker": SPEAKER,
            "audio_params": {
                "format": "pcm",
                "sample_rate": 24000,
                "speech_rate": 0,
                "loudness_rate": 0,
            },
        },
    }

    print("========== Doubao TTS ==========")
    print("文本:", text)
    print("Resource ID:", RESOURCE_ID)
    print("Speaker:", SPEAKER)
    print("Request ID:", request_id)
    print("正在请求豆包...")

    response = requests.post(
        TTS_URL,
        headers=headers,
        json=payload,
        stream=True,
        timeout=60,
    )

    print("HTTP Status:", response.status_code)
    print("Log ID:", response.headers.get("X-Tt-Logid"))

    response.raise_for_status()

    audio_data = bytearray()

    for raw_line in response.iter_lines():

        if not raw_line:
            continue

        line = raw_line.decode("utf-8")

        # SSE 数据格式：
        # data: {"code":0, ...}
        if not line.startswith("data:"):
            continue

        json_text = line[5:].strip()

        try:
            result = json.loads(json_text)
        except json.JSONDecodeError:
            continue

        code = result.get("code", 0)

        # 官方示例兼容这两个成功状态
        if code not in (0, 20000000):
            raise RuntimeError(
                "豆包 TTS 调用失败："
                f"code={code}, "
                f"message={result.get('message')}"
            )

        data = result.get("data")

        if data:
            audio_chunk = base64.b64decode(data)
            audio_data.extend(audio_chunk)

    if not audio_data:
        raise RuntimeError("请求成功，但没有收到音频数据")

    with open(output_file, "wb") as f:
        f.write(audio_data)

    print("TTS 成功")
    print("输出文件:", output_file)
    print("PCM 大小:", len(audio_data), "bytes")


# --------------------------------------------------
# 5. 程序入口
# --------------------------------------------------

if __name__ == "__main__":

    text = "你好，我是基于RK3566开发的桌面机器人。"

    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])

    output_file = OUTPUT_DIR / "tts_test.pcm"

    text_to_speech(
        text=text,
        output_file=output_file,
    )