#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ビルド結果をブラウザで操作して確かめる（Playwright + Chromium）。

references/browser-validation.md のチェックリストのうち、機械で確かめられるものを実行する。
  - file:// と HTTP 配信の両方で、JavaScript 有効時の章切り替え・戻る／進む・キー操作
  - JavaScript 無効時に全章が縦に並ぶこと
  - 375px 幅で横にはみ出さないこと、メニューの開閉
  - コンソールエラーと画像の読み込み失敗がないこと

使い方:
  pip install playwright && python -m playwright install chromium   # 初回のみ
  python tools/browser_check.py [--book DIR] [--site OUT_DIR] [--chrome PATH]

結果は「N件中X件PASS」と「# | テストケース | 結果」の表で出す。1件でも FAIL なら終了コード 1。
"""
import argparse
import functools
import http.server
import re
import sys
import threading
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class Report:
    def __init__(self):
        self.rows = []

    def check(self, name, fn):
        try:
            result = fn()
            ok, note = (result if isinstance(result, tuple) else (bool(result), ""))
        except Exception as exc:  # 1件の失敗で全体を止めない
            ok, note = False, f"{type(exc).__name__}: {str(exc).splitlines()[0][:160]}"
        self.rows.append((name, "PASS" if ok else "FAIL", note))

    def print(self):
        passed = sum(1 for r in self.rows if r[1] == "PASS")
        failed = len(self.rows) - passed
        print(f"\n{len(self.rows)}件中{passed}件PASS／{failed}件FAIL\n")
        print("| # | テストケース | 結果 |")
        print("| --- | --- | --- |")
        for i, (name, res, note) in enumerate(self.rows, 1):
            print(f"| {i} | {name} | {res}{'（' + note + '）' if note and res == 'FAIL' else ''} |")
        return failed


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve(directory):
    handler = functools.partial(QuietHandler, directory=str(directory))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def visible_chapters(page):
    return page.eval_on_selector_all(
        ".chapter", "els => els.filter(e => e.offsetParent !== null || e.getClientRects().length).map(e => e.id)")


def is_visible(page, selector):
    return page.eval_on_selector(selector, "e => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length)")


def no_hscroll(page):
    w = page.evaluate("() => [document.documentElement.scrollWidth, window.innerWidth]")
    return (w[0] <= w[1], f"scrollWidth={w[0]} > {w[1]}" if w[0] > w[1] else "")


def run_js_suite(rep, browser, base, label, slugs):
    errors = []
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(base)
    first, second, last = slugs[0], slugs[1] if len(slugs) > 1 else slugs[0], slugs[-1]

    rep.check(f"[{label}] 表紙だけが表示され、章は隠れている",
              lambda: is_visible(page, "#top") and visible_chapters(page) == [])

    def open_first():
        page.click(".book-actions .btn-primary")
        page.wait_for_function(f"location.hash === '#ch-{first}'")
        vis = visible_chapters(page)
        ok = vis == [f"ch-{first}"] and not is_visible(page, "#top")
        return ok, "" if ok else f"visible={vis}"
    rep.check(f"[{label}]「本を読む」で1章目だけが表示される", open_first)

    def title_and_label():
        t = page.title()
        lab = page.inner_text("#topbar-chapter")
        cur = page.get_attribute(f'.chapter-list a[href="#ch-{first}"]', "aria-current")
        return (lab == "Chapter 01" and "|" in t and cur == "page", f"title={t} label={lab} current={cur}")
    rep.check(f"[{label}] タイトル・章番号・サイドバーの現在位置が変わる", title_and_label)

    def to_second_and_back():
        if second == first:
            return True, "章が1つだけなので省略"
        page.mouse.wheel(0, 600)
        page.wait_for_timeout(400)  # スクロール位置の保存を待つ
        y_before = page.evaluate("scrollY")
        page.click(f'.chapter-list a[href="#ch-{second}"]')
        page.wait_for_function(f"location.hash === '#ch-{second}'")
        top = page.evaluate("scrollY")
        if visible_chapters(page) != [f"ch-{second}"] or top != 0:
            return False, f"2章目へ移動できない（scrollY={top}）"
        page.go_back()
        page.wait_for_function(f"location.hash === '#ch-{first}'")
        page.wait_for_timeout(100)
        y_after = page.evaluate("scrollY")
        ok = visible_chapters(page) == [f"ch-{first}"] and abs(y_after - y_before) < 5
        return ok, "" if ok else f"戻ったときの位置 {y_after}（元は {y_before}）"
    rep.check(f"[{label}] 章を移動し「戻る」で元の章と読んでいた位置に戻る", to_second_and_back)

    def forward_and_cover():
        if second != first:
            page.go_forward()
            page.wait_for_function(f"location.hash === '#ch-{second}'")
        page.goto(base + "#top")
        page.wait_for_timeout(100)
        return is_visible(page, "#top") and visible_chapters(page) == []
    rep.check(f"[{label}]「進む」と #top（表紙）への移動", forward_and_cover)

    def rapid_clicks():
        page.goto(base + f"#ch-{first}")
        for s in slugs * 2:
            page.evaluate(f"document.querySelector('.chapter-list a[href=\"#ch-{s}\"]').click()")
        page.wait_for_timeout(150)
        vis = visible_chapters(page)
        return (vis == [f"ch-{last}"] and page.evaluate("location.hash") == f"#ch-{last}", f"visible={vis}")
    rep.check(f"[{label}] 章リンクを連打しても最後に選んだ章が出る", rapid_clicks)

    def deep_link():
        hid = page.eval_on_selector(f"#ch-{second} .chapter-body h2[id]", "e => e.id")
        page.goto(base + "#top")
        page.goto(base + f"#{hid}")
        page.wait_for_timeout(150)
        top = page.eval_on_selector(f"#{hid}", "e => e.getBoundingClientRect().top")
        ok = visible_chapters(page) == [f"ch-{second}"] and 0 <= top < 200
        return ok, "" if ok else f"見出しの位置 top={top}"
    rep.check(f"[{label}] 見出しアンカーを直接開くと、その章のその見出しが出る", deep_link)

    def reload_keeps():
        page.reload()
        page.wait_for_timeout(150)
        return visible_chapters(page) == [f"ch-{second}"]
    rep.check(f"[{label}] 再読み込みしても同じ章が表示される", reload_keeps)

    def keys():
        page.goto(base + f"#ch-{first}")
        page.keyboard.press("ArrowLeft")
        page.wait_for_timeout(100)
        ok1 = is_visible(page, "#top")
        page.goto(base + f"#ch-{first}")
        if second != first:
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(100)
            ok2 = visible_chapters(page) == [f"ch-{second}"]
        else:
            ok2 = True
        return ok1 and ok2, "" if ok1 and ok2 else f"←={ok1} →={ok2}"
    rep.check(f"[{label}] ←／→キーで前後の章・表紙に移動する", keys)

    def toc_and_copy():
        page.goto(base + f"#ch-{first}")
        cards = page.eval_on_selector_all(".toc-card", "els => els.filter(e => e.offsetParent).length")
        has_copy = page.locator(f"#ch-{first} .copy-btn").count() == page.locator(f"#ch-{first} .code-block").count()
        return cards == 1 and has_copy, f"表示中の目次カード={cards}"
    rep.check(f"[{label}] 右の目次は表示中の章の分だけ。コードにコピーボタンがある", toc_and_copy)

    def images_ok():
        bad = []
        for s in slugs:
            page.goto(base + f"#ch-{s}")
            bad += page.eval_on_selector_all(f"#ch-{s} img", """async els => {
                const bad = [];
                for (const i of els) {
                  i.scrollIntoView();
                  if (!(i.complete && i.naturalWidth)) {
                    await new Promise(r => {
                      i.addEventListener("load", r, {once: true});
                      i.addEventListener("error", r, {once: true});
                      setTimeout(r, 5000);
                    });
                  }
                  if (!i.naturalWidth) bad.push(i.getAttribute("src"));
                }
                return bad;
            }""")
        return (not bad, ", ".join(bad[:3]))
    rep.check(f"[{label}] すべての図が読み込める", images_ok)

    rep.check(f"[{label}] コンソールにエラーが出ない", lambda: (not errors, "; ".join(errors[:2])))
    page.close()


def run_nojs_suite(rep, browser, base, slugs):
    page = browser.new_page(java_script_enabled=False, viewport={"width": 1400, "height": 900})
    page.goto(base)
    rep.check("[JS無効] 表紙のあとに全章が縦に並ぶ",
              lambda: (is_visible(page, "#top") and visible_chapters(page) == [f"ch-{s}" for s in slugs],
                       f"visible={visible_chapters(page)}"))

    def toc_inline():
        n = page.eval_on_selector_all(".toc-inline", "els => els.filter(e => e.offsetParent).length")
        hidden_right = not is_visible(page, "#page-toc")
        return n == len(slugs) and hidden_right, f"章内目次={n} 右の目次表示={not hidden_right}"
    rep.check("[JS無効] 各章に「このチャプターの目次」が出て、右の目次は隠れる", toc_inline)

    def jump():
        target = slugs[-1]
        page.click(f'.chapter-list a[href="#ch-{target}"]')
        page.wait_for_timeout(100)
        top = page.eval_on_selector(f"#ch-{target}", "e => e.getBoundingClientRect().top")
        return 0 <= top < 120, f"top={top}"
    rep.check("[JS無効] サイドバーのリンクで章の位置にジャンプする", jump)

    def details_toggle():
        sel = ".acc > summary"
        if page.locator(sel).count() == 0:
            return True, "折りたたみなし"
        page.locator(sel).first.click()
        return page.eval_on_selector(".acc", "e => e.open")
    rep.check("[JS無効] 確認問題の解答（details）が開閉できる", details_toggle)
    page.close()

    page = browser.new_page(java_script_enabled=False, viewport={"width": 375, "height": 800})
    page.goto(base)
    rep.check("[JS無効・375px] 横にはみ出さない", lambda: no_hscroll(page))

    def menu_link():
        page.click(".menu-btn") if is_visible(page, ".menu-btn") else None
        page.wait_for_timeout(100)
        href = page.get_attribute(".menu-btn", "href")
        top = page.eval_on_selector(href, "e => e.getBoundingClientRect().top")
        links = page.eval_on_selector_all(href + ' a[href^="#ch-"]', "els => els.length")
        return 0 <= top < 120 and links == len(slugs), f"{href} top={top} links={links}"
    rep.check("[JS無効・375px] メニューボタンでチャプター一覧に移動する", menu_link)
    page.close()


def run_mobile_js_suite(rep, browser, base, slugs):
    page = browser.new_page(viewport={"width": 375, "height": 800})
    page.goto(base + f"#ch-{slugs[0]}")
    page.wait_for_timeout(100)
    rep.check("[JS有効・375px] 1列表示で横にはみ出さない", lambda: no_hscroll(page))

    def drawer():
        closed = page.eval_on_selector("#sidebar", "e => e.getBoundingClientRect().right <= 0")
        page.click(".menu-btn")
        page.wait_for_timeout(300)
        opened = page.eval_on_selector("#sidebar", "e => e.getBoundingClientRect().left >= 0")
        expanded = page.get_attribute(".menu-btn", "aria-expanded")
        target = slugs[-1]
        page.click(f'.chapter-list a[href="#ch-{target}"]')
        page.wait_for_timeout(300)
        reclosed = not page.evaluate("document.body.classList.contains('nav-open')")
        ok = closed and opened and expanded == "true" and reclosed and visible_chapters(page) == [f"ch-{target}"]
        return ok, f"初期={closed} 開く={opened} aria={expanded} 閉じる={reclosed}"
    rep.check("[JS有効・375px] メニューで一覧を開き、章を選ぶと閉じる", drawer)

    def escape_closes():
        page.click(".menu-btn")
        page.wait_for_timeout(100)
        page.keyboard.press("Escape")
        return not page.evaluate("document.body.classList.contains('nav-open')")
    rep.check("[JS有効・375px] Esc でメニューが閉じる", escape_closes)
    page.close()


def run_fallback_suite(rep, browser, base, slugs):
    """JavaScript の途中で例外が起きても、縦に並べた表示で読めることを確かめる。"""
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.add_init_script("Object.defineProperty(history, 'replaceState', {value: null});"
                         "Object.defineProperty(window, 'IntersectionObserver', {value: undefined});"
                         "Element.prototype.closest = function () { throw new Error('broken'); };")
    page.goto(base + f"#ch-{slugs[0]}")
    page.wait_for_timeout(150)
    rep.check("[JS失敗時] 例外が起きても全章を縦に並べた表示に戻る",
              lambda: (visible_chapters(page) == [f"ch-{s}" for s in slugs],
                       f"visible={visible_chapters(page)}"))
    page.close()


def main():
    ap = argparse.ArgumentParser(description="ビルド結果をブラウザで確かめる")
    ap.add_argument("--book", default=".", help="本のディレクトリ（既定: カレント）")
    ap.add_argument("--site", default=None, help="既定: <book>/site")
    ap.add_argument("--chrome", default=None, help="Chromium / Chrome の実行ファイル（省略時は Playwright 同梱）")
    args = ap.parse_args()
    site = Path(args.site).resolve() if args.site else Path(args.book).resolve() / "site"
    index = site / "index.html"
    if not index.is_file():
        print(f"browser_check.py: error: {index} がありません", file=sys.stderr)
        return 1
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("browser_check.py: Playwright がありません。"
              "`pip install playwright && python -m playwright install chromium` を実行するか、"
              "references/browser-validation.md の手順で手動確認してください", file=sys.stderr)
        return 2
    slugs = re.findall(r'<section class="chapter" id="ch-([^"]+)"', index.read_text(encoding="utf-8"))
    if not slugs:
        print("browser_check.py: error: 章が見つかりません", file=sys.stderr)
        return 1

    rep = Report()
    httpd = serve(site)
    try:
        with sync_playwright() as p:
            launch = {"executable_path": args.chrome} if args.chrome else {}
            browser = p.chromium.launch(**launch)
            run_js_suite(rep, browser, index.as_uri(), "file://", slugs)
            run_js_suite(rep, browser, f"http://127.0.0.1:{httpd.server_port}/index.html", "HTTP", slugs)
            run_nojs_suite(rep, browser, index.as_uri(), slugs)
            run_mobile_js_suite(rep, browser, index.as_uri(), slugs)
            run_fallback_suite(rep, browser, index.as_uri(), slugs)
            browser.close()
    finally:
        httpd.shutdown()
    return 1 if rep.print() else 0


if __name__ == "__main__":
    raise SystemExit(main())
