import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import sys
import tempfile
from pathlib import Path

from robot.core.config import Settings
from robot.drivers.audio import AudioDriver
from robot.providers.tts.doubao import DoubaoTTSProvider


def main():
    settings = Settings.from_env()
    provider = DoubaoTTSProvider(settings)
    audio = AudioDriver(settings)
    text = " ".join(sys.argv[1:]) or "你好，我是桌面机器人。"
    with tempfile.TemporaryDirectory(prefix="robot_tts_test_") as directory:
        output_file = Path(directory) / "tts_test.pcm"
        provider.synthesize(text, output_file)
        print("TTS 成功，正在通过 {} 播放。".format(settings.audio_device))
        asyncio.run(audio.play(output_file))


if __name__ == "__main__":
    main()
