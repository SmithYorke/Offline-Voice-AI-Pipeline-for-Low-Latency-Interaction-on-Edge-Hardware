"""Recovered HTTP client design from Appendix A, with timeout and cleanup.

Requires independently supplied servers; this repository does NOT include them.
This client cannot by itself reproduce the report's memory comparison.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile
import time


def main():
    import requests  # optional: python -m pip install requests
    parser = argparse.ArgumentParser()
    parser.add_argument("--asr-url", default="http://localhost:5001/transcribe")
    parser.add_argument("--llm-url", default="http://localhost:5002/generate")
    parser.add_argument("--device", default="default")
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="nova-baseline-") as folder:
        wav = Path(folder) / "input.wav"
        while True:
            subprocess.run(["arecord", "-D", args.device, "-d", "3", "-c", "1",
                            "-f", "S16_LE", "-r", "16000", str(wav)], check=True, timeout=10)
            with wav.open("rb") as stream:
                response = requests.post(args.asr_url, files={"audio": stream}, timeout=180)
            response.raise_for_status()
            text = response.json().get("text", "").strip()
            if text:
                response = requests.post(args.llm_url, json={"prompt": text, "max_tokens": 50}, timeout=180)
                response.raise_for_status()
                print(response.json().get("response", ""))
            if not args.loop:
                break
            time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
