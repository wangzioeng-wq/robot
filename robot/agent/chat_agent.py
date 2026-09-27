# Agent 只组合提示词、短期记忆和 LLM 接口，不感知具体供应商或硬件。
class ChatAgent:
    def __init__(self, llm_provider, memory, system_prompt):
        if not callable(getattr(llm_provider, "chat", None)):
            raise TypeError("llm_provider must provide chat(messages)")
        for method in (
            "get_messages",
            "add_user_message",
            "add_assistant_message",
        ):
            if not callable(getattr(memory, method, None)):
                raise TypeError("memory must provide {}".format(method))
        self._llm = llm_provider
        self._memory = memory
        self._system_prompt = system_prompt

    def chat(self, user_text):
        text = user_text.strip()
        if not text:
            return ""

        # 本轮消息只在模型成功回答后写入记忆，避免留下半轮对话。
        messages = [{"role": "system", "content": self._system_prompt}]
        messages.extend(self._memory.get_messages())
        messages.append({"role": "user", "content": text})
        reply = self._llm.chat(messages)
        if not isinstance(reply, str) or not reply.strip():
            return ""

        reply = reply.strip()
        self._memory.add_user_message(text)
        self._memory.add_assistant_message(reply)
        return reply
