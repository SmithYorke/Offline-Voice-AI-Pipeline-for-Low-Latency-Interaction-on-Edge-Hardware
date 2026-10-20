import math
from pathlib import Path
import struct
import tempfile
import unittest
import wave

from nova.audio import EndpointDetector, read_wav, rms, write_wav


def frame(amplitude=0, count=480):
    return struct.pack("<" + "h" * count, *[
        int(amplitude * math.sin(2 * math.pi * 440 * i / 16000)) for i in range(count)])


class AudioTests(unittest.TestCase):
    def test_rms_scale_and_invalid_bytes(self):
        self.assertEqual(rms(frame()), 0)
        self.assertAlmostEqual(rms(struct.pack("<hh", 16384, -16384)), 0.5)
        with self.assertRaises(ValueError):
            rms(b"x")

    def test_silence_never_triggers(self):
        gate = EndpointDetector()
        self.assertTrue(all(gate.feed(frame()) is None for _ in range(50)))

    def test_short_pause_is_kept_and_endpoint_waits(self):
        gate = EndpointDetector(silence_ms=90, min_speech_ms=60, preroll_ms=60)
        quiet, voice = frame(), frame(4000)
        for block in [quiet, quiet, voice, voice, quiet, quiet, voice, quiet, quiet]:
            self.assertIsNone(gate.feed(block))
        result = gate.feed(quiet)
        self.assertEqual(len(result), len(quiet) * 10)
        self.assertIsNone(gate.feed(quiet))  # state resets for another utterance

    def test_click_rejected(self):
        gate = EndpointDetector(silence_ms=60, min_speech_ms=90)
        for block in [frame(4000), frame(), frame()]:
            self.assertIsNone(gate.feed(block))
        self.assertFalse(gate.active)

    def test_maximum_duration(self):
        gate = EndpointDetector(preroll_ms=0, min_speech_ms=30, max_utterance_seconds=0.09)
        self.assertIsNone(gate.feed(frame(4000)))
        self.assertIsNone(gate.feed(frame(4000)))
        self.assertEqual(len(gate.feed(frame(4000))), 3 * 960)

    def test_wav_roundtrip_and_reject_wrong_rate(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "audio.wav"
            write_wav(path, frame(4000))
            pcm, duration = read_wav(path)
            self.assertEqual(pcm, frame(4000))
            self.assertAlmostEqual(duration, 0.03)
            with wave.open(str(path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(8000)
                wav.writeframes(frame())
            with self.assertRaisesRegex(ValueError, "16 kHz"):
                read_wav(path)

    def test_bad_configuration_and_partial_frame(self):
        with self.assertRaises(ValueError):
            EndpointDetector(threshold=0)
        with self.assertRaises(ValueError):
            EndpointDetector().feed(b"\0\0")


if __name__ == "__main__":
    unittest.main()
