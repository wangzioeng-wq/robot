import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from robot.core.exceptions import ConfigurationError


# 统一从仓库根目录读取 .env；密钥字段不会出现在 Settings 的 repr 中。
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _integer(env, name, default, minimum=1):
    raw = env.get(name, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ConfigurationError("{} must be an integer".format(name))
    if value < minimum:
        raise ConfigurationError("{} must be at least {}".format(name, minimum))
    return value


@dataclass
class Settings:
    doubao_api_key: str = field(default="", repr=False)
    doubao_asr_resource_id: str = "volc.seedasr.sauc.duration"
    doubao_tts_resource_id: str = "seed-tts-2.0"
    doubao_tts_speaker: str = "zh_female_vv_uranus_bigtts"
    dashscope_api_key: str = field(default="", repr=False)
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen3.8-flash"
    audio_device: str = "plughw:0,0"
    audio_input_rate: int = 16000
    audio_output_rate: int = 24000
    asr_chunk_ms: int = 200
    asr_end_window_ms: int = 800
    asr_no_speech_timeout_seconds: int = 8
    asr_timeout_seconds: int = 60
    chat_history_turns: int = 6

    @classmethod
    def from_env(cls, environ=None, dotenv_path=None):
        if environ is None:
            path = Path(dotenv_path) if dotenv_path else PROJECT_ROOT / ".env"
            if path.is_file():
                load_dotenv(str(path), override=False)
            env = os.environ
        else:
            env = environ

        base_url = env.get(
            "QWEN_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ).strip().rstrip("/")
        return cls(
            doubao_api_key=env.get("DOUBAO_API_KEY", "").strip(),
            doubao_asr_resource_id=env.get(
                "DOUBAO_ASR_RESOURCE_ID",
                "volc.seedasr.sauc.duration",
            ).strip(),
            doubao_tts_resource_id=env.get(
                "DOUBAO_TTS_RESOURCE_ID",
                "seed-tts-2.0",
            ).strip(),
            doubao_tts_speaker=env.get(
                "DOUBAO_TTS_SPEAKER",
                "zh_female_vv_uranus_bigtts",
            ).strip(),
            dashscope_api_key=env.get("DASHSCOPE_API_KEY", "").strip(),
            qwen_base_url=base_url,
            qwen_model=env.get("QWEN_MODEL", "qwen3.8-flash").strip(),
            audio_device=env.get("AUDIO_DEVICE", "plughw:0,0").strip(),
            audio_input_rate=_integer(env, "AUDIO_INPUT_RATE", 16000),
            audio_output_rate=_integer(env, "AUDIO_OUTPUT_RATE", 24000),
            asr_chunk_ms=_integer(env, "ASR_CHUNK_MS", 200),
            asr_end_window_ms=_integer(env, "ASR_END_WINDOW_MS", 800),
            asr_no_speech_timeout_seconds=_integer(
                env,
                "ASR_NO_SPEECH_TIMEOUT_SECONDS",
                8,
            ),
            asr_timeout_seconds=_integer(env, "ASR_TIMEOUT_SECONDS", 60),
            chat_history_turns=_integer(env, "CHAT_HISTORY_TURNS", 6, minimum=0),
        )

    def validate_credentials(self):
        missing = []
        if not self.doubao_api_key:
            missing.append("DOUBAO_API_KEY")
        if not self.dashscope_api_key:
            missing.append("DASHSCOPE_API_KEY")
        if missing:
            raise ConfigurationError(
                "Missing required environment variable(s): {}".format(
                    ", ".join(missing)
                )
            )
