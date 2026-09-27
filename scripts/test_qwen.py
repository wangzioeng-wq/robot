import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys

from robot.core.config import Settings
from robot.core.exceptions import ConfigurationError
from robot.providers.llm.qwen import QwenProvider


def main():
    settings = Settings.from_env()
    if not settings.dashscope_api_key:
        raise ConfigurationError("DASHSCOPE_API_KEY is not configured")
    question = " ".join(sys.argv[1:]) or "你好，你是谁？"
    provider = QwenProvider(settings)
    reply = provider.chat([{"role": "user", "content": question}])
    print("千问回答：{}".format(reply))


if __name__ == "__main__":
    main()
