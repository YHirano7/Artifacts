#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zenn本風の静的HTMLドキュメントをビルドする。

src/book.json と src/chapters/*.md から、次の2種類のファイルだけを出力する。

  <out>/index.html   CSS・JavaScript を埋め込んだ1枚のHTML（表紙＋全章）
  <out>/images/      本文から参照している画像だけ

JavaScript が有効なら #ch-<slug> のハッシュで章を1つずつ切り替えて表示し、
無効なら表紙のあとに全章が縦に並んだ1ページとして読める。fetch を使わないので
file:// で開いても、HTTP で配信しても同じように動く。

使い方:
  python tools/build.py                       # 本のディレクトリで実行（出力: site/）
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
    "ts": "typescript", "typescript": "typescript", "tsx": "tsx",
    "js": "javascript", "javascript": "javascript", "jsx": "jsx",
    "sh": "bash", "bash": "bash", "shell": "bash", "zsh": "bash",
    "console": "console", "powershell": "powershell", "ps1": "powershell",
    "yaml": "yaml", "yml": "yaml",
    "json": "json",
    "go": "go", "golang": "go",
    "py": "python", "python": "python",
    "java": "java", "kotlin": "kotlin", "rust": "rust", "rs": "rust",
    "sql": "sql",
    "diff": "diff",
    "html": "html", "xml": "xml", "css": "css",
    "toml": "toml",
    "ini": "ini",
    "hcl": "terraform", "terraform": "terraform", "tf": "terraform",
    "dockerfile": "dockerfile",
    "text": "text", "plaintext": "text", "txt": "text", "none": "text", "": "text",
}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".avif"}

PLACEHOLDER = re.compile(r"\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}")
FENCE_OPEN = re.compile(r"^(`{3,}|~{3,})\s*([^`]*?)\s*$")
FENCE_CLOSE = re.compile(r"^(`{3,}|~{3,})\s*$")
# Zenn と同じく、入れ子にするときは外側のコロンを増やせる（::::details の中に :::message）。
BLOCK_OPEN = re.compile(r"^(:{3,})(message|details)\b\s*(.*)$")
BLOCK_CLOSE = re.compile(r"^(:{3,})\s*$")
# ![代替テキスト](パス =600x "title")。=600x は Zenn の幅指定。
IMAGE_LINE = re.compile(
    r'^!\[([^\]]*)\]\(([^\s)"]+)(?:\s+=(\d+)x)?(?:\s+"([^"]*)")?\)\s*$')
# 画像の直後の行に *キャプション* と書く Zenn の書き方
CAPTION_LINE = re.compile(r"^\*([^*\s][^*]*)\*\s*$")
HEADING = re.compile(r"<h([23])[^>]*>(.*?)</h\1>", re.S)
TABLE_TAG = re.compile(r"<table\b[^>]*>.*?</table>", re.S)
TAG = re.compile(r"<[^>]+>")
LINK_ATTR = re.compile(r'\b(href|src)="([^"]*)"')
HTML_PATH = re.compile(r"^(?:\.\./)?(?:chapters/)?([^/]+)\.html$")
IMG_PATH = re.compile(r"^(?:\.\./)*(images/[^?#]+)$")
ID_ATTR = re.compile(r'\bid="([^"]+)"')
CSS_URL = re.compile(r"url\(\s*['\"]?([^)'\"]+)", re.I)


def die(msg):
    print(f"build.py: error: {msg}", file=sys.stderr)
    sys.exit(1)


def strip_tags(s):
    return html.unescape(TAG.sub("", s))


def esc(s):
    return html.escape(s)


def esc_br(s):
    """HTML エスケープしてから改行を <br> にする（表紙タイトル用）。"""
    return html.escape(s).replace("\n", "<br>")


def image_size(path):
    """画像の (width, height) を返す。分からなければ None。"""
    if path.suffix.lower() == ".png":
        with open(path, "rb") as f:
            head = f.read(33)
        if len(head) < 33 or head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
            die(f"not a PNG file: {path}")
        return struct.unpack(">II", head[16:24])
    if path.suffix.lower() == ".svg":
        return None
    try:
        from PIL import Image
    except ImportError:
        return None
    with Image.open(path) as im:
        return im.size


class ChapterRenderer:
    """1ファイル分の Markdown → HTML 変換。読了時間の計測も担う。"""

    def __init__(self, src_dir, md):
        self.src_dir = src_dir
        self.md = md
        self.formatter = HtmlFormatter(nowrap=True)
        self.text_chars = 0   # 本文の非空白文字数（コードブロック・図を除く）
        self.code_lines = 0   # コードブロックの行数

    def render_code(self, info, code):
        """```lang[:filename] を code-block HTML にする。"""
        lang_raw, _, fname = info.partition(":")
        lang_raw = lang_raw.strip().lower()
        lexer_name = LANG_ALIAS.get(lang_raw, "text")
        try:
            lexer = TextLexer() if lexer_name == "text" else get_lexer_by_name(lexer_name)
        except Exception:
            lexer = TextLexer()
        code_html = highlight(code, lexer, self.formatter)
        self.code_lines += code.count("\n") + (0 if code.endswith("\n") else 1)
        cls = html.escape(lang_raw or "text", quote=True)
        file_div = ""
        if fname.strip():
            file_div = f'<div class="code-file">{html.escape(fname.strip())}</div>'
        return (f'<div class="code-block">{file_div}'
                f'<pre class="hl"><code class="language-{cls}">{code_html}</code></pre></div>')

    def render_figure(self, line, caption=None):
        m = IMAGE_LINE.match(line)
        alt, src, width = m.group(1), m.group(2), m.group(3)
        attrs = ""
        if not re.match(r"^(https?:|data:)", src):
            # ../images/x.png のような src/chapters 相対パスを src_dir 基準で検証する
            rel = re.sub(r"^(\.\./)+", "", src)
            img_path = self.src_dir / rel
            if not img_path.is_file():
                die(f"image not found: {src} (resolved: {img_path})")
            size = image_size(img_path)
            if size and width:
                w = int(width)
                attrs = f' width="{w}" height="{round(size[1] * w / size[0])}"'
            elif size:
                # 図は 2 倍の解像度で作る前提なので、表示サイズは半分にする
                attrs = f' width="{size[0] // 2}" height="{size[1] // 2}"'
            elif width:
                attrs = f' width="{int(width)}"'
        elif width:
            attrs = f' width="{int(width)}"'
        cap = caption if caption is not None else alt
        cap_html = f"<figcaption>{html.escape(cap)}</figcaption>" if cap else ""
        return (f'<figure class="fig"><img src="{html.escape(src, quote=True)}" '
                f'alt="{html.escape(alt, quote=True)}" loading="lazy" decoding="async"'
                f'{attrs}>{cap_html}</figure>')

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

            bm = BLOCK_OPEN.match(line)
            if bm:
                flush()
                colons, kind, rest = bm.group(1), bm.group(2), bm.group(3).strip()
                j = i + 1
                inner = []
                depth = 1
                closed = False
                in_fence = None
                while j < n:
                    cur = lines[j]
                    if in_fence:
                        if FENCE_CLOSE.match(cur) and cur.strip().startswith(in_fence):
                            in_fence = None
                    elif FENCE_OPEN.match(cur):
                        in_fence = FENCE_OPEN.match(cur).group(1)
                    else:
                        om = BLOCK_OPEN.match(cur)
                        cm = BLOCK_CLOSE.match(cur)
                        if om and len(om.group(1)) == len(colons):
                            depth += 1
                        elif cm and len(cm.group(1)) == len(colons):
                            depth -= 1
                            if depth == 0:
                                closed = True
                                break
                    inner.append(cur)
                    j += 1
                if not closed:
                    die(f"unclosed {colons}{kind} block")
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

            if IMAGE_LINE.match(line) and (not buf or not buf[-1].strip()):
                nxt = lines[i + 1] if i + 1 < n else ""
                cap_m = CAPTION_LINE.match(nxt)
                end = i + 2 if cap_m else i + 1
                if end >= n or not lines[end].strip():
                    flush()
                    out.append(self.render_figure(line, cap_m.group(1) if cap_m else None))
                    i = end
                    continue

            buf.append(line)
            i += 1

        flush()
        return "".join(out)

    def render_file(self, path):
        if not path.is_file():
            die(f"file not found: {path}")
        return self.render_lines(path.read_text(encoding="utf-8").splitlines())

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

    return HEADING.sub(repl, body), heads


def build_toc(heads):
    """h2 直下に h3 をネストした <ol class="toc"> を生成する。"""
    cur = None
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
    """{{name}} を単一パスで置換する。未定義のキーはエラー。"""
    def repl(m):
        key = m.group(1)
        if key not in values:
            die(f"unknown placeholder {{{{{key}}}}} in {where}")
        return values[key]
    # 単一パスで置換するので、差し込んだ本文中の {{...}} は再スキャンされない。
    return PLACEHOLDER.sub(repl, template)


def rewrite_refs(fragment, slugs, where, used_images):
    """href/src を1ファイル内の参照に書き換え、参照している画像を集める。"""
    def repl(m):
        attr, ref = m.group(1), m.group(2)
        if not ref or ref.startswith(("#", "http://", "https://", "mailto:", "tel:", "data:")):
            return m.group(0)
        path, _, frag = html.unescape(ref).partition("#")
        mm = HTML_PATH.match(path)
        if mm:
            name = mm.group(1)
            if name in slugs:
                return f'{attr}="#{frag}"' if frag else f'{attr}="#ch-{name}"'
            if name == "index":
                return f'{attr}="#{frag}"' if frag else f'{attr}="#top"'
        im = IMG_PATH.match(path)
        if im:
            used_images.add(im.group(1))
            return f'{attr}="{html.escape(im.group(1), quote=True)}"'
        die(f'unsupported relative link "{ref}" in {where} '
            "（出力は index.html と images/ だけなので、章・表紙・images/ 以外は参照できません）")
    return LINK_ATTR.sub(repl, fragment)


def chapter_list_html(chapters):
    return "\n".join(
        f'<li><a href="#ch-{ch["slug"]}">'
        f'<span class="ch-no">{i}</span>'
        f'<span class="ch-title">{esc(ch["title"])}</span></a></li>'
        for i, ch in enumerate(chapters, 1))


def chapter_cards_html(chapters):
    return "\n".join(
        f'<li><a href="#ch-{ch["slug"]}">'
        f'<span class="ic-no">Chapter {i:02d}</span>'
        f'<span class="ic-title">{esc(ch["title"])}</span>'
        f'<span class="ic-summary">{esc(ch["summary"])}</span></a></li>'
        for i, ch in enumerate(chapters, 1))


def pager_html(chapters, idx, book_title):
    prev_ch = chapters[idx - 1] if idx > 0 else None
    next_ch = chapters[idx + 1] if idx + 1 < len(chapters) else None
    if prev_ch:
        prev = (f'<a class="pager-link prev" href="#ch-{prev_ch["slug"]}" rel="prev">'
                f'<span class="pager-dir">← 前のチャプター</span>'
                f'<span class="pager-title">{esc(prev_ch["title"])}</span></a>')
    else:
        prev = (f'<a class="pager-link prev" href="#top" rel="prev">'
                f'<span class="pager-dir">← 本のトップ</span>'
                f'<span class="pager-title">{esc(book_title)}</span></a>')
    if next_ch:
        nxt = (f'<a class="pager-link next" href="#ch-{next_ch["slug"]}" rel="next">'
               f'<span class="pager-dir">次のチャプター →</span>'
               f'<span class="pager-title">{esc(next_ch["title"])}</span></a>')
    else:
        nxt = (f'<a class="pager-link next" href="#top" rel="next">'
               f'<span class="pager-dir">本のトップへ →</span>'
               f'<span class="pager-title">{esc(book_title)}</span></a>')
    return prev + "\n" + nxt


def format_duration(minutes):
    h, m = divmod(minutes, 60)
    return f"{h}時間{m}分" if h else f"{m}分"


def validate_meta(meta):
    for key in ("title", "subtitle", "updated", "chapters"):
        if not meta.get(key):
            die(f"book.json: {key} は必須です")
    seen = set()
    for i, ch in enumerate(meta["chapters"], 1):
        for key in ("file", "slug", "title", "summary"):
            if not ch.get(key):
                die(f"book.json: chapters[{i}].{key} は必須です")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", ch["slug"]):
            die(f"book.json: slug は英数字・-・_ だけにしてください: {ch['slug']}")
        if ch["slug"] in seen:
            die(f"book.json: slug が重複しています: {ch['slug']}")
        seen.add(ch["slug"])


def load_assets(src_dir):
    css_path, js_path = src_dir / "assets" / "book.css", src_dir / "assets" / "book.js"
    for p in (css_path, js_path):
        if not p.is_file():
            die(f"{p.relative_to(src_dir)} がありません。スキルの template/src/assets からコピーしてください")
    css, js = css_path.read_text(encoding="utf-8"), js_path.read_text(encoding="utf-8")
    for m in CSS_URL.finditer(css):
        if not re.match(r"(data:|#)", m.group(1), re.I):
            die(f"book.css の url() は data: URI だけにしてください（1ファイルに埋め込むため）: {m.group(1)}")
    if re.search(r"@import\b", css, re.I):
        die("book.css に @import は使えません")
    if "</style" in css.lower():
        die("book.css に </style> が含まれるため埋め込めません")
    if "</script" in js.lower():
        die("book.js に </script> が含まれるため埋め込めません")
    return css, js


def load_templates(src_dir):
    tpl_dir = src_dir / "templates"
    names = ("book.html", "cover.html", "chapter.html")
    missing = [n for n in names if not (tpl_dir / n).is_file()]
    if missing:
        old = (tpl_dir / "index.html").is_file()
        hint = ("旧形式（章ごとのHTML）のテンプレートです。references/book-format.md の"
                "「旧形式からの移行」を参照してください" if old else
                "スキルの template/src/templates からコピーしてください")
        die(f"src/templates/ に {', '.join(missing)} がありません。{hint}")
    return {n: (tpl_dir / n).read_text(encoding="utf-8") for n in names}


def main():
    ap = argparse.ArgumentParser(description="Zenn本風の静的HTMLドキュメントをビルドする")
    ap.add_argument("--book", default=".", help="本のディレクトリ（既定: カレント）")
    ap.add_argument("--src", default=None, help="既定: <book>/src")
    ap.add_argument("--out", default=None, help="既定: <book>/site")
    args = ap.parse_args()
    book_dir = Path(args.book).resolve()
    src_dir = Path(args.src).resolve() if args.src else book_dir / "src"
    out_dir = Path(args.out).resolve() if args.out else book_dir / "site"

    meta_path = src_dir / "book.json"
    if not meta_path.is_file():
        die(f"book.json not found: {meta_path}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    validate_meta(meta)
    chapters = meta["chapters"]
    slugs = {ch["slug"] for ch in chapters}
    book_title = meta["title"]
    tpl = load_templates(src_dir)
    css, js = load_assets(src_dir)

    md = markdown.Markdown(extensions=["tables", "sane_lists", "attr_list"])
    used_images = set()
    common = {
        "lang": esc(meta.get("lang", "ja")),
        "book_title": esc(book_title),
        "updated": esc(meta["updated"]),
    }

    sections, toc_cards, total_minutes = [], [], 0
    for idx, ch in enumerate(chapters):
        ch_no = idx + 1
        r = ChapterRenderer(src_dir, md)
        body = wrap_tables(r.render_file(src_dir / "chapters" / ch["file"]))
        body, heads = assign_heading_ids(body, ch_no)
        toc = build_toc(heads)
        minutes = r.reading_minutes()
        total_minutes += minutes
        section = substitute(tpl["chapter.html"], dict(common, **{
            "chapter_slug": ch["slug"],
            "chapter_title": esc(ch["title"]),
            "chapter_summary": esc(ch["summary"]),
            "chapter_no": str(ch_no),
            "chapter_no_padded": f"{ch_no:02d}",
            "reading_minutes": str(minutes),
            "toc": toc,
            "body": body,
            "pager": pager_html(chapters, idx, book_title),
        }), f"chapter.html ({ch['slug']})")
        sections.append(rewrite_refs(section, slugs, f"chapter {ch['slug']}", used_images))
        toc_cards.append(f'<div class="toc-card" data-chapter-toc="ch-{ch["slug"]}">'
                         f'<p class="toc-heading">目次</p>{toc}</div>')
        print(f"rendered {ch['slug']} (約{minutes}分)")

    about_html = ChapterRenderer(src_dir, md).render_file(
        src_dir / meta.get("description_file", "about.md"))
    plain = re.sub(r"\s+", " ", strip_tags(about_html)).strip()
    cover_title = meta.get("cover_title") or book_title
    cover_sub = meta.get("cover_sub") or ""
    cover = substitute(tpl["cover.html"], dict(common, **{
        "cover_title": esc_br(cover_title),
        "cover_sub_html": (f'<span class="cover-sub">{esc_br(cover_sub)}</span>'
                           if cover_sub else ""),
        "book_subtitle": esc(meta["subtitle"]),
        "book_description": about_html,
        "chapter_count": str(len(chapters)),
        "total_hours": format_duration(total_minutes),
        "first_chapter_href": f"#ch-{chapters[0]['slug']}",
        "chapter_cards": chapter_cards_html(chapters),
    }), "cover.html")
    cover = rewrite_refs(cover, slugs, "cover", used_images)

    footer_note = meta.get("footer_note") or ""
    out = substitute(tpl["book.html"], dict(common, **{
        "book_description_plain": esc(plain[:120]),
        "mini_cover_title": esc_br(meta.get("mini_cover_title") or cover_title),
        "chapter_list": chapter_list_html(chapters),
        "cover": cover,
        "chapters": "\n".join(sections),
        "page_tocs": "\n".join(toc_cards),
        "footer_note_html": (f'<p class="footer-note">{esc_br(footer_note)}</p>'
                             if footer_note else ""),
        # CSS・JS は参照の書き換え対象から外すため、あとで差し込む
        "inline_css": "\x00CSS\x00",
        "inline_js": "\x00JS\x00",
    }), "book.html")
    out = rewrite_refs(out, slugs, "book.html", used_images)
    out = out.replace("\x00CSS\x00", css, 1).replace("\x00JS\x00", js, 1)

    ids = ID_ATTR.findall(out)
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        die(f"duplicated id(s) in output: {', '.join(dup)}")

    for rel in sorted(used_images):
        p = src_dir / rel
        if not p.is_file():
            die(f"image not found: {rel}")
        if p.suffix.lower() not in IMAGE_EXTS:
            die(f"画像以外のファイルは出力できません: {rel}")

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    (out_dir / "index.html").write_text(out, encoding="utf-8")
    for rel in sorted(used_images):
        dest = out_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_dir / rel, dest)
    unused = sorted(str(p.relative_to(src_dir)).replace("\\", "/")
                    for p in (src_dir / "images").rglob("*")
                    if p.is_file() and str(p.relative_to(src_dir)).replace("\\", "/") not in used_images) \
        if (src_dir / "images").is_dir() else []
    for u in unused:
        print(f"note: 本文から参照されていない画像はコピーしません: {u}")
    size_kb = (out_dir / "index.html").stat().st_size // 1024
    print(f"built {out_dir.name}/index.html ({len(chapters)} chapters, 約{format_duration(total_minutes)}, "
          f"{size_kb}KB) + images/ ({len(used_images)} files)")


if __name__ == "__main__":
    main()
