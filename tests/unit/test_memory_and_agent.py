import unittest

from robot.agent.chat_agent import ChatAgent
from robot.memory.in_memory import InMemoryMemory


class RecordingLLM:
    def __init__(self):
        self.messages = None

    def chat(self, messages):
        self.messages = messages
        return "你好。"


class MemoryAndAgentTests(unittest.TestCase):
    def test_memory_keeps_only_the_latest_six_turns(self):
        memory = InMemoryMemory(max_turns=6)
        for index in range(8):
            memory.add_user_message("问题{}".format(index))
            memory.add_assistant_message("回答{}".format(index))

        messages = memory.get_messages()
        self.assertEqual(len(messages), 12)
        self.assertEqual(messages[0], {"role": "user", "content": "问题2"})
        self.assertEqual(messages[-1], {"role": "assistant", "content": "回答7"})

    def test_memory_returns_a_copy_and_clear_removes_history(self):
        memory = InMemoryMemory()
        memory.add_user_message("你好")
        returned = memory.get_messages()
        returned[0]["content"] = "changed"
        self.assertEqual(memory.get_messages()[0]["content"], "你好")
        memory.clear()
        self.assertEqual(memory.get_messages(), [])

    def test_chat_agent_passes_system_prompt_and_history_to_llm(self):
        memory = InMemoryMemory()
        llm = RecordingLLM()
        agent = ChatAgent(llm, memory, "system prompt")
        self.assertEqual(agent.chat("你好"), "你好。")

        self.assertEqual(
            llm.messages,
            [
                {"role": "system", "content": "system prompt"},
                {"role": "user", "content": "你好"},
            ],
        )
        self.assertEqual(
            memory.get_messages(),
            [
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "你好。"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
