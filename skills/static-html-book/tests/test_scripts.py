# -*- coding: utf-8 -*-
"""static-html-book スキルのスクリプト群のテスト。"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL / "scripts"
TEMPLATE = SKILL / "template"


def run(args, cwd):
    return subprocess.run([sys.executable] + [str(a) for a in args],
                          cwd=str(cwd), capture_output=True, text=True)


class TemplateBookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.site = self.tmp / "site"

    def test_build_and_check_template(self):
        r = run([SCRIPTS / "build.py", "--book", TEMPLATE, "--out", self.site], TEMPLATE)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertTrue((self.site / "index.html").is_file())
        r = run([SCRIPTS / "check.py", "--site", self.site, "--strict"], TEMPLATE)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_public_check_template_passes(self):
        r = run([SCRIPTS / "public_check.py", "--book", TEMPLATE], TEMPLATE)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_public_check_finds_problems(self):
        book = self.tmp / "badbook"
        book.mkdir()
        (book / "notes.md").write_text(
            "id: 987654321098\n"
            "mail: user@mail.invalid\n"
            "path: C:\\Users\\someone\\secret.txt\n"
            "word: fumeibo\n"
            "url: https://intranet.invalid/doc\n",
            encoding="utf-8")
        bl = self.tmp / "blocklist.txt"
        bl.write_text("# comment\nfumeibo\n", encoding="utf-8")
        r = run([SCRIPTS / "public_check.py", "--book", book, "--blocklist", bl], book)
        self.assertEqual(r.returncode, 1)
        self.assertIn("987654321098", r.stdout)
        self.assertIn("email", r.stdout)
        self.assertIn("C:\\Users", r.stdout)
        self.assertIn("fumeibo", r.stdout)
        self.assertIn("intranet.invalid", r.stdout)

    def test_public_check_allowed_number_and_blocklist_env(self):
        book = self.tmp / "okbook"
        book.mkdir()
        (book / "public-check.json").write_text(
            '{"allowed_numbers": ["987654321098"], "allow_domains": ["docs.example.com"]}',
            encoding="utf-8")
        (book / "notes.md").write_text(
            "id: 987654321098\nurl: https://docs.example.com/x\n",
            encoding="utf-8")
        r = run([SCRIPTS / "public_check.py", "--book", book], book)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("WARNING", r.stdout)  # ブロックリスト未指定の警告

    def test_single_format_build(self):
        r = run([SCRIPTS / "build.py", "--book", TEMPLATE, "--format", "single",
                 "--out", self.tmp / "single"], TEMPLATE)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        single = self.tmp / "single"
        self.assertTrue((single / "index.html").is_file())
        self.assertTrue((single / "images" / "ch01-book-structure.png").is_file())
        self.assertFalse((single / "assets").exists())
        doc = (single / "index.html").read_text(encoding="utf-8")
        self.assertNotIn('<link rel="stylesheet"', doc)
        self.assertNotIn('<script src=', doc)
        self.assertIn('id="ch-01-introduction"', doc)
        self.assertIn('id="top"', doc)
        self.assertNotIn('href="chapters/', doc)
        self.assertNotIn('href="../index.html"', doc)
        r = run([SCRIPTS / "check.py", "--site", single, "--strict"], TEMPLATE)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_single_format_rewrites_links(self):
        book = self.tmp / "book-links"
        shutil.copytree(TEMPLATE, book)
        ch2 = book / "src" / "chapters" / "02-writing-chapters.md"
        ch2.write_text(ch2.read_text(encoding="utf-8")
                       + "\n[第1章](01-introduction.html) と [節](01-introduction.html#s1-1) へのリンク。\n",
                       encoding="utf-8")
        single = self.tmp / "single-links"
        r = run([SCRIPTS / "build.py", "--book", book, "--format", "single",
                 "--out", single], book)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        doc = (single / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="#ch-01-introduction"', doc)
        self.assertIn('href="#s1-1"', doc)

    def test_single_format_rejects_unknown_relative_link(self):
        book = self.tmp / "book-badlink"
        shutil.copytree(TEMPLATE, book)
        ch2 = book / "src" / "chapters" / "02-writing-chapters.md"
        ch2.write_text(ch2.read_text(encoding="utf-8")
                       + "\n[サンプル](../samples/x.txt)\n",
                       encoding="utf-8")
        r = run([SCRIPTS / "build.py", "--book", book, "--format", "single",
                 "--out", self.tmp / "single-bad"], book)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("unsupported relative link", r.stderr)

    def test_code_fence_variants(self):
        """```yaml:file と ``` yaml の両方がコードブロックになる。"""
        book = self.tmp / "book"
        for sub in ("src/chapters", "src/templates", "src/assets", "src/images"):
            (book / sub).mkdir(parents=True)
        shutil.copy(TEMPLATE / "src" / "templates" / "index.html", book / "src/templates/index.html")
        shutil.copy(TEMPLATE / "src" / "templates" / "chapter.html", book / "src/templates/chapter.html")
        (book / "src" / "book.json").write_text(
            '{"title": "t", "subtitle": "s", "lang": "ja", "updated": "2026-01-01",'
            ' "chapters": [{"file": "c1.md", "slug": "c1", "title": "c1", "summary": "x"}]}',
            encoding="utf-8")
        (book / "src" / "about.md").write_text("about\n", encoding="utf-8")
        (book / "src" / "chapters" / "c1.md").write_text(
            "## この章で分かること\n\nx\n\n## まとめ\n\nx\n\n"
            "```yaml:conf/app.yaml\nkey: value\n```\n\n"
            "``` yaml\nplain: fence\n```\n",
            encoding="utf-8")
        site = self.tmp / "site2"
        r = run([SCRIPTS / "build.py", "--book", book, "--out", site], book)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        html = (site / "chapters" / "c1.html").read_text(encoding="utf-8")
        self.assertIn('class="code-file">conf/app.yaml', html)
        self.assertIn('language-yaml', html)
        self.assertEqual(html.count('class="code-block"'), 2)


if __name__ == "__main__":
    unittest.main()
