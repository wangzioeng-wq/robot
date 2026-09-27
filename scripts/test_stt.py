import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio

from robot.core.config import Settings
from robot.drivers.audio import AudioDriver
from robot.providers.stt.doubao import DoubaoSTTProvider


async def run():
    settings = Settings.from_env()
    provider = DoubaoSTTProvider(settings, AudioDriver(settings))
    print("正在监听，请说一句话；按 Ctrl+C 取消。")

    def show_partial(text):
        print("\r识别中：{}".format(text), end="", flush=True)

    result = await provider.listen(on_partial=show_partial)
    print("\n识别结果：{}".format(result or "（没有识别到语音）"))


if __name__ == "__main__":
    asyncio.run(run())
