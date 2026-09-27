import asyncio
import os
import uuid
from pathlib import Path

import websockets
from dotenv import load_dotenv
from websockets.exceptions import InvalidStatusCode


VOICE_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(VOICE_ROOT / ".env")


API_KEY = os.getenv("DOUBAO_API_KEY")
RESOURCE_ID = os.getenv("DOUBAO_ASR_RESOURCE_ID")

URL = (
    "wss://openspeech.bytedance.com"
    "/api/v3/sauc/bigmodel_nostream"
)


async def main():

    request_id = str(uuid.uuid4())

    print("========== ASR 鉴权测试 ==========")
    print("API Key存在:", bool(API_KEY))
    print("API Key长度:", len(API_KEY) if API_KEY else 0)
    print("Resource ID:", repr(RESOURCE_ID))
    print("Request ID:", request_id)
    print("URL:", URL)

    headers = {
        "X-Api-Key": API_KEY,
        "X-Api-Resource-Id": RESOURCE_ID,
        "X-Api-Request-Id": request_id,
    }

    try:

        async with websockets.connect(
            URL,
            extra_headers=headers,
            open_timeout=15,
        ) as websocket:

            print()
            print("✅ WebSocket 鉴权成功")
            print("连接已经建立")

            print(
                "Log ID:",
                websocket.response_headers.get(
                    "X-Tt-Logid"
                )
            )

    except InvalidStatusCode as e:

        print()
        print("❌ WebSocket 鉴权失败")
        print("HTTP Status:", e.status_code)

        for name in [
            "X-Api-Status-Code",
            "X-Api-Message",
            "X-Tt-Logid",
        ]:

            print(
                f"{name}:",
                e.headers.get(name)
            )


if __name__ == "__main__":
    asyncio.run(main())
