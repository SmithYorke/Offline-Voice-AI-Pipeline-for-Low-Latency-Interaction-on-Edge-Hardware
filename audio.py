"""16 kHz PCM utilities and a simple energy-based endpoint detector.

This is an RMS gate, not a trained speech/non-speech classifier.
"""
import array
from collections import deque
import math
import os
from pathlib import Path
import select
import subprocess
import sys
import time
import wave

RATE = 16000


def rms(pcm: bytes) -> float:
    if len(pcm) % 2:
        raise ValueError("PCM16 data must have an even byte count")
    samples = array.array("h", pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    return math.sqrt(sum(x * x for x in samples) / len(samples)) / 32768 if samples else 0.0


def read_wav(path):
    with wave.open(str(path), "rb") as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) != (1, 2, RATE, "NONE"):
            raise ValueError("Input must be mono, 16 kHz, uncompressed PCM16 WAV")
        expected = wav.getnframes() * 2
        pcm = wav.readframes(wav.getnframes())
    if not pcm or len(pcm) != expected:
        raise ValueError("Empty or truncated input WAV")
    return pcm, len(pcm) / (2 * RATE)


def write_wav(path, pcm):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes(pcm)


class EndpointDetector:
    """Feed complete frames; returns one utterance, or None while waiting."""

    def __init__(self, threshold=0.015, frame_ms=30, silence_ms=800,
                 preroll_ms=300, min_speech_ms=150, max_utterance_seconds=20,
                 wait_seconds=30):
        if not 0 < threshold <= 1 or frame_ms <= 0 or silence_ms <= 0:
            raise ValueError("Invalid threshold/frame/silence configuration")
        if preroll_ms < 0 or min_speech_ms <= 0 or max_utterance_seconds <= 0 or wait_seconds <= 0:
            raise ValueError("Invalid VAD timing configuration")
        if min_speech_ms > max_utterance_seconds * 1000:
            raise ValueError("Minimum speech cannot exceed maximum utterance")
        self.threshold = threshold
        self.frame_bytes = int(RATE * frame_ms / 1000) * 2
        if self.frame_bytes < 2:
            raise ValueError("Frame too short")
        self.hangover = math.ceil(silence_ms / frame_ms)
        self.minimum = math.ceil(min_speech_ms / frame_ms)
        self.maximum = math.ceil(max_utterance_seconds * 1000 / frame_ms)
        self.pre = deque(maxlen=math.ceil(preroll_ms / frame_ms))
        self.active = []
        self.voice_frames = self.quiet_frames = self.elapsed_frames = 0

    def feed(self, frame):
        if len(frame) != self.frame_bytes:
            raise ValueError("Expected one complete PCM frame")
        voiced = rms(frame) >= self.threshold
        if not self.active:
            if not voiced:
                self.pre.append(frame)
                return None
            self.active = list(self.pre)
            self.pre.clear()
        self.active.append(frame)
        self.elapsed_frames += 1
        self.voice_frames += int(voiced)
        self.quiet_frames = 0 if voiced else self.quiet_frames + 1
        if self.quiet_frames >= self.hangover or self.elapsed_frames >= self.maximum:
            result = b"".join(self.active) if self.voice_frames >= self.minimum else None
            self.active = []
            self.voice_frames = self.quiet_frames = self.elapsed_frames = 0
            return result
        return None


def record_alsa(output, device="default", **options):
    if not sys.platform.startswith("linux"):
        raise RuntimeError("Microphone capture requires Linux ALSA; use --wav on other platforms")
    detector = EndpointDetector(**options)
    deadline = time.monotonic() + options.get("wait_seconds", 30)
    capture_deadline = None
    buffer = bytearray()
    # No shell and no privileged commands. arecord stderr remains visible.
    proc = subprocess.Popen(
        ["arecord", "-q", "-D", device, "-t", "raw", "-f", "S16_LE",
         "-r", str(RATE), "-c", "1"], stdout=subprocess.PIPE)
    try:
        while True:
            now = time.monotonic()
            if capture_deadline is None and now >= deadline:
                raise TimeoutError("No valid speech captured before microphone timeout")
            if capture_deadline is not None and now >= capture_deadline:
                raise TimeoutError("Microphone stalled during utterance")
            ready, _, _ = select.select([proc.stdout], [], [], 0.1)
            if not ready:
                continue
            chunk = os.read(proc.stdout.fileno(), 4096)
            if not chunk:
                raise RuntimeError("arecord ended before a complete utterance")
            buffer.extend(chunk)
            while len(buffer) >= detector.frame_bytes:
                frame = bytes(buffer[:detector.frame_bytes])
                del buffer[:detector.frame_bytes]
                result = detector.feed(frame)
                if result is not None:
                    write_wav(output, result)
                    return
                if detector.active and capture_deadline is None:
                    capture_deadline = time.monotonic() + options.get("max_utterance_seconds", 20) + 2
                elif not detector.active:
                    capture_deadline = None
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        proc.stdout.close()
