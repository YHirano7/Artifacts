#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""静的HTML本ビルドスクリプト。

src/book.json と src/chapters/*.md から site/ を生成する。
使い方: python tools/build.py [--src SRC_DIR] [--out OUT_DIR]
"""
import argparse
import html
import json
import math
import re
import shutil
import struct
import sys
from pathlib import Path

import markdown
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.lexers.special import TextLexer

BOOK_ROOT = Path(__file__).resolve().parent.parent

# Windows コンソール（cp1252 等）でも日本語を出力できるようにする。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# フェンス言語名 → Pygments lexer 名
LANG_ALIAS = {
    "ts": "typescript", "typescript": "typescript",
    "js": "javascript", "javascript": "javascript",
    "sh": "bash", "bash": "bash", "shell": "bash",
    "yaml": "yaml", "yml": "yaml",
    "json": "json",
    "go": "go", "golang": "go",
    "diff": "diff",
    "html": "html",
    "toml": "toml",
    "ini": "ini",
    "dockerfile": "dockerfile",
    "text": "text", "plaintext": "text", "none": "text", "": "text",
}

VOID_CHECK = re.compile(r"\{\{[a-zA-Z_][a-zA-Z0-9_]*\}\}")
FENCE_OPEN = re.compile(r"^(`{3,}|~{3,})s*([^`]*?)s*$")
FENCE_CLOSE = re.compile(r"^(`{3,}|~{3,})\s*$")
ZENN_OPEN = re.compile(r"^:::(message|details)\b\s*(.*)$")
ZENN_CLOSE = re.compile(r"^:::\s*$")
IMAGE_LINE = re.compile(r'^!\[([^\]]*)\]\(([^\s)"]+)(?:\s+"([^"]*)")?\)\s*$')
HEADING = re.compile(r"<h([23])[^>]*>(.*?)</h\1>", re.S)
TABLE_TAG = re.compile(r"<table\b[^>]*>.*?</table>", re.S)
TAG = re.compile(r"<[^>]+>")


def die(msg):
    print(f"build.py: error: {msg}", file=sys.stderr)
    sys.exit(1)


def strip_tags(s):
    return html.unescape(TAG.sub("", s))


def png_size(path):
    """PNG の IHDR から (width, height) を読む。"""
    with open(path, "rb") as f:
        head = f.read(33)
    if len(head) < 33 or head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        die(f"not a PNG file: {path}")
    w, h = struct.unpack(">II", head[16:24])
    return w, h


class ChapterRenderer:
    """1ファイル分の Markdown → HTML 変換。読了時間の計測も担う。"""

    def __init__(self, src_dir, md):
        self.src_dir = src_dir
        self.md = md
        self.formatter = HtmlFormatter(nowrap=True)
        self.text_chars = 0   # 本文の非空白文字数（コードブロック・図版を除く）
        self.code_lines = 0   # コードブロックの行数

    # ---- ブロック部品 ----

    def render_code(self, info, code):
        """```lang[:filename] を code-block HTML にする。"""
        lang_raw, _, fname = info.partition(":")
        lang_raw = lang_raw.strip().lower()
        lexer_name = LANG_ALIAS.get(lang_raw, "text")
        lexer = TextLexer() if lexer_name == "text" else get_lexer_by_name(lexer_name)
        code_html = highlight(code, lexer, self.formatter)
        self.code_lines += code.count("\n") + (0 if code.endswith("\n") else 1)
        cls = html.escape(lang_raw or "text", quote=True)
        file_div = ""
        if fname.strip():
            file_div = f'<div class="code-file">{html.escape(fname.strip())}</div>'
        return (f'<div class="code-block">{file_div}'
                f'<pre class="hl"><code class="language-{cls}">{code_html}</code></pre></div>')

    def render_figure(self, line):
        m = IMAGE_LINE.match(line)
        alt, src = m.group(1), m.group(2)
        # ../images/x.png のような src/chapters 相対パスを src_dir 基準で検証する
        rel = re.sub(r"^(\.\./)+", "", src)
        img_path = self.src_dir / rel
        if not img_path.is_file():
            die(f"image not found: {src} (resolved: {img_path})")
        w, h = png_size(img_path)
        w, h = w // 2, h // 2  # インフォグラフィックは deviceScaleFactor 2 で描画済み
        return (f'<figure class="fig"><img src="{html.escape(src, quote=True)}" '
                f'alt="{html.escape(alt, quote=True)}" loading="lazy" '
                f'width="{w}" height="{h}">'
                f'<figcaption>{html.escape(alt)}</figcaption></figure>')

    # ---- ブロック走査 ----

    def render_lines(self, lines):
        """行リストを HTML に変換する。:::details / :::message は再帰処理。"""
        out = []
        buf = []

        def flush():
            while buf and not buf[0].strip():
                buf.pop(0)
            while buf and not buf[-1].strip():
                buf.pop()
            if buf:
                seg = self.md.reset().convert("\n".join(buf))
                self.text_chars += sum(1 for c in strip_tags(seg) if not c.isspace())
                out.append(seg)
            buf.clear()

        i = 0
        n = len(lines)
        while i < n:
            line = lines[i]

            fm = FENCE_OPEN.match(line)
            if fm:
                flush()
                fence, info = fm.group(1), fm.group(2)
                j = i + 1
                code_lines = []
                closed = False
                while j < n:
                    cm = FENCE_CLOSE.match(lines[j])
                    if cm and cm.group(1)[0] == fence[0] and len(cm.group(1)) >= len(fence):
                        closed = True
                        break
                    code_lines.append(lines[j])
                    j += 1
                if not closed:
                    die(f"unclosed code fence: {line!r}")
                out.append(self.render_code(info, "\n".join(code_lines)))
                i = j + 1
                continue

            zm = ZENN_OPEN.match(line)
            if zm:
                flush()
                kind, rest = zm.group(1), zm.group(2).strip()
                j = i + 1
                inner = []
                depth = 1
                closed = False
                while j < n:
                    if ZENN_OPEN.match(lines[j]):
                        depth += 1
                    elif ZENN_CLOSE.match(lines[j]):
                        depth -= 1
                        if depth == 0:
                            closed = True
                            break
                    inner.append(lines[j])
                    j += 1
                if not closed:
                    die(f"unclosed :::{kind} block")
                body = self.render_lines(inner)
                if kind == "message":
                    variant = "msg-alert" if rest == "alert" else "msg-info"
                    out.append(f'<aside class="msg {variant}"><div class="msg-body">{body}</div></aside>')
                else:
                    title = self.md.reset().convert(rest) if rest else ""
                    title = re.sub(r"^<p>|</p>$", "", title.strip())
                    if not title:
                        title = "詳細"
                    out.append(f'<details class="acc"><summary>{title}</summary>'
                               f'<div class="acc-body">{body}</div></details>')
                i = j + 1
                continue

            if IMAGE_LINE.match(line) and (i + 1 == n or not lines[i + 1].strip()) \
                    and (not buf or not buf[-1].strip()):
                flush()
                out.append(self.render_figure(line))
                i += 1
                continue

            buf.append(line)
            i += 1

        flush()
        return "".join(out)

    def render_file(self, path):
        if not path.is_file():
            die(f"chapter file not found: {path}")
        text = path.read_text(encoding="utf-8")
        return self.render_lines(text.splitlines())

    def reading_minutes(self):
        return max(1, math.ceil(self.text_chars / 500 + self.code_lines / 20))


def assign_heading_ids(body, chapter_no):
    """h2/h3 に s<章番号>-<連番> の id を付け、目次用の見出し一覧を返す。"""
    heads = []
    counter = [0]

    def repl(m):
        counter[0] += 1
        hid = f"s{chapter_no}-{counter[0]}"
        level = int(m.group(1))
        inner = m.group(2)
        heads.append((level, hid, strip_tags(inner).strip()))
        return f'<h{level} id="{hid}">{inner}</h{level}>'

    body = HEADING.sub(repl, body)
    return body, heads


def build_toc(heads):
    """h2 直下に h3 をネストした <ol class="toc"> を生成。"""
    if not heads:
        return '<ol class="toc"></ol>'
    items = []
    cur = None  # [level, id, text, children]
    roots = []
    for level, hid, text in heads:
        node = (hid, text, [])
        if level == 3 and cur is not None:
            cur[2].append(node)
        else:
            roots.append(node)
            cur = node

    def node_html(node):
        hid, text, children = node
        s = f'<li><a href="#{hid}">{html.escape(text)}</a>'
        if children:
            s += "<ol>" + "".join(node_html(c) for c in children) + "</ol>"
        return s + "</li>"

    return '<ol class="toc">' + "".join(node_html(r) for r in roots) + "</ol>"


def wrap_tables(body):
    return TABLE_TAG.sub(lambda m: f'<div class="table-wrap">{m.group(0)}</div>', body)


def substitute(template, values, where):
    """{{name}} を単一パスで置換する。未定義キー・残留プレースホルダはエラー。"""
    def repl(m):
        key = m.group(1)
        if key not in values:
            die(f"unknown placeholder {{{{{key}}}}} in {where}")
        return values[key]
    # 単一パスで置換する。コンテンツ中の {{...}} は再スキャンされない。
    out = re.sub(r"\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}", repl, template)
    if VOID_CHECK.search(out):
        die(f"unsubstituted placeholder remains in {where}: "
            f"{VOID_CHECK.search(out).group(0)}")
    return out


def esc(s):
    return html.escape(s)


def chapter_list_html(chapters, current_slug):
    items = []
    for i, ch in enumerate(chapters, 1):
        cur = ' aria-current="page"' if ch["slug"] == current_slug else ""
        items.append(
            f'<li><a href="{ch["slug"]}.html"{cur}>'
            f'<span class="ch-no">{i}</span>'
            f'<span class="ch-title">{esc(ch["title"])}</span></a></li>')
    return "\n".join(items)


def chapter_cards_html(chapters):
    items = []
    for i, ch in enumerate(chapters, 1):
        items.append(
            f'<li><a href="chapters/{ch["slug"]}.html">'
            f'<span class="ic-no">Chapter {i:02d}</span>'
            f'<span class="ic-title">{esc(ch["title"])}</span>'
            f'<span class="ic-summary">{esc(ch["summary"])}</span></a></li>')
    return "\n".join(items)


def pager_html(chapters, idx, book_title):
    prev_ch = chapters[idx - 1] if idx > 0 else None
    next_ch = chapters[idx + 1] if idx + 1 < len(chapters) else None
    if prev_ch:
        prev = (f'<a class="pager-link prev" href="{prev_ch["slug"]}.html" rel="prev">'
                f'<span class="pager-dir">← 前のチャプター</span>'
                f'<span class="pager-title">{esc(prev_ch["title"])}</span></a>')
    else:
        prev = (f'<a class="pager-link prev" href="../index.html" rel="prev">'
                f'<span class="pager-dir">← 本のトップ</span>'
                f'<span class="pager-title">{esc(book_title)}</span></a>')
    if next_ch:
        nxt = (f'<a class="pager-link next" href="{next_ch["slug"]}.html" rel="next">'
               f'<span class="pager-dir">次のチャプター →</span>'
               f'<span class="pager-title">{esc(next_ch["title"])}</span></a>')
    else:
        nxt = (f'<a class="pager-link next" href="../index.html" rel="next">'
               f'<span class="pager-dir">本のトップへ →</span>'
               f'<span class="pager-title">{esc(book_title)}</span></a>')
    return prev + "\n" + nxt


def format_duration(minutes):
    h, m = divmod(minutes, 60)
    return f"{h}時間{m}分" if h else f"{m}分"


def main():
    ap = argparse.ArgumentParser(description="静的HTML本をビルドする")
    ap.add_argument("--src", default=str(BOOK_ROOT / "src"))
    ap.add_argument("--out", default=str(BOOK_ROOT / "site"))
    args = ap.parse_args()
    src_dir, out_dir = Path(args.src), Path(args.out)

    meta_path = src_dir / "book.json"
    if not meta_path.is_file():
        die(f"book.json not found: {meta_path}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    chapters = meta["chapters"]
    book_title = meta["title"]

    tpl_index = (src_dir / "templates" / "index.html").read_text(encoding="utf-8")
    tpl_chapter = (src_dir / "templates" / "chapter.html").read_text(encoding="utf-8")

    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "chapters").mkdir(parents=True)
    if (src_dir / "assets").is_dir():
        shutil.copytree(src_dir / "assets", out_dir / "assets")
    if (src_dir / "images").is_dir():
        shutil.copytree(src_dir / "images", out_dir / "images")

    md = markdown.Markdown(extensions=["tables", "sane_lists", "attr_list"])
    total_minutes = 0

    for idx, ch in enumerate(chapters):
        ch_no = idx + 1
        r = ChapterRenderer(src_dir, md)
        body = r.render_file(src_dir / "chapters" / ch["file"])
        body = wrap_tables(body)
        body, heads = assign_heading_ids(body, ch_no)
        toc = build_toc(heads)
        minutes = r.reading_minutes()
        total_minutes += minutes
        html_out = substitute(tpl_chapter, {
            "book_title": esc(book_title),
            "chapter_title": esc(ch["title"]),
            "chapter_summary": esc(ch["summary"]),
            "chapter_no": str(ch_no),
            "chapter_no_padded": f"{ch_no:02d}",
            "reading_minutes": str(minutes),
            "updated": esc(meta["updated"]),
            "chapter_list": chapter_list_html(chapters, ch["slug"]),
            "toc": toc,
            "body": body,
            "pager": pager_html(chapters, idx, book_title),
        }, f"chapter {ch['slug']}")
        (out_dir / "chapters" / f"{ch['slug']}.html").write_text(html_out, encoding="utf-8")
        print(f"built chapters/{ch['slug']}.html (約{minutes}分)")

    # index
    desc_file = meta.get("description_file", "about.md")
    r = ChapterRenderer(src_dir, md)
    about_html = r.render_file(src_dir / desc_file)
    plain = re.sub(r"\s+", " ", strip_tags(about_html)).strip()
    about_plain = esc(plain[:120])
    index_html = substitute(tpl_index, {
        "book_title": esc(book_title),
        "book_subtitle": esc(meta["subtitle"]),
        "book_description_plain": about_plain,
        "book_description": about_html,
        "chapter_count": str(len(chapters)),
        "total_hours": format_duration(total_minutes),
        "updated": esc(meta["updated"]),
        "first_chapter_href": f"chapters/{chapters[0]['slug']}.html",
        "chapter_cards": chapter_cards_html(chapters),
    }, "index.html")
    (out_dir / "index.html").write_text(index_html, encoding="utf-8")
    print(f"built index.html ({len(chapters)} chapters, 約{format_duration(total_minutes)})")


if __name__ == "__main__":
    main()
