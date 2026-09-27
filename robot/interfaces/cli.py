import asyncio
import logging
import sys

from robot.core.exceptions import RobotError


LOGGER = logging.getLogger(__name__)


# CLI 负责提示用户和展示结果；错误限制在当前轮并继续等待。
class CLI:
    def __init__(self, voice_chat_service):
        self._voice_chat = voice_chat_service

    async def run(self):
        print("================================")
        print("       RK3566 AI Robot")
        print("================================")

        loop = asyncio.get_event_loop()
        while True:
            try:
                command = await loop.run_in_executor(
                    None,
                    input,
                    "\n按 Enter 开始讲话，输入 q 退出：",
                )
            except EOFError:
                print("\n输入结束，退出语音聊天。")
                return

            if command.strip().lower() == "q":
                print("退出语音聊天")
                return

            print("正在监听...")
            sys.stdout.flush()

            def show_transcript(text):
                sys.stdout.write("\r识别中：{}".format(text))
                sys.stdout.flush()

            def show_user_text(text):
                print("\n检测到说话结束")
                print("你：{}".format(text))
                sys.stdout.flush()

            def show_reply(user_text, reply):
                print("AI：{}".format(reply))
                sys.stdout.flush()

            try:
                user_text, reply = await self._voice_chat.run_turn(
                    on_transcript=show_transcript,
                    on_user_text=show_user_text,
                    on_reply=show_reply,
                )
                if not user_text:
                    print("\n没有识别到有效语音，请重新说一次。")
                elif not reply:
                    print("\nAI 没有返回有效回答。")
            except RobotError as exc:
                print("\n本轮失败：{}".format(exc))
                LOGGER.warning("Voice turn failed: %s", type(exc).__name__)
            except Exception as exc:
                print("\n本轮发生错误：{}".format(type(exc).__name__))
                LOGGER.error("Unexpected voice turn error: %s", type(exc).__name__)
