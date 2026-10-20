"""Explicit, sequential CLI adapters. No web service or model download."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import wave

from .audio import read_wav, record_alsa


def load_config(path):
    path = Path(path).resolve()
    config = json.loads(path.read_text(encoding="utf-8"))
    for key in ("asr_model", "llm_model", "tts_model", "output_dir"):
        value = Path(config[key]).expanduser()
        config[key] = str(value if value.is_absolute() else path.parent / value)
    for key in ("asr_command", "llm_command", "tts_command", "player_command"):
        command = config[key]
        if not isinstance(command, list) or not command or not all(isinstance(x, str) for x in command):
            raise ValueError(f"{key} must be a nonempty string array")
        if "/" in command[0] or "\\" in command[0]:
            exe = Path(command[0]).expanduser()
            command[0] = str(exe if exe.is_absolute() else path.parent / exe)
    for key in ("threads", "context_size", "max_tokens", "timeout_seconds"):
        if config[key] <= 0:
            raise ValueError(f"{key} must be positive")
    return config


def check(config):
    missing = []
    for key in ("asr_model", "llm_model", "tts_model"):
        if not Path(config[key]).is_file():
            missing.append(f"{key}: {config[key]}")
    if not Path(config["tts_model"] + ".json").is_file():
        missing.append(f"Piper voice config: {config['tts_model']}.json")
    for key in ("asr_command", "llm_command", "tts_command"):
        if not shutil.which(config[key][0]):
            missing.append(f"{key}: {config[key][0]}")
    return missing


def command(args, destination, error_log, timeout, stdin=None):
    """Keep backend diagnostics on disk; never parse stderr as recognized text."""
    start = time.perf_counter()
    with open(destination, "w", encoding="utf-8") as out, open(error_log, "w", encoding="utf-8") as err:
        subprocess.run(args, input=stdin, stdout=out, stderr=err,
                       text=True, encoding="utf-8", timeout=timeout, check=True)
    return time.perf_counter() - start


def tinyllama_prompt(text, system):
    return f"<|system|>\n{system}</s>\n<|user|>\n{text}</s>\n<|assistant|>\n"


def run(config, wav_path=None, play=False):
    output_root = Path(config["output_dir"])
    output_root.mkdir(parents=True, exist_ok=True)
    turn = Path(tempfile.mkdtemp(prefix="turn-", dir=output_root))
    metrics = {"status": "running", "timing_scope": "WAV ready to synthesized WAV; excludes capture and playback"}
    try:
        source = turn / "input.wav"
        if wav_path is None:
            record_alsa(source, config.get("alsa_device", "default"), **config.get("vad", {}))
        else:
            read_wav(wav_path)
            shutil.copyfile(wav_path, source)
        _, duration = read_wav(source)
        metrics["input_seconds"] = duration
        start = time.perf_counter()
        timeout = config["timeout_seconds"]
        prefix = turn / "transcript"
        metrics["asr_seconds"] = command(
            config["asr_command"] + ["-m", config["asr_model"], "-f", str(source),
            "-t", str(config["threads"]), "-l", config["language"], "-ng", "-otxt", "-of", str(prefix)],
            turn / "asr.stdout.log", turn / "asr.stderr.log", timeout)
        text = prefix.with_suffix(".txt").read_text(encoding="utf-8").strip()
        if not text:
            raise ValueError("ASR returned an empty transcript")
        metrics["asr_rtf"] = metrics["asr_seconds"] / duration
        prompt = turn / "prompt.txt"
        prompt.write_text(tinyllama_prompt(text, config["system_prompt"]), encoding="utf-8")
        reply_path = turn / "reply.txt"
        metrics["llm_seconds"] = command(
            config["llm_command"] + ["-m", config["llm_model"], "-f", str(prompt),
            "-no-cnv", "--no-display-prompt", "-n", str(config["max_tokens"]),
            "-c", str(config["context_size"]), "-t", str(config["threads"]),
            "-ngl", "0", "--temp", str(config["temperature"])],
            reply_path, turn / "llm.stderr.log", timeout)
        reply = reply_path.read_text(encoding="utf-8").strip()
        if not reply:
            raise ValueError("LLM returned an empty reply")
        # Do not strip arbitrary bracketed text or silently hide backend errors.
        speech = turn / "reply.wav"
        metrics["tts_seconds"] = command(
            config["tts_command"] + ["-m", config["tts_model"], "-f", str(speech), "--", reply],
            turn / "tts.stdout.log", turn / "tts.stderr.log", timeout)
        with wave.open(str(speech), "rb") as wav:
            if wav.getnframes() == 0:
                raise ValueError("TTS returned empty audio")
            metrics["output_audio_seconds"] = wav.getnframes() / wav.getframerate()
        metrics["pipeline_seconds"] = time.perf_counter() - start
        if play:
            subprocess.run(config["player_command"] + [str(speech)], check=True, timeout=timeout)
        metrics["status"] = "ok"
        return turn, text, reply
    except KeyboardInterrupt:
        metrics.update(status="interrupted", error="Interrupted by user")
        raise
    except Exception as exc:
        metrics.update(status="error", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        (turn / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
