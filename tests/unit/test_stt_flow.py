import asyncio
import struct
import unittest

from robot.core.config import Settings
from robot.providers.stt.doubao import (
    DoubaoSTTProvider,
    SERVER_FULL_RESPONSE,
)


def encode_response(body):
    import json
    import struct

    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    return bytes((0x11, SERVER_FULL_RESPONSE << 4, 0x10, 0)) + struct.pack(
        ">I", len(payload)
    ) + payload


class FakeWebSocket:
    def __init__(self):
        self.response_headers = {}
        self.incoming = asyncio.Queue()
        self.sent_audio = False
        self.sequences = []

    async def send(self, packet):
        message_type = packet[1] >> 4
        flags = packet[1] & 0x0F
        if message_type == 1:
            await self.incoming.put(encode_response({"code": 0}))
            return

        if message_type != 2:
            return
        self.sequences.append(struct.unpack(">i", packet[4:8])[0])
        if flags == 3:
            await self.incoming.put(encode_response({
                "code": 0,
                "is_last_package": True,
                "result": {"text": "你好", "definite": True},
            }))
        elif not self.sent_audio:
            self.sent_audio = True
            await self.incoming.put(encode_response({
                "code": 0,
                "result": {"text": "你好", "definite": True},
            }))

    async def recv(self):
        return await self.incoming.get()


class FakeContext:
    def __init__(self, websocket):
        self.websocket = websocket

    async def __aenter__(self):
        return self.websocket

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False


class STTStreamingFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_streams_audio_receives_partial_and_waits_for_final_package(self):
        settings = Settings.from_env({"DOUBAO_API_KEY": "test-key"})
        websocket = FakeWebSocket()

        async def audio_source():
            while True:
                await asyncio.sleep(0.01)
                yield b"\x00" * 6400

        provider = DoubaoSTTProvider(
            settings,
            audio_driver=None,
            connect_func=lambda *args, **kwargs: FakeContext(websocket),
        )
        partials = []
        result = await provider.listen(audio_source(), partials.append)

        self.assertEqual(result, "你好")
        self.assertEqual(partials, ["你好"])
        self.assertTrue(websocket.sent_audio)
        self.assertGreaterEqual(len(websocket.sequences), 2)
        self.assertEqual(websocket.sequences[0], 2)
        self.assertLess(websocket.sequences[-1], 0)


if __name__ == "__main__":
    unittest.main()
