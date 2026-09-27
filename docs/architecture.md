# Architecture / 架构说明

The robot runs as one Python process on Python 3.8.10. Startup begins at python3 -m robot.app.main.

## Request flow / 请求流程

    CLI（交互层）
      -> VoiceChatService（业务服务）
          -> STTProvider（语音识别适配器） -> AudioDriver（音频驱动封装）
          -> ChatAgent（聊天智能体）
              -> LLMProvider（大模型接口） -> QwenProvider（千问适配器）
              -> Memory（短期记忆） -> InMemoryMemory（内存实现）
          -> TTSProvider（语音合成接口） -> DoubaoTTSProvider（豆包适配器）
          -> AudioDriver（音频驱动封装）

## Responsibilities / 职责

- App（应用入口）: app/main.py starts the CLI; app/bootstrap.py manually builds dependencies.
- Agent（智能体）: agent/chat_agent.py combines the system prompt, conversation memory, and an LLM reply. It has no provider, network, audio, or hardware details.
- Provider（服务适配器）: providers/llm, providers/stt, and providers/tts define small interfaces and implement Qwen and Doubao API calls.
- Service（业务服务）: services/voice_chat.py coordinates live recognition, chat, synthesis, and playback.
- Memory（记忆）: memory/in_memory.py keeps the latest six user/assistant turns in RAM.
- Driver（硬件驱动封装）: drivers/audio.py captures and plays PCM through arecord and aplay.
- Interface（交互层）: interfaces/cli.py shows transcript progress, replies, and turn errors.
- Core（基础模块）: core/config.py, core/logging.py, and core/exceptions.py centralize settings, safe logs, and recoverable errors.
- Tools（工具） and Skills（技能）: reserved for later; neither is implemented or called by this application.
- State（机器人状态）: reserved for later; no state manager is implemented.

## Live audio / 实时音频

The microphone provides mono, 16-bit, 16 kHz PCM in 200 ms chunks. DoubaoSTTProvider uploads audio while receiving interim recognition results and waits for a stable sentence and the service's final response package. The ASR VAD end window defaults to 800 ms. Playback uses mono, 16-bit, 24 kHz PCM on plughw:0,0.

## Memory and error handling / 记忆与错误处理

The system prompt is applied by ChatAgent; only user and assistant messages are stored in memory. The oldest complete turns are dropped after six turns. Network, provider, and audio errors end the current turn and return control to the CLI.
