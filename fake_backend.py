"""TEST ONLY: stand-in executables, not speech recognition or generation."""
from pathlib import Path
import sys
import time
import wave

mode = sys.argv[1]
args = sys.argv[2:]


def value(flag):
    return args[args.index(flag) + 1]


if mode == "asr":
    assert "-otxt" in args and Path(value("-f")).is_file()
    Path(value("-of") + ".txt").write_text('Hello "NOVA"; $HOME & test', encoding="utf-8")
elif mode == "empty_asr":
    Path(value("-of") + ".txt").write_text("", encoding="utf-8")
elif mode == "llm":
    assert "-no-cnv" in args and "--no-display-prompt" in args
    prompt = Path(value("-f")).read_text(encoding="utf-8")
    assert "<|assistant|>" in prompt and '$HOME & test' in prompt
    print("This is a test-only response.")
elif mode == "tts":
    assert args[args.index("--") + 1] == "This is a test-only response."
    with wave.open(value("-f"), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(22050)
        output.writeframes(b"\0\0" * 2205)
elif mode == "fail":
    print("intentional backend failure", file=sys.stderr)
    sys.exit(7)
elif mode == "slow":
    time.sleep(10)
else:
    raise ValueError(mode)
