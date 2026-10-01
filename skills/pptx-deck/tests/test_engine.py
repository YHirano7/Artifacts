import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import engine  # noqa: E402


class TestEngine(unittest.TestCase):
    def test_environment_override_skips_powerpoint_probe(self):
        with mock.patch.dict(os.environ, {"PPTX_DECK_ENGINE": "powerpoint"}), \
                mock.patch.object(engine, "_powershell",
                                  side_effect=AssertionError("probed")):
            result = engine.detect()
        self.assertEqual(result["engine"], "powerpoint")
        self.assertEqual(result["reason"], "PPTX_DECK_ENGINE")
        self.assertFalse(result["powerpoint"]["ok"])

    def test_non_windows_skips_powerpoint_probe(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(engine.os, "name", "posix"), \
                mock.patch.object(engine, "_find_soffice", return_value=None), \
                mock.patch.object(engine, "_probe_powerpoint",
                                  side_effect=AssertionError("probed")):
            result = engine.detect()
        self.assertEqual(result["engine"], "none")
        self.assertIsNone(result["soffice"])

    def test_powerpoint_probe_failure_falls_back_to_libreoffice(self):
        def which(name):
            return {"powershell.exe": "powershell.exe",
                    "soffice": "soffice.exe"}.get(name)

        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(engine.os, "name", "nt"), \
                mock.patch.object(engine.shutil, "which", side_effect=which), \
                mock.patch.object(engine, "_probe_powerpoint",
                                  side_effect=RuntimeError("COM class missing")):
            result = engine.detect()
        self.assertEqual(result["engine"], "libreoffice")
        self.assertIn("COM class missing", result["reason"])
        self.assertEqual(result["soffice"], "soffice.exe")
        self.assertEqual(result["powerpoint"]["error"], "COM class missing")

    def test_no_engines_returns_none(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(engine.os, "name", "posix"), \
                mock.patch.object(engine.shutil, "which", return_value=None), \
                mock.patch.object(Path, "is_file", return_value=False):
            result = engine.detect()
        self.assertEqual(result["engine"], "none")

    def test_probe_timeout_is_recorded(self):
        proc = subprocess.TimeoutExpired("powershell.exe", 90)
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(engine.os, "name", "nt"), \
                mock.patch.object(engine.shutil, "which",
                                  side_effect=lambda name:
                                  "powershell.exe" if name == "powershell.exe"
                                  else None), \
                mock.patch.object(engine, "_probe_powerpoint",
                                  side_effect=proc):
            result = engine.detect()
        self.assertEqual(result["powerpoint"]["error"],
                         "PowerPoint probe timed out after 90 seconds")

    def test_powershell_closes_only_its_presentation_and_guards_quit(self):
        script = engine.POWERSHELL_SCRIPT
        self.assertIn("Presentations.Open($In, -1, 0, 0)", script)
        self.assertIn("$app.Presentations.Count -eq 0", script)
        self.assertIn("$app.Quit()", script)
        self.assertIn("ReleaseComObject($app)", script)
        self.assertIn('.SaveAs($Out, 32)', script)
        self.assertIn('.Export($path, "PNG", $Width, $height)', script)

    def test_explicit_engine_is_returned_without_fallback(self):
        with mock.patch.dict(os.environ, {"PPTX_DECK_ENGINE": "libreoffice"}):
            self.assertEqual(engine.resolve("libreoffice"), "libreoffice")


if __name__ == "__main__":
    unittest.main()
