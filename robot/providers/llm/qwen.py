import logging

import requests

from robot.core.exceptions import LLMError
from robot.providers.llm.base import LLMProvider


LOGGER = logging.getLogger(__name__)


# 千问适配器只处理一次 chat completion，不负责记忆和对话流程。
class QwenProvider(LLMProvider):
    def __init__(self, settings, session=None, timeout_seconds=60):
        self._settings = settings
        self._session = session or requests
        self._timeout = timeout_seconds

    def chat(self, messages):
        if not self._settings.dashscope_api_key:
            raise LLMError("DASHSCOPE_API_KEY is not configured")

        url = self._settings.qwen_base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": "Bearer {}".format(
                self._settings.dashscope_api_key
            ),
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._settings.qwen_model,
            "messages": messages,
            "enable_thinking": False,
            "temperature": 0.7,
            "max_tokens": 256,
        }

        try:
            response = self._session.post(
                url,
                headers=headers,
                json=payload,
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            LOGGER.warning("Qwen request failed: %s", type(exc).__name__)
            raise LLMError(
                "Qwen request failed: {}".format(type(exc).__name__)
            )

        if response.status_code != 200:
            LOGGER.warning("Qwen returned HTTP %s", response.status_code)
            raise LLMError(
                "Qwen request returned HTTP {}".format(response.status_code)
            )

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise LLMError("Qwen response did not contain a chat reply")

        if not isinstance(content, str) or not content.strip():
            raise LLMError("Qwen returned an empty chat reply")
        return content.strip()
