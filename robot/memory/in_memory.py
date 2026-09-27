from robot.memory.base import Memory


# 只在进程内保存最近若干轮，不写磁盘或数据库。
class InMemoryMemory(Memory):
    def __init__(self, max_turns=6):
        if max_turns < 0:
            raise ValueError("max_turns must not be negative")
        self.max_turns = max_turns
        self._messages = []

    def add_user_message(self, content):
        self._messages.append({"role": "user", "content": content})
        self._trim()

    def add_assistant_message(self, content):
        self._messages.append({"role": "assistant", "content": content})
        self._trim()

    def get_messages(self):
        return [dict(message) for message in self._messages]

    def clear(self):
        self._messages = []

    # 每轮包含一条 user 和一条 assistant 消息。
    def _trim(self):
        max_messages = self.max_turns * 2
        if max_messages == 0:
            self._messages = []
        elif len(self._messages) > max_messages:
            self._messages = self._messages[-max_messages:]
