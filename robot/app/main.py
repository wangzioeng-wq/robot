import asyncio
import sys

from robot.app.bootstrap import build_cli
from robot.core.exceptions import ConfigurationError
from robot.core.logging import configure_logging


# 应用入口只负责初始化日志、组装依赖并启动 CLI。
def main():
    configure_logging()
    try:
        cli = build_cli()
        asyncio.run(cli.run())
    except ConfigurationError as exc:
        print("配置错误：{}".format(exc))
        return 2
    except KeyboardInterrupt:
        print("\n语音机器人已退出")
    return 0


if __name__ == "__main__":
    sys.exit(main())
