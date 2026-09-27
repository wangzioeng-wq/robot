import asyncio
from pathlib import Path

from robot.core.exceptions import AudioError


# ALSA 命令集中在驱动层；采集按配置切成固定时长的 PCM 帧。
class AudioDriver:
    def __init__(self, settings):
        self._settings = settings

    async def capture_pcm(self):
        command = [
            "arecord",
            "-q",
            "-D",
            self._settings.audio_device,
            "-t",
            "raw",
            "-f",
            "S16_LE",
            "-r",
            str(self._settings.audio_input_rate),
            "-c",
            "1",
        ]
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except OSError as exc:
            raise AudioError(
                "Could not start arecord: {}".format(type(exc).__name__)
            )

        chunk_bytes = (
            self._settings.audio_input_rate
            * 2
            * self._settings.asr_chunk_ms
            // 1000
        )
        buffer = bytearray()
        try:
            while True:
                required = max(1, chunk_bytes - len(buffer))
                chunk = await process.stdout.read(required)
                if not chunk:
                    break
                buffer.extend(chunk)
                if len(buffer) >= chunk_bytes:
                    yield bytes(buffer[:chunk_bytes])
                    del buffer[:chunk_bytes]

            if buffer:
                yield bytes(buffer)

            return_code = await process.wait()
            if return_code != 0:
                raise AudioError(
                    "arecord exited with status {}".format(return_code)
                )
        except asyncio.CancelledError:
            raise
        except AudioError:
            raise
        except Exception as exc:
            raise AudioError(
                "Audio capture failed: {}".format(type(exc).__name__)
            )
        finally:
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=2)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()

    async def play(self, audio_file):
        audio_file = Path(audio_file)
        if not audio_file.is_file():
            raise AudioError("Generated PCM audio file is missing")

        command = [
            "aplay",
            "-q",
            "-D",
            self._settings.audio_device,
            "-t",
            "raw",
            "-f",
            "S16_LE",
            "-r",
            str(self._settings.audio_output_rate),
            "-c",
            "1",
            str(audio_file),
        ]
        try:
            process = await asyncio.create_subprocess_exec(*command)
            return_code = await process.wait()
        except OSError as exc:
            raise AudioError(
                "Could not start aplay: {}".format(type(exc).__name__)
            )
        if return_code != 0:
            raise AudioError(
                "aplay exited with status {}".format(return_code)
            )
