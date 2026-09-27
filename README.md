# RK3566 Desktop Robot

Python 3.8 voice chat for the RK3566 board. The application runs in one process and connects a live Doubao speech-recognition stream to Qwen, then synthesizes the reply with Doubao TTS and plays it through ALSA.

## Setup

1. Keep the board's credentials in the root .env file. Start from .env.example and fill in DOUBAO_API_KEY and DASHSCOPE_API_KEY.
2. Install dependencies with python3 -m pip install -r requirements.txt.
3. Start the application from /home/ztl/robot_v1 with python3 -m robot.app.main.

Press Enter to speak. Say q and press Enter to exit. The default ALSA device is plughw:0,0.

## Provider checks

Run a provider check only when needed:

    python3 scripts/test_qwen.py
    python3 scripts/test_stt.py
    python3 scripts/test_tts.py
    python3 scripts/test_audio.py

The STT and audio scripts use the board microphone and speaker. Provider checks need the corresponding cloud credentials; the audio check runs locally.

See docs/architecture.md for module responsibilities and boundaries.
