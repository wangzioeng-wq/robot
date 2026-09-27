# 架构说明

程序运行在 RK3566 开发板的 Python 3.8 环境中，以单进程方式启动：

~~~bash
python3 -m robot.app.main
~~~

## 语音处理流程

~~~text
命令行交互
  -> VoiceChatService
      -> DoubaoSTTProvider -> AudioDriver（麦克风采集）
      -> ChatAgent -> QwenProvider
                   -> InMemoryMemory（短期对话记忆）
      -> DoubaoTTSProvider
      -> AudioDriver（扬声器播放）
~~~

## 模块职责

- robot/app/：初始化日志、创建依赖并启动命令行。
- robot/agent/：组合系统提示词、对话记忆和大模型接口，不处理网络或硬件细节。
- robot/providers/：定义服务接口，并封装 Qwen、豆包语音识别和豆包语音合成请求。
- robot/services/：按一轮对话的顺序协调识别、回复生成、语音合成和播放。
- robot/memory/：只在当前进程内保存最近若干轮用户和助手消息。
- robot/drivers/：通过 arecord 和 aplay 采集、播放 PCM 音频。
- robot/interfaces/：提供交互式命令行，显示识别文本、回复和本轮错误。
- robot/core/：集中处理配置、日志和可恢复异常。
- robot/tools/、robot/skills/：仅保留空包和说明文件，尚无工具或技能实现。

## 音频和记忆

麦克风输入为单声道、16 位、16 kHz PCM，按 200 毫秒分块实时上传；识别端并行接收临时文本，并在检测到分句后收尾。VAD 结束窗口默认 800 毫秒。扬声器播放豆包返回的单声道、16 位、24 kHz PCM，默认设备为 plughw:0,0。

记忆默认保存最近 6 轮对话，仅包含用户和助手消息。系统提示词在每次模型请求时单独传入，不写入对话记忆。旧轮次按完整问答对清理。

网络服务或音频设备出错时，当前轮会报告错误并返回命令行，用户可以重新发起下一轮。
