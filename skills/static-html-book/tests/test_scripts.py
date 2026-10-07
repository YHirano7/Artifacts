# -*- coding: utf-8 -*-
"""static-html-book スキルのスクリプト群のテスト。"""
import os
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
                          cwd=str(cwd), capture_output=True, text=True, encoding="utf-8")


def minimal_book(root, chapter_md, extra_images=()):
    """テンプレートのレイアウトを使い、章1つだけの本を作る。"""
    shutil.copytree(TEMPLATE / "src" / "templates", root / "src" / "templates")
    shutil.copytree(TEMPLATE / "src" / "assets", root / "src" / "assets")
    (root / "src" / "chapters").mkdir(parents=True)
    (root / "src" / "images").mkdir()
    shutil.copy(TEMPLATE / "src" / "images" / "ch01-book-structure.png", root / "src" / "images" / "a.png")
    for name in extra_images:
        shutil.copy(TEMPLATE / "src" / "images" / "ch01-book-structure.png", root / "src" / "images" / name)
    (root / "src" / "book.json").write_text(
        '{"title": "t", "subtitle": "s", "lang": "ja", "updated": "2026-01-01",'
        ' "chapters": [{"file": "c1.md", "slug": "c1", "title": "c1", "summary": "x"}]}',
        encoding="utf-8")
    (root / "src" / "about.md").write_text("about\n", encoding="utf-8")
    (root / "src" / "chapters" / "c1.md").write_text(
        "## この章で分かること\n\nx\n\n![図](../images/a.png)\n\n" + chapter_md + "\n\n## まとめ\n\nx\n",
        encoding="utf-8")
    return root


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def build(self, book, out=None):
        out = out or self.tmp / "out"
        r = run([SCRIPTS / "build.py", "--book", book, "--out", out], book)
        return r, out

    def test_template_builds_to_html_and_images_only(self):
        r, out = self.build(TEMPLATE)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        files = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
        self.assertEqual(files, ["images/ch01-book-structure.png", "index.html"])
        doc = (out / "index.html").read_text(encoding="utf-8")
        self.assertNotIn('<link rel="stylesheet"', doc)
        self.assertNotIn("<script src=", doc)
        self.assertIn('id="top"', doc)
        self.assertIn('id="ch-01-introduction"', doc)
        self.assertIn('id="ch-02-writing-chapters"', doc)
        self.assertNotIn('href="chapters/', doc)
        self.assertNotIn('href="../', doc)
        r = run([SCRIPTS / "check.py", "--site", out, "--strict"], TEMPLATE)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_rewrites_chapter_links_to_anchors(self):
        book = self.tmp / "book"
        shutil.copytree(TEMPLATE, book)
        ch2 = book / "src" / "chapters" / "02-writing-chapters.md"
        ch2.write_text(ch2.read_text(encoding="utf-8")
                       + "\n[第1章](01-introduction.html)、[節](01-introduction.html#s1-1)、[トップ](../index.html)。\n",
                       encoding="utf-8")
        r, out = self.build(book)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        doc = (out / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="#ch-01-introduction"', doc)
        self.assertIn('href="#s1-1"', doc)
        self.assertIn('href="#top"', doc)

    def test_rejects_link_outside_output(self):
        book = minimal_book(self.tmp / "b", "[サンプル](../samples/x.txt)")
        r, _ = self.build(book)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("unsupported relative link", r.stderr)

    def test_copies_only_referenced_images(self):
        book = minimal_book(self.tmp / "b", "x", extra_images=("unused.png",))
        r, out = self.build(book)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertTrue((out / "images" / "a.png").is_file())
        self.assertFalse((out / "images" / "unused.png").exists())
        self.assertIn("unused.png", r.stdout)

    def test_zenn_syntax(self):
        md = ("```yaml:conf/app.yaml\nkey: value\n```\n\n"
              "``` yaml\nplain: fence\n```\n\n"
              "::::details 外側\n:::message alert\n内側\n:::\n```text\n:::\n```\n::::\n\n"
              "![幅指定](../images/a.png =320x)\n*別のキャプション*\n")
        book = minimal_book(self.tmp / "b", md)
        r, out = self.build(book)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        doc = (out / "index.html").read_text(encoding="utf-8")
        self.assertIn('class="code-file">conf/app.yaml', doc)
        self.assertEqual(doc.count('class="code-block"'), 3)
        self.assertIn('<details class="acc"><summary>外側</summary>', doc)
        self.assertIn('class="msg msg-alert"', doc)
        self.assertIn('width="320" height="180"', doc)
        self.assertIn("<figcaption>別のキャプション</figcaption>", doc)

    def test_duplicate_slug_is_error(self):
        book = minimal_book(self.tmp / "b", "x")
        (book / "src" / "book.json").write_text(
            '{"title": "t", "subtitle": "s", "updated": "2026-01-01", "chapters": ['
            '{"file": "c1.md", "slug": "c1", "title": "a", "summary": "x"},'
            '{"file": "c1.md", "slug": "c1", "title": "b", "summary": "x"}]}', encoding="utf-8")
        r, _ = self.build(book)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("重複", r.stderr)

    def test_old_template_layout_gives_migration_hint(self):
        book = minimal_book(self.tmp / "b", "x")
        (book / "src" / "templates" / "book.html").unlink()
        (book / "src" / "templates" / "index.html").write_text("old", encoding="utf-8")
        r, _ = self.build(book)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("旧形式からの移行", r.stderr)


class CheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.out = self.tmp / "out"
        r = run([SCRIPTS / "build.py", "--book", TEMPLATE, "--out", self.out], TEMPLATE)
        assert r.returncode == 0, r.stderr

    def check(self):
        return run([SCRIPTS / "check.py", "--site", self.out, "--strict"], TEMPLATE)

    def test_rejects_extra_files(self):
        (self.out / "assets").mkdir()
        (self.out / "assets" / "book.js").write_text("x", encoding="utf-8")
        r = self.check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("assets/book.js", r.stdout)

    def test_rejects_external_and_separate_resources(self):
        idx = self.out / "index.html"
        t = idx.read_text(encoding="utf-8")
        t = t.replace("</head>", '<link rel="stylesheet" href="https://cdn.invalid/x.css">'
                                 '<script src="app.js"></script></head>', 1)
        idx.write_text(t, encoding="utf-8")
        r = self.check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("stylesheet", r.stdout)
        self.assertIn("app.js", r.stdout)

    def test_rejects_broken_anchor(self):
        idx = self.out / "index.html"
        idx.write_text(idx.read_text(encoding="utf-8").replace(
            "</main>", '<a href="#nowhere">x</a></main>', 1), encoding="utf-8")
        r = self.check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("#nowhere", r.stdout)


class PublicCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_template_passes(self):
        r = run([SCRIPTS / "public_check.py", "--book", TEMPLATE], TEMPLATE)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_finds_problems(self):
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
        for needle in ("987654321098", "email", "C:\\Users", "fumeibo", "intranet.invalid"):
            self.assertIn(needle, r.stdout)

    def test_allowed_number_and_missing_blocklist_warning(self):
        book = self.tmp / "okbook"
        book.mkdir()
        (book / "public-check.json").write_text(
            '{"allowed_numbers": ["987654321098"], "allow_domains": ["docs.example.com"]}',
            encoding="utf-8")
        (book / "notes.md").write_text("id: 987654321098\nurl: https://docs.example.com/x\n",
                                       encoding="utf-8")
        r = run([SCRIPTS / "public_check.py", "--book", book], book)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("WARNING", r.stdout)


@unittest.skipUnless(os.environ.get("BROWSER_CHECK") == "1", "BROWSER_CHECK=1 のときだけ実行する")
class BrowserCheckTest(unittest.TestCase):
    def test_template_in_browser(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        out = tmp / "out"
        r = run([SCRIPTS / "build.py", "--book", TEMPLATE, "--out", out], TEMPLATE)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = run([SCRIPTS / "browser_check.py", "--site", out], TEMPLATE)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
