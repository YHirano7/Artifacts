import json
import os
import subprocess
import sys
import tempfile
import unittest


SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_DIR = os.path.join(SKILL_DIR, "scripts")
SCRIPT_PATH = os.path.join(SCRIPT_DIR, "yomiyasu_lint.py")
sys.path.insert(0, SCRIPT_DIR)

import yomiyasu_lint


class YomiyasuLintTests(unittest.TestCase):
    def run_cli(self, *args, input_bytes=None):
        env = os.environ.copy()
        env.pop("PYTHONIOENCODING", None)
        env.pop("PYTHONUTF8", None)
        return subprocess.run(
            [sys.executable, SCRIPT_PATH, *args],
            input=input_bytes,
            capture_output=True,
            env=env,
        )

    def test_clean_japanese_paragraph(self):
        text = (
            "昨日、私は図書館で新しい本を借りました。"
            "帰りに川沿いを歩き、風の冷たさに気づきました。"
            "夕食には野菜を使った温かいスープを作る予定です。"
        )
        result = yomiyasu_lint.lint_text(text)
        self.assertTrue(result["is_clean"])
        self.assertEqual(result["score"], 100)

    def test_slop_findings(self):
        text = (
            "ここで重要なのは解像度です。\n"
            "片方だけを見ると静かに壊れます。\n"
            "今日はうまく進みました 😀"
        )
        rules = {finding["rule"] for finding in yomiyasu_lint.lint_text(text)["findings"]}
        self.assertTrue(
            {"slop_vocabulary", "metaphor_verb", "meta_filler", "emoji_prohibited"}
            <= rules
        )

    def test_crlf_has_same_findings_as_lf(self):
        text = "確認を始めます。\n結果を記録します:\n"
        lf_result = yomiyasu_lint.lint_text(text)
        crlf_result = yomiyasu_lint.lint_text(text.replace("\n", "\r\n"))
        self.assertEqual(lf_result, crlf_result)
        self.assertIn("trailing_colon", {item["rule"] for item in lf_result["findings"]})

    def test_frontmatter_and_code_block_are_not_scanned(self):
        text = (
            "---\n"
            "title: 重要なのは解像度\n"
            "---\n\n"
            "本文は落ち着いた文章です。\n\n"
            "```text\n"
            "ここで重要なのは解像度です。\n"
            "```\n"
        )
        rules = {finding["rule"] for finding in yomiyasu_lint.lint_text(text)["findings"]}
        self.assertNotIn("slop_vocabulary", rules)
        self.assertNotIn("meta_filler", rules)

    def test_cli_json_strict_stdin_bom_and_missing_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            clean_path = os.path.join(temp_dir, "clean.md")
            slop_path = os.path.join(temp_dir, "slop.md")
            bom_path = os.path.join(temp_dir, "bom.md")
            with open(clean_path, "w", encoding="utf-8") as output:
                output.write("今日は図書館へ行きました。")
            with open(slop_path, "w", encoding="utf-8") as output:
                output.write("ここで重要なのは解像度です。")
            with open(bom_path, "wb") as output:
                output.write("\ufeff今日は図書館へ行きました。".encode("utf-8"))

            json_run = self.run_cli("--json", clean_path)
            self.assertEqual(json_run.returncode, 0)
            json_result = json.loads(json_run.stdout.decode("utf-8"))
            self.assertTrue(json_result["is_clean"])

            strict_run = self.run_cli("--strict", slop_path)
            self.assertEqual(strict_run.returncode, 1)
            self.assertIn("検査レポート", strict_run.stdout.decode("utf-8"))

            stdin_run = self.run_cli(input_bytes="今日は図書館へ行きました。".encode("utf-8"))
            self.assertEqual(stdin_run.returncode, 0)
            self.assertIn("検査レポート", stdin_run.stdout.decode("utf-8"))

            bom_run = self.run_cli("--json", bom_path)
            self.assertEqual(bom_run.returncode, 0)
            self.assertTrue(json.loads(bom_run.stdout.decode("utf-8"))["is_clean"])

            missing_run = self.run_cli(os.path.join(temp_dir, "missing.md"))
            self.assertEqual(missing_run.returncode, 2)
            missing_run.stderr.decode("utf-8")


if __name__ == "__main__":
    unittest.main()
