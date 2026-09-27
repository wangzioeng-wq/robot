import asyncio
import os
import tempfile
from pathlib import Path


# 每次调用只处理一轮：实时识别、聊天、合成，再播放。
class VoiceChatService:
    def __init__(
        self,
        stt_provider,
        chat_agent,
        tts_provider,
        audio_driver,
    ):
        self._stt = stt_provider
        self._agent = chat_agent
        self._tts = tts_provider
        self._audio = audio_driver

    async def run_turn(
        self,
        on_transcript=None,
        on_user_text=None,
        on_reply=None,
    ):
        audio_source = self._audio.capture_pcm()
        user_text = await self._stt.listen(
            audio_source,
            on_partial=on_transcript,
        )
        user_text = (user_text or "").strip()
        if not user_text:
            return "", ""
        if on_user_text:
            on_user_text(user_text)

        # HTTP 请求使用 Python 3.8 的线程池接口，避免阻塞事件循环。
        loop = asyncio.get_event_loop()
        reply = await loop.run_in_executor(None, self._agent.chat, user_text)
        if not reply:
            return user_text, ""

        if on_reply:
            on_reply(user_text, reply)

        handle = tempfile.NamedTemporaryFile(
            prefix="robot_reply_",
            suffix=".pcm",
            delete=False,
        )
        output_file = Path(handle.name)
        handle.close()
        try:
            await loop.run_in_executor(
                None,
                self._tts.synthesize,
                reply,
                output_file,
            )
            await self._audio.play(output_file)
        finally:
            try:
                os.unlink(str(output_file))
            except OSError:
                pass

        return user_text, reply
