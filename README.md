# RK3566 桌面机器人

面向 RK3566 开发板的轻量级语音聊天程序，使用 Python 3.8，以单进程方式运行。语音识别、对话生成和语音合成都通过云端服务完成，音频采集与播放由板载 ALSA 设备负责。

## 当前功能

- 按回车开始一轮语音对话，输入 q 退出。
- 豆包实时语音识别（STT）将麦克风 PCM 分块上传，并显示识别过程。
- ChatAgent 使用千问（Qwen）生成回复。
- 豆包语音合成（TTS）生成 PCM，并通过 ALSA 播放。
- 短期记忆保留最近 6 轮对话，进程退出后清空。
- 默认输入设备为 plughw:0,0；输入为单声道、16 kHz、16 位 PCM，输出为单声道、24 kHz、16 位 PCM。

## 目录说明

- robot/app/：程序入口和依赖组装。
- robot/agent/：聊天流程和系统提示词。
- robot/providers/：Qwen、豆包 STT 和豆包 TTS 适配器。
- robot/services/：协调识别、对话、合成和播放。
- robot/memory/：进程内短期对话记忆。
- robot/drivers/：ALSA 音频采集与播放封装。
- robot/interfaces/：交互式命令行。
- robot/tools/、robot/skills/：预留目录，目前没有工具或技能实现。
- tests/：单元测试与集成测试说明。
- scripts/：云服务和开发板音频自检脚本。
- docs/architecture.md：模块职责和语音数据流说明。

本次重构把原 modules/ 语音程序整理到 robot/ 分层结构，统一从仓库根目录读取配置，并保留 Qwen、豆包 STT/TTS 和 ALSA 语音链路。没有加入数据库、工具执行框架或技能系统。

## 安装与配置

在开发板的仓库根目录执行：

~~~bash
python3 -m pip install -r requirements.txt
~~~

在根目录 .env 中设置云服务凭证。首次配置可参考 .env.example；已有 .env 时请直接编辑，避免覆盖现有凭证。.env 已加入 Git 忽略规则，不应提交到版本库。

可按实际设备修改 AUDIO_DEVICE、AUDIO_INPUT_RATE、AUDIO_OUTPUT_RATE 和 CHAT_HISTORY_TURNS；默认值分别为 plughw:0,0、16000、24000 和 6。

## 启动

~~~bash
cd /home/ztl/robot_v1
python3 -m robot.app.main
~~~

按提示回车开始讲话；输入 q 并回车退出。

## 自检与测试

~~~bash
python3 -m unittest discover -s tests/unit -v
python3 -m py_compile $(find robot scripts tests -name '*.py' -type f)
python3 scripts/test_audio.py
~~~

云服务可分别检查：

~~~bash
python3 scripts/test_qwen.py
python3 scripts/test_stt.py
python3 scripts/test_tts.py
~~~

音频自检会短暂采集麦克风并播放静音；STT/TTS 脚本会访问豆包服务，Qwen 脚本会访问千问服务。
