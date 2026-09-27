import gzip
import json
import struct
import unittest

from robot.providers.stt.doubao import (
    build_audio_request,
    build_full_request,
    extract_text,
    parse_server_message,
)


def server_response(body, flags=0):
    encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
    header = bytes((0x11, (0x9 << 4) | flags, 0x10, 0))
    return header + struct.pack(">I", len(encoded)) + encoded


class DoubaoProtocolTests(unittest.TestCase):
    def test_full_request_uses_streaming_pcm_and_vad_settings(self):
        packet = build_full_request(end_window_ms=800)
        self.assertEqual(packet[:4], bytes((0x11, 0x11, 0x11, 0)))
        self.assertEqual(struct.unpack(">i", packet[4:8])[0], 1)
        size = struct.unpack(">I", packet[8:12])[0]
        request = json.loads(gzip.decompress(packet[12:12 + size]).decode("utf-8"))
        self.assertEqual(request["audio"], {
            "format": "pcm",
            "codec": "raw",
            "rate": 16000,
            "bits": 16,
            "channel": 1,
        })
        self.assertEqual(request["request"]["model_name"], "bigmodel")
        self.assertEqual(request["request"]["end_window_size"], 800)
        self.assertEqual(request["request"]["result_type"], "full")

    def test_audio_packets_include_monotonic_sequence_and_negative_final_sequence(self):
        audio = b"pcm-data"
        packet = build_audio_request(audio, sequence=3)
        self.assertEqual(packet[:4], bytes((0x11, 0x21, 0x01, 0)))
        self.assertEqual(struct.unpack(">i", packet[4:8])[0], 3)
        size = struct.unpack(">I", packet[8:12])[0]
        self.assertEqual(gzip.decompress(packet[12:12 + size]), audio)

        final = build_audio_request(b"", sequence=4, is_last=True)
        self.assertEqual(final[1], 0x23)
        self.assertEqual(struct.unpack(">i", final[4:8])[0], -4)

    def test_response_parser_extracts_live_text_and_final_marker(self):
        body = {
            "code": 0,
            "is_last_package": True,
            "result": {"text": "你好，机器人"},
        }
        parsed = parse_server_message(server_response(body))
        self.assertTrue(parsed["is_last_package"])
        self.assertEqual(extract_text(parsed["body"]), "你好，机器人")

    def test_nonzero_service_code_raises_stt_error(self):
        parsed = parse_server_message(server_response({
            "code": 123,
            "message": "bad request",
        }))
        self.assertEqual(parsed["body"]["code"], 123)


if __name__ == "__main__":
    unittest.main()
