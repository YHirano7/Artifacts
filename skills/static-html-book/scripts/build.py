#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""静的HTML本ビルドスクリプト。

src/book.json と src/chapters/*.md から site/ を生成する。
使い方:
  python tools/build.py                      # 本のディレクトリで実行
  python build.py --book DIR [--src SRC_DIR] [--out OUT_DIR]
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
FENCE_OPEN = re.compile(r"^(`{3,}|~{3,})\s*([^`]*?)\s*$")
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


def esc_br(s):
    """HTML エスケープしてから改行を <br> にする（表紙タイトル用）。"""
    return html.escape(s).replace("\n", "<br>")


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


def meta_display(meta):
    """表紙・フッターなど、全ページ共通の表示値を返す。改行は <br> にする。"""
    book_title = meta["title"]
    cover_title = meta.get("cover_title") or book_title
    mini_cover_title = meta.get("mini_cover_title") or cover_title
    footer_note = meta.get("footer_note") or ""
    return {
        "lang": esc(meta.get("lang", "ja")),
        "book_title": esc(book_title),
        "cover_title": esc_br(cover_title),
        "mini_cover_title": esc_br(mini_cover_title),
        "footer_note_html": (f'<p class="footer-note">{esc_br(footer_note)}</p>'
                             if footer_note else ""),
        "updated": esc(meta["updated"]),
    }


def render_chapter(src_dir, md, ch, ch_no):
    """章 Markdown → (body HTML, toc HTML, 読了分数)。両フォーマットで共用。"""
    r = ChapterRenderer(src_dir, md)
    body = r.render_file(src_dir / "chapters" / ch["file"])
    body = wrap_tables(body)
    body, heads = assign_heading_ids(body, ch_no)
    return body, build_toc(heads), r.reading_minutes()


def chapter_page_values(disp, chapters, ch, idx, toc, body, minutes):
    """chapter.html に渡す値一式。サイト版・単一ファイル版で同じページを作る。"""
    ch_no = idx + 1
    v = dict(disp)
    v.update({
        "chapter_title": esc(ch["title"]),
        "chapter_summary": esc(ch["summary"]),
        "chapter_no": str(ch_no),
        "chapter_no_padded": f"{ch_no:02d}",
        "reading_minutes": str(minutes),
        "chapter_list": chapter_list_html(chapters, ch["slug"]),
        "toc": toc,
        "body": body,
        "pager": pager_html(chapters, idx, disp["book_title"]),
    })
    return v


def render_index(src_dir, md, tpl_index, meta, disp, chapters, total_minutes):
    """index.html のレンダリング結果（全文）を返す。"""
    desc_file = meta.get("description_file", "about.md")
    r = ChapterRenderer(src_dir, md)
    about_html = r.render_file(src_dir / desc_file)
    plain = re.sub(r"\s+", " ", strip_tags(about_html)).strip()
    return substitute(tpl_index, {
        "lang": disp["lang"],
        "book_title": disp["book_title"],
        "cover_title": disp["cover_title"],
        "footer_note_html": disp["footer_note_html"],
        "book_subtitle": esc(meta["subtitle"]),
        "book_description_plain": esc(plain[:120]),
        "book_description": about_html,
        "chapter_count": str(len(chapters)),
        "total_hours": format_duration(total_minutes),
        "updated": disp["updated"],
        "first_chapter_href": f"chapters/{chapters[0]['slug']}.html",
        "chapter_cards": chapter_cards_html(chapters),
    }, "index.html")


# ---- 単一ファイル（single）フォーマット ----

ARTICLE_RE = re.compile(r'<article class="chapter-card">.*</article>', re.S)
MAIN_INNER_RE = re.compile(r"<main\b[^>]*>(.*)</main>", re.S)
LINK_ATTR = re.compile(r'(href|src)="([^"]*)"')
HTML_PATH = re.compile(r"^(?:\.\./)?(?:chapters/)?([^/]+)\.html$")
IMG_PATH = re.compile(r"^(?:\.\./)?(images/.+)$")
ID_ATTR = re.compile(r'\bid="([^"]+)"')
CSS_URL = re.compile(r"url\(\s*['\"]?([^)'\"]+)", re.I)


def rewrite_refs(fragment, slugs, where):
    """href/src を単一ファイル内の参照に書き換える。未対応の相対リンクはエラー。"""
    def repl(m):
        attr, ref = m.group(1), m.group(2)
        if not ref or ref.startswith(("#", "http://", "https://", "mailto:", "tel:", "data:")):
            return m.group(0)
        path, _, frag = ref.partition("#")
        mm = HTML_PATH.match(path)
        if mm:
            name = mm.group(1)
            if name in slugs:
                return f'{attr}="#{frag}"' if frag else f'{attr}="#ch-{name}"'
            if name == "index":
                return f'{attr}="#{frag}"' if frag else f'{attr}="#top"'
        im = IMG_PATH.match(path)
        if im:
            return f'{attr}="{im.group(1)}"'
        die(f'single format: unsupported relative link "{ref}" in {where}')
    return LINK_ATTR.sub(repl, fragment)


def chapter_list_single(chapters):
    items = []
    for i, ch in enumerate(chapters, 1):
        items.append(
            f'<li><a href="#ch-{ch["slug"]}">'
            f'<span class="ch-no">{i}</span>'
            f'<span class="ch-title">{esc(ch["title"])}</span></a></li>')
    return "\n".join(items)


def build_single(src_dir, out_dir, meta, disp, chapters, rendered, index_html):
    """1つの index.html + images/ を出力する。"""
    needed = [src_dir / "templates" / "single.html",
              src_dir / "assets" / "book-single.css",
              src_dir / "assets" / "book-single.js"]
    missing = [str(p.relative_to(src_dir)) for p in needed if not p.is_file()]
    if missing:
        die("single format には src/ に次のファイルが必要です: "
            + ", ".join(missing)
            + "。スキルの template/src からコピーしてください。")

    book_css = (src_dir / "assets" / "book.css").read_text(encoding="utf-8")
    for m in CSS_URL.finditer(book_css):
        if not re.match(r"(https?:|data:|#)", m.group(1), re.I):
            die(f"book.css に相対パスの url() があるため単一ファイルにできません: {m.group(1)}")
    inline_css = book_css + "\n" + (src_dir / "assets" / "book-single.css").read_text(encoding="utf-8")
    inline_js = (src_dir / "assets" / "book-single.js").read_text(encoding="utf-8")
    for name, text in (("book-single.css", inline_css), ("book-single.js", inline_js)):
        if "</style" in text.lower() or "</script" in text.lower():
            die(f"{name} に </script> または </style> が含まれるためインライン化できません")

    slugs = {ch["slug"] for ch in chapters}
    book_title = meta["title"]

    # 表紙: index.html の <main> の中身
    m = MAIN_INNER_RE.search(index_html)
    if not m:
        die("index.html テンプレートの出力に <main> が見つかりません（src/templates/index.html を確認）")
    cover = rewrite_refs(m.group(1), slugs, "cover")

    sections, toc_cards = [], []
    for (ch, ch_no, _toc, page_html, _min) in rendered:
        m = ARTICLE_RE.search(page_html)
        if not m:
            die("chapter テンプレートの出力に <article class=\"chapter-card\"> が見つかりません"
                f"（src/templates/chapter.html を確認）: {ch['slug']}")
        article = rewrite_refs(m.group(0), slugs, f"chapter {ch['slug']}")
        pager = rewrite_refs(pager_html(chapters, ch_no - 1, book_title),
                             slugs, f"pager of {ch['slug']}")
        toc_card = (f'<div class="toc-card" data-chapter-toc="ch-{ch["slug"]}">'
                    f'<p class="toc-heading">目次</p>{_toc}</div>')
        sections.append(
            f'<section class="single-chapter" id="ch-{ch["slug"]}" '
            f'data-title="{html.escape(ch["title"] + " | " + book_title, quote=True)}" '
            f'data-label="Chapter {ch_no:02d}">\n'
            f'{article}\n'
            f'<nav class="pager" aria-label="チャプター移動">\n{pager}\n</nav>\n'
            f'</section>')
        toc_cards.append(toc_card)

    tpl_single = (src_dir / "templates" / "single.html").read_text(encoding="utf-8")
    out = substitute(tpl_single, {
        "lang": disp["lang"],
        "book_title": disp["book_title"],
        "book_description_plain": substitute_index_plain(index_html),
        "mini_cover_title": disp["mini_cover_title"],
        "footer_note_html": disp["footer_note_html"],
        "updated": disp["updated"],
        "chapter_list": rewrite_refs(chapter_list_single(chapters), slugs, "chapter_list"),
        "cover": cover,
        "chapters": "\n".join(sections),
        "page_tocs": "\n".join(toc_cards),
        "inline_css": inline_css,
        "inline_js": inline_js,
    }, "single.html")

    ids = ID_ATTR.findall(out)
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        die(f"single format: duplicated id(s) in output: {', '.join(dup)}")

    out_dir.mkdir(parents=True)
    (out_dir / "index.html").write_text(out, encoding="utf-8")
    if (src_dir / "images").is_dir():
        shutil.copytree(src_dir / "images", out_dir / "images")
    print(f"built index.html (single: {len(chapters)} chapters)")


def substitute_index_plain(index_html):
    """レンダリング済み index.html から meta description 用のテキストを取り出す。"""
    m = re.search(r'<meta name="description" content="([^"]*)">', index_html)
    return m.group(1) if m else ""


def main():
    ap = argparse.ArgumentParser(description="静的HTML本をビルドする")
    ap.add_argument("--book", default=".", help="本のディレクトリ（既定: カレント）")
    ap.add_argument("--src", default=None, help="既定: <book>/src")
    ap.add_argument("--out", default=None,
                    help="既定: <book>/site（--format site）、<book>/single（--format single）")
    ap.add_argument("--format", choices=["site", "single"], default="site",
                    help="出力形式（既定: site）")
    args = ap.parse_args()
    book_dir = Path(args.book).resolve()
    src_dir = Path(args.src).resolve() if args.src else book_dir / "src"
    out_dir = (Path(args.out).resolve() if args.out
               else book_dir / ("site" if args.format == "site" else "single"))

    meta_path = src_dir / "book.json"
    if not meta_path.is_file():
        die(f"book.json not found: {meta_path}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    chapters = meta["chapters"]
    book_title = meta["title"]
    disp = meta_display(meta)

    tpl_index = (src_dir / "templates" / "index.html").read_text(encoding="utf-8")
    tpl_chapter = (src_dir / "templates" / "chapter.html").read_text(encoding="utf-8")

    if out_dir.exists():
        shutil.rmtree(out_dir)
    md = markdown.Markdown(extensions=["tables", "sane_lists", "attr_list"])
    total_minutes = 0

    if args.format == "single":
        rendered = []
        for idx, ch in enumerate(chapters):
            ch_no = idx + 1
            body, toc, minutes = render_chapter(src_dir, md, ch, ch_no)
            total_minutes += minutes
            page_html = substitute(tpl_chapter,
                                   chapter_page_values(disp, chapters, ch, idx, toc, body, minutes),
                                   f"chapter {ch['slug']}")
            rendered.append((ch, ch_no, toc, page_html, minutes))
        index_html = render_index(src_dir, md, tpl_index, meta, disp, chapters, total_minutes)
        build_single(src_dir, out_dir, meta, disp, chapters, rendered, index_html)
        return

    (out_dir / "chapters").mkdir(parents=True)
    if (src_dir / "assets").is_dir():
        # single 専用のアセットは埋め込み用なので、章ごとのサイトにはコピーしない
        shutil.copytree(src_dir / "assets", out_dir / "assets",
                        ignore=shutil.ignore_patterns("book-single.css", "book-single.js"))
    if (src_dir / "images").is_dir():
        shutil.copytree(src_dir / "images", out_dir / "images")

    for idx, ch in enumerate(chapters):
        ch_no = idx + 1
        body, toc, minutes = render_chapter(src_dir, md, ch, ch_no)
        total_minutes += minutes
        html_out = substitute(tpl_chapter,
                              chapter_page_values(disp, chapters, ch, idx, toc, body, minutes),
                              f"chapter {ch['slug']}")
        (out_dir / "chapters" / f"{ch['slug']}.html").write_text(html_out, encoding="utf-8")
        print(f"built chapters/{ch['slug']}.html (約{minutes}分)")

    index_html = render_index(src_dir, md, tpl_index, meta, disp, chapters, total_minutes)
    (out_dir / "index.html").write_text(index_html, encoding="utf-8")
    print(f"built index.html ({len(chapters)} chapters, 約{format_duration(total_minutes)})")


if __name__ == "__main__":
    main()
