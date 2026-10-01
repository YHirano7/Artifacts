#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ビルド済みサイトのリンク、HTML、公開要件を検証する。"""
import argparse
from html.parser import HTMLParser
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

BOOK_ROOT = Path(__file__).resolve().parent.parent
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
BALANCED = {"main", "section", "article", "header", "footer", "nav", "aside", "div", "p", "ol", "ul", "li", "figure", "figcaption", "table", "thead", "tbody", "tr", "th", "td", "details", "summary", "pre", "code", "h1", "h2", "h3", "h4"}


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.refs = []
        self.ids = set()
        self.stack = []
        self.errors = []
        self.resources = []
        self.figures = 0
        self.headings = []
        self.in_heading = False
        self.heading_text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        for attr in ("href", "src"):
            if attrs.get(attr) is not None:
                value = attrs[attr]
                self.refs.append((tag, attr, value))
                if (tag, attr) in (("link", "href"), ("script", "src"), ("img", "src")) and re.match(r"^https?://", value, re.I):
                    self.resources.append(value)
        if "fig" in attrs.get("class", "").split() and tag == "figure":
            self.figures += 1
        if tag in ("h2", "h3") and tag in BALANCED:
            self.in_heading = True
            self.heading_text = []
        if tag in BALANCED and tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in ("h2", "h3") and self.in_heading:
            self.headings.append((tag, "".join(self.heading_text).strip()))
            self.in_heading = False
        if tag in BALANCED and tag not in VOID:
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

    def handle_data(self, data):
        if self.in_heading:
            self.heading_text.append(data)


def main():
    ap = argparse.ArgumentParser(description="built site を検証する")
    ap.add_argument("--site", default=str(BOOK_ROOT / "site"))
    ap.add_argument("--strict", action="store_true", help="章要件の警告をエラーにする")
    args = ap.parse_args()
    site = Path(args.site).resolve()
    errors, warnings = [], []
    html_files = sorted(site.rglob("*.html")) if site.exists() else []
    if not html_files:
        print(f"check.py: error: no HTML files in {site}", file=sys.stderr)
        return 1
    parsed = {}
    for page in html_files:
        parser = PageParser()
        try:
            parser.feed(page.read_text(encoding="utf-8"))
            parser.close()
        except Exception as exc:
            errors.append(f"{page}: HTML parse failed: {exc}")
        if parser.stack:
            errors.append(f"{page}: unclosed tags: {' > '.join(parser.stack)}")
        errors.extend(f"{page}: {e}" for e in parser.errors)
        text = page.read_text(encoding="utf-8")
        if re.search(r"\{\{[a-zA-Z_][a-zA-Z0-9_]*\}\}", text):
            errors.append(f"{page}: unresolved template placeholder")
        parsed[page] = parser

    for page, parser in parsed.items():
        for tag, attr, ref in parser.refs:
            if not ref or ref.startswith(("//", "http://", "https://", "mailto:", "tel:", "data:", "javascript:")):
                continue
            u = urlsplit(ref)
            target = (page.parent / unquote(u.path)).resolve() if u.path else page
            if not target.is_file():
                errors.append(f"{page}: missing {attr} target {ref}")
                continue
            if u.fragment:
                target_parser = parsed.get(target)
                if target_parser is None and target.suffix.lower() == ".html":
                    target_parser = PageParser()
                    target_parser.feed(target.read_text(encoding="utf-8"))
                    parsed[target] = target_parser
                if target_parser and unquote(u.fragment) not in target_parser.ids:
                    errors.append(f"{page}: missing anchor #{u.fragment} in {target}")

        # CSS 外部リソースも禁止（url() / @import）
        for css in re.findall(r"url\(\s*['\"]?([^)'\"]+)", page.read_text(encoding="utf-8"), re.I):
            if re.match(r"https?://", css, re.I):
                errors.append(f"{page}: external CSS resource {css}")
        for value in parser.resources:
            errors.append(f"{page}: external resource {value}")
        if page.parent.name == "chapters":
            if parser.figures < 1:
                warnings.append(f"{page}: <figure class=\"fig\"> がありません")
            texts = [t for _, t in parser.headings]
            if not any("この章で分かること" in t for t in texts):
                warnings.append(f"{page}: 見出し「この章で分かること」がありません")
            if not any("まとめ" in t for t in texts):
                warnings.append(f"{page}: 見出し「まとめ」がありません")

    for warning in warnings:
        print(("ERROR: " if args.strict else "WARNING: ") + warning)
    for error in errors:
        print("ERROR: " + error)
    if errors or (args.strict and warnings):
        print(f"check.py: failed ({len(errors)} errors, {len(warnings)} warnings)")
        return 1
    print(f"check.py: passed ({len(html_files)} HTML files, {len(warnings)} warnings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
