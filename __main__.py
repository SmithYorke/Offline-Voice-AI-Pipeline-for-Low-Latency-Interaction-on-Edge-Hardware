import argparse
import subprocess
import sys

from .pipeline import check, load_config, run


def main():
    parser = argparse.ArgumentParser(description="NOVA offline voice assistant — reconstructed edition")
    sub = parser.add_subparsers(dest="action", required=True)
    doctor = sub.add_parser("check", help="Check executable and model paths (not inference)")
    doctor.add_argument("--config", default="config.local.json")
    execute = sub.add_parser("run", help="Run a complete voice interaction")
    execute.add_argument("--config", default="config.local.json")
    source = execute.add_mutually_exclusive_group(required=True)
    source.add_argument("--wav", help="16 kHz mono PCM16 WAV")
    source.add_argument("--mic", action="store_true", help="Capture using Linux ALSA")
    execute.add_argument("--play", action="store_true")
    execute.add_argument("--loop", action="store_true")
    args = parser.parse_args()
    if args.action == "run" and args.loop and not args.mic:
        parser.error("--loop requires --mic")
    try:
        config = load_config(args.config)
        missing = check(config)
        if missing:
            print("Missing prerequisites:\n" + "\n".join(f"- {x}" for x in missing), file=sys.stderr)
            return 2
        if args.action == "check":
            print("Paths found. Python modules, backend flags and real inference still need runtime validation.")
            return 0
        while True:
            folder, transcript, reply = run(config, args.wav, args.play)
            print(f"User: {transcript}\nNOVA: {reply}\nArtifacts: {folder}")
            if not args.loop:
                return 0
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        return 130
    except (OSError, ValueError, KeyError, RuntimeError, TimeoutError, subprocess.SubprocessError) as exc:
        print(f"NOVA failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
