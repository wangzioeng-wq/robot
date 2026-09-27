import unittest

from robot.core.config import Settings


class SettingsTests(unittest.TestCase):
    def test_reads_values_and_defaults_from_environment(self):
        settings = Settings.from_env({
            "DOUBAO_API_KEY": "secret",
            "DOUBAO_ASR_RESOURCE_ID": "asr-resource",
            "DOUBAO_TTS_RESOURCE_ID": "tts-resource",
            "DOUBAO_TTS_SPEAKER": "speaker",
            "DASHSCOPE_API_KEY": "qwen-secret",
            "QWEN_BASE_URL": "https://example.test/v1/",
            "QWEN_MODEL": "qwen-model",
        })

        self.assertEqual(settings.doubao_api_key, "secret")
        self.assertEqual(settings.doubao_asr_resource_id, "asr-resource")
        self.assertEqual(settings.doubao_tts_resource_id, "tts-resource")
        self.assertEqual(settings.doubao_tts_speaker, "speaker")
        self.assertEqual(settings.dashscope_api_key, "qwen-secret")
        self.assertEqual(settings.qwen_base_url, "https://example.test/v1")
        self.assertEqual(settings.qwen_model, "qwen-model")
        self.assertEqual(settings.audio_device, "plughw:0,0")
        self.assertEqual(settings.audio_input_rate, 16000)
        self.assertEqual(settings.audio_output_rate, 24000)
        self.assertEqual(settings.asr_chunk_ms, 200)
        self.assertEqual(settings.asr_end_window_ms, 800)
        self.assertEqual(settings.chat_history_turns, 6)

    def test_secret_values_do_not_appear_in_repr(self):
        settings = Settings.from_env({
            "DOUBAO_API_KEY": "secret-one",
            "DASHSCOPE_API_KEY": "secret-two",
        })
        self.assertNotIn("secret-one", repr(settings))
        self.assertNotIn("secret-two", repr(settings))


if __name__ == "__main__":
    unittest.main()
