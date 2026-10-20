"""Replacement for the vad_alsa.py referenced, but not supplied, in Appendix A."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nova.audio import record_alsa

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--device", default="default")
    parser.add_argument("--threshold", type=float, default=0.015)
    parser.add_argument("--silence-ms", type=int, default=800)
    args = parser.parse_args()
    record_alsa(args.out, args.device, threshold=args.threshold, silence_ms=args.silence_ms)
