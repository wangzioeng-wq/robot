import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from robot.core.config import Settings
from robot.drivers.audio import AudioDriver


async def run():
    settings = Settings.from_env()
    audio = AudioDriver(settings)

    # 采集约一秒麦克风 PCM，确认 ALSA 输入设备可以持续读取。
    chunks = []
    captured_bytes = 0
    capture = audio.capture_pcm()
    try:
        async for chunk in capture:
            chunks.append(chunk)
            captured_bytes += len(chunk)
            if captured_bytes >= settings.audio_input_rate * 2:
                break
    finally:
        await capture.aclose()

    if not chunks:
        raise RuntimeError("麦克风没有采集到音频数据")

    # 播放短暂静音，只检查扬声器设备可用，不产生突兀声音。
    with tempfile.TemporaryDirectory(prefix="robot_audio_test_") as directory:
        silence = Path(directory) / "silence.pcm"
        silence.write_bytes(b"\x00\x00" * (settings.audio_output_rate // 4))
        await audio.play(silence)

    print("音频自检通过：麦克风采集 {} 字节，扬声器播放正常。".format(captured_bytes))


if __name__ == "__main__":
    asyncio.run(run())
