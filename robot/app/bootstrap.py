from robot.agent.chat_agent import ChatAgent
from robot.agent.prompts import SYSTEM_PROMPT
from robot.core.config import Settings
from robot.drivers.audio import AudioDriver
from robot.interfaces.cli import CLI
from robot.memory.in_memory import InMemoryMemory
from robot.providers.llm.qwen import QwenProvider
from robot.providers.stt.doubao import DoubaoSTTProvider
from robot.providers.tts.doubao import DoubaoTTSProvider
from robot.services.voice_chat import VoiceChatService


# 手动组装依赖，保持单进程且不引入 DI 框架。
def build_cli(settings=None):
    settings = settings or Settings.from_env()
    settings.validate_credentials()

    audio_driver = AudioDriver(settings)
    llm_provider = QwenProvider(settings)
    stt_provider = DoubaoSTTProvider(settings, audio_driver)
    tts_provider = DoubaoTTSProvider(settings)
    memory = InMemoryMemory(max_turns=settings.chat_history_turns)
    chat_agent = ChatAgent(
        llm_provider,
        memory,
        SYSTEM_PROMPT,
    )
    voice_chat = VoiceChatService(
        stt_provider,
        chat_agent,
        tts_provider,
        audio_driver,
    )
    return CLI(voice_chat)
