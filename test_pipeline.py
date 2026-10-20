import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from nova.audio import write_wav
from nova.pipeline import check, load_config, run

ROOT = Path(__file__).resolve().parents[1]
FAKE = str(Path(__file__).with_name("fake_backend.py"))


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="nova test space ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        config = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
        for key in ("asr", "llm", "tts"):
            config[key + "_command"] = [sys.executable, FAKE, key]
            config[key + "_model"] = key + ".model"
            (self.root / (key + ".model")).touch()
        (self.root / "tts.model.json").write_text("{}", encoding="utf-8")
        self.path = self.root / "config.json"
        self.path.write_text(json.dumps(config), encoding="utf-8")
        self.config = load_config(self.path)
        self.wav = self.root / "speech input.wav"
        write_wav(self.wav, b"\0\0" * 1600)  # synthetic fixture, no real speech

    def metrics(self):
        return json.loads(next((self.root / "runs").glob("*/metrics.json")).read_text(encoding="utf-8"))

    def test_config_resolves_relative_to_file(self):
        self.assertEqual(Path(self.config["asr_model"]), self.root / "asr.model")
        self.assertEqual(check(self.config), [])

    def test_full_external_command_contract(self):
        turn, text, reply = run(self.config, self.wav)
        self.assertIn("$HOME & test", text)  # preserved as data, not shell-expanded
        self.assertEqual(reply, "This is a test-only response.")
        self.assertTrue((turn / "reply.wav").is_file())
        metrics = self.metrics()
        self.assertEqual(metrics["status"], "ok")
        self.assertAlmostEqual(metrics["input_seconds"], 0.1)
        self.assertAlmostEqual(metrics["output_audio_seconds"], 0.1)
        self.assertGreater(metrics["pipeline_seconds"], 0)
        self.assertAlmostEqual(metrics["asr_rtf"], metrics["asr_seconds"] / 0.1)

    def test_backend_failure_stops_and_logs(self):
        self.config["asr_command"][-1] = "fail"
        with self.assertRaises(subprocess.CalledProcessError):
            run(self.config, self.wav)
        self.assertEqual(self.metrics()["status"], "error")
        self.assertFalse(list((self.root / "runs").glob("*/reply.wav")))
        log = next((self.root / "runs").glob("*/asr.stderr.log"))
        self.assertIn("intentional backend failure", log.read_text())

    def test_empty_asr_does_not_invoke_llm(self):
        self.config["asr_command"][-1] = "empty_asr"
        with self.assertRaisesRegex(ValueError, "empty transcript"):
            run(self.config, self.wav)
        self.assertFalse(list((self.root / "runs").glob("*/prompt.txt")))

    def test_timeout_is_recorded(self):
        self.config["asr_command"][-1] = "slow"
        self.config["timeout_seconds"] = 0.15
        with self.assertRaises(subprocess.TimeoutExpired):
            run(self.config, self.wav)
        self.assertIn("TimeoutExpired", self.metrics()["error"])

    def test_turns_do_not_overwrite(self):
        first, _, _ = run(self.config, self.wav)
        second, _, _ = run(self.config, self.wav)
        self.assertNotEqual(first, second)
        self.assertTrue((first / "reply.wav").exists())


if __name__ == "__main__":
    unittest.main()
