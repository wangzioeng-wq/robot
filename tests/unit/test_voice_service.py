import asyncio
import unittest
from unittest.mock import Mock

from robot.services.voice_chat import VoiceChatService


class FakeSTT:
    async def listen(self, audio_source, on_partial=None):
        if on_partial:
            on_partial("你好")
        return "你好"


class FakeAudio:
    async def capture_pcm(self):
        if False:
            yield b""

    async def play(self, path):
        self.played_path = path


class VoiceServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_turn_runs_stt_agent_tts_and_playback(self):
        agent = Mock()
        agent.chat.return_value = "你好，我是桌面机器人。"
        tts = Mock()
        audio = FakeAudio()
        service = VoiceChatService(FakeSTT(), agent, tts, audio)

        partials = []
        user_text, reply = await service.run_turn(partials.append)

        self.assertEqual((user_text, reply), ("你好", "你好，我是桌面机器人。"))
        self.assertEqual(partials, ["你好"])
        agent.chat.assert_called_once_with("你好")
        tts.synthesize.assert_called_once()
        self.assertIsNotNone(audio.played_path)
        self.assertFalse(audio.played_path.exists())


if __name__ == "__main__":
    unittest.main()
