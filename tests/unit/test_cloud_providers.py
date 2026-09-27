import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from robot.core.config import Settings
from robot.providers.llm.qwen import QwenProvider
from robot.providers.stt.doubao import DoubaoSTTProvider
from robot.providers.tts.doubao import DoubaoTTSProvider


class CloudProviderTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings.from_env({
            "DOUBAO_API_KEY": "doubao-key",
            "DOUBAO_ASR_RESOURCE_ID": "asr-resource",
            "DOUBAO_TTS_RESOURCE_ID": "tts-resource",
            "DOUBAO_TTS_SPEAKER": "test-speaker",
            "DASHSCOPE_API_KEY": "qwen-key",
            "QWEN_BASE_URL": "https://dashscope.example/v1",
            "QWEN_MODEL": "qwen-model",
        })

    def test_qwen_posts_messages_without_printing_credentials(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [{"message": {"content": "  你好。  "}}],
        }
        session = Mock()
        session.post.return_value = response

        provider = QwenProvider(self.settings, session=session)
        self.assertEqual(
            provider.chat([{"role": "user", "content": "你好"}]),
            "你好。",
        )
        args, kwargs = session.post.call_args
        self.assertEqual(args[0], "https://dashscope.example/v1/chat/completions")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer qwen-key")
        self.assertEqual(kwargs["json"]["model"], "qwen-model")
        self.assertFalse(kwargs["json"]["enable_thinking"])

    def test_tts_streams_pcm_to_requested_file(self):
        audio = b"small-pcm"
        line = "data: {}".format(json.dumps({
            "code": 0,
            "data": base64.b64encode(audio).decode("ascii"),
        })).encode("utf-8")
        response = Mock()
        response.iter_lines.return_value = [line]
        response.headers = {"X-Tt-Logid": "request-log"}
        session = Mock()
        session.post.return_value = response

        provider = DoubaoTTSProvider(self.settings, session=session)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "reply.pcm"
            provider.synthesize("你好", target)
            self.assertEqual(target.read_bytes(), audio)

        args, kwargs = session.post.call_args
        self.assertEqual(
            args[0],
            "https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse",
        )
        self.assertEqual(kwargs["headers"]["X-Api-Resource-Id"], "tts-resource")
        self.assertEqual(kwargs["json"]["req_params"]["speaker"], "test-speaker")
        self.assertEqual(
            kwargs["json"]["req_params"]["audio_params"]["sample_rate"],
            24000,
        )

    def test_stt_error_response_does_not_include_api_key(self):
        provider = DoubaoSTTProvider(self.settings, audio_driver=Mock())
        error = provider._service_error({"code": 1, "message": "bad request"})
        self.assertNotIn("doubao-key", str(error))


if __name__ == "__main__":
    unittest.main()
