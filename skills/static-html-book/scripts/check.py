#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ビルド結果（index.html + images/）を検査する。

検査すること:
  - 出力が index.html と images/ 配下の画像だけでできているか
  - 外部の CSS・JavaScript・画像・フォントを読み込んでいないか
  - ページ内リンク（#id）と画像の参照先が存在するか。id が重複していないか
  - HTML のタグの対応が崩れていないか。テンプレートのプレースホルダが残っていないか
  - 各章に「この章で分かること」「まとめ」の見出しと図が1枚以上あるか（--strict でエラー）

使い方:
  python tools/check.py [--book DIR] [--site OUT_DIR] [--strict]
"""
import argparse
from html.parser import HTMLParser
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
BALANCED = {"main", "section", "article", "header", "footer", "nav", "aside", "div", "p", "ol", "ul", "li",
            "figure", "figcaption", "table", "thead", "tbody", "tr", "th", "td", "details", "summary",
            "pre", "code", "h1", "h2", "h3", "h4", "a", "style", "script"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".avif"}
EXTERNAL = re.compile(r"^(?:https?:)?//", re.I)


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.refs = []          # (tag, attr, value)
        self.ids = []
        self.stack = []
        self.errors = []
        self.chapters = []      # {"id", "figures", "headings"}
        self.chapter_depth = None
        self.heading = None
        self.imgs_without_alt = 0
        self.link_tags = []
        self.script_srcs = []
        self.has_cover = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        if a.get("id"):
            self.ids.append(a["id"])
        for attr in ("href", "src", "srcset", "poster"):
            if a.get(attr) is not None:
                self.refs.append((tag, attr, a[attr]))
        if tag == "link":
            self.link_tags.append(a)
        if tag == "script" and a.get("src") is not None:
            self.script_srcs.append(a["src"])
        if tag == "img" and not (a.get("alt") or "").strip():
            self.imgs_without_alt += 1
        if tag == "section" and "cover" in classes and a.get("id") == "top":
            self.has_cover = True
        if tag == "section" and "chapter" in classes and self.chapter_depth is None:
            self.chapters.append({"id": a.get("id", "?"), "figures": 0, "headings": []})
            self.chapter_depth = len(self.stack)
        if self.chapter_depth is not None:
            if tag == "figure" and "fig" in classes:
                self.chapters[-1]["figures"] += 1
            if tag in ("h2", "h3"):
                self.heading = []
        if tag in BALANCED and tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in ("h2", "h3") and self.heading is not None:
            self.chapters[-1]["headings"].append("".join(self.heading).strip())
            self.heading = None
        if tag not in BALANCED or tag in VOID:
            return
        if not self.stack:
            self.errors.append(f"unexpected closing tag </{tag}>")
        elif self.stack[-1] == tag:
            self.stack.pop()
        elif tag in self.stack:
            self.errors.append(f"misnested closing tag </{tag}> (expected </{self.stack[-1]}>)")
            while self.stack and self.stack[-1] != tag:
                self.stack.pop()
            if self.stack:
                self.stack.pop()
        else:
            self.errors.append(f"unexpected closing tag </{tag}>")
        if self.chapter_depth is not None and tag == "section" and len(self.stack) == self.chapter_depth:
            self.chapter_depth = None

    def handle_data(self, data):
        if self.heading is not None:
            self.heading.append(data)


def main():
    ap = argparse.ArgumentParser(description="ビルド結果（index.html + images/）を検査する")
    ap.add_argument("--book", default=".", help="本のディレクトリ（既定: カレント）")
    ap.add_argument("--site", default=None, help="検査する出力ディレクトリ（既定: <book>/site）")
    ap.add_argument("--strict", action="store_true", help="章の型の警告もエラーにする")
    args = ap.parse_args()
    book_dir = Path(args.book).resolve()
    site = Path(args.site).resolve() if args.site else book_dir / "site"
    index = site / "index.html"
    if not index.is_file():
        print(f"check.py: error: {index} がありません（先に build.py を実行してください）", file=sys.stderr)
        return 1
    errors, warnings = [], []

    # 1. 出力の構成：index.html と images/ の画像だけ
    files = [p for p in site.rglob("*") if p.is_file()]
    for p in files:
        rel = p.relative_to(site).as_posix()
        if rel == "index.html":
            continue
        if not (rel.startswith("images/") and p.suffix.lower() in IMAGE_EXTS):
            errors.append(f"出力に index.html と images/ の画像以外のファイルがあります: {rel}")

    text = index.read_text(encoding="utf-8")
    parser = PageParser()
    try:
        parser.feed(text)
        parser.close()
    except Exception as exc:
        errors.append(f"HTML parse failed: {exc}")
    if parser.stack:
        errors.append(f"unclosed tags: {' > '.join(parser.stack)}")
    errors.extend(parser.errors)
    if re.search(r"\{\{[a-zA-Z_][a-zA-Z0-9_]*\}\}", text):
        errors.append("テンプレートのプレースホルダが残っています")

    # 2. 外部・別ファイルの CSS / JavaScript を読み込んでいないか
    for link in parser.link_tags:
        rel = (link.get("rel") or "").lower()
        if any(k in rel for k in ("stylesheet", "preload", "modulepreload", "icon", "manifest")) and link.get("href"):
            if not link["href"].startswith("data:"):
                errors.append(f'<link rel="{rel}" href="{link["href"]}"> は使えません（CSS・アイコンは埋め込む）')
    for src in parser.script_srcs:
        errors.append(f'<script src="{src}"> は使えません（JavaScript は埋め込む）')
    css = "\n".join(re.findall(r"<style\b[^>]*>(.*?)</style>", text, re.S | re.I))
    css += "\n".join(re.findall(r'\sstyle="([^"]*)"', text))
    for m in re.finditer(r"url\(\s*['\"]?([^)'\"]+)", css, re.I):
        if not m.group(1).startswith(("data:", "#")):
            errors.append(f"CSS の url() に外部・別ファイルの参照があります: {m.group(1)}")
    if re.search(r"@import\b", css, re.I):
        errors.append("CSS に @import があります")

    # 3. 参照先
    ids = set(parser.ids)
    dup = sorted({i for i in parser.ids if parser.ids.count(i) > 1})
    if dup:
        errors.append(f"id が重複しています: {', '.join(dup)}")
    used_images = set()
    for tag, attr, ref in parser.refs:
        if attr == "srcset":
            errors.append(f"<{tag} srcset> は使えません（images/ の1枚を src で参照する）")
            continue
        if not ref or ref.startswith(("mailto:", "tel:", "data:")):
            continue
        if ref.startswith("javascript:"):
            errors.append(f"javascript: リンクは使えません: {ref}")
            continue
        if EXTERNAL.match(ref):
            if tag in ("img", "script", "link", "iframe", "source", "video", "audio") or attr != "href":
                errors.append(f"外部リソースを読み込んでいます: <{tag} {attr}={ref}>")
            continue
        u = urlsplit(ref)
        if not u.path:
            frag = unquote(u.fragment)
            if frag and frag not in ids:
                errors.append(f"ページ内リンクの行き先がありません: #{u.fragment}")
            continue
        path = unquote(u.path)
        if path.startswith("images/") and (site / path).is_file():
            used_images.add(path)
            continue
        errors.append(f"index.html と images/ 以外を参照しています: <{tag} {attr}={ref}>")
    if parser.imgs_without_alt:
        warnings.append(f"alt のない画像が {parser.imgs_without_alt} 枚あります")
    for p in files:
        rel = p.relative_to(site).as_posix()
        if rel.startswith("images/") and rel not in used_images:
            warnings.append(f"どこからも参照されていない画像です: {rel}")

    # 4. 本の構成と章の型
    if not parser.has_cover:
        errors.append('表紙 <section class="cover" id="top"> がありません')
    if not parser.chapters:
        errors.append('章 <section class="chapter"> がありません')
    for ch in parser.chapters:
        if ch["figures"] < 1:
            warnings.append(f"{ch['id']}: 図（<figure class=\"fig\">）がありません")
        if not any("この章で分かること" in h for h in ch["headings"]):
            warnings.append(f"{ch['id']}: 見出し「この章で分かること」がありません")
        if not any("まとめ" in h for h in ch["headings"]):
            warnings.append(f"{ch['id']}: 見出し「まとめ」がありません")

    for w in warnings:
        print(("ERROR: " if args.strict else "WARNING: ") + w)
    for e in errors:
        print("ERROR: " + e)
    if errors or (args.strict and warnings):
        print(f"check.py: failed ({len(errors)} errors, {len(warnings)} warnings)")
        return 1
    size_kb = index.stat().st_size // 1024
    print(f"check.py: passed (index.html {size_kb}KB, {len(parser.chapters)} chapters, "
          f"{len(files) - 1} images, {len(warnings)} warnings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
