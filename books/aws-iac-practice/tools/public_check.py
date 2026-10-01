#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公開用ファイルに個人情報・実在アカウントID等がないか調べる。

使い方:
  python tools/public_check.py [--book DIR] [--blocklist FILE]

検出するもの:
  - 12桁の数字（許可リスト以外。AWS アカウント ID などの検出用）
  - example.com / example.org / example.net 以外のメールアドレス
  - 許可リストにないドメインの URL
  - ローカルのホームパス（C:\\Users\\<名前> など）
  - --blocklist または環境変数 PUBLIC_CHECK_BLOCKLIST で渡した禁止語
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

SELF = Path(__file__).resolve()
SKIP_DIRS = {"node_modules", "cdk.out", "dist", ".git"}
# 生成物のロックファイルはツールが作るメタデータなのでスキャン対象外とする。
SKIP_FILES = {"package-lock.json", "go.sum", "yarn.lock", "pnpm-lock.yaml"}
# サンプルとして常に使ってよい予約済みドメイン。
ALWAYS_ALLOW_DOMAINS = {"example.com", "example.org", "example.net"}
ALLOWED_EMAIL_DOMAINS = ALWAYS_ALLOW_DOMAINS
# {} や < は URL テンプレート記法・引用符なので終端として扱う。
URL_RE = re.compile(r"https?://[^\s\])}<>\"'{]+", re.I)
EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
# 12桁の連続した数字。証明書UUIDの末尾など、ハイフンでつながる識別子の一部は除外する。
ID_RE = re.compile(r"(?<![\d-])\d{12}(?![\d-])")
# ローカルのホームディレクトリのパス。
LOCAL_PATH_RES = [
    re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+"),
    re.compile(r"/home/[^/\s]+/"),
    re.compile(r"/Users/[^/\s]+/"),
]


def load_blocklist(path):
    """1行1語の禁止語リストを読む。# で始まる行と空行は無視。"""
    words = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            words.append(line)
    return words


def iter_files(root):
    for path in root.rglob("*"):
        if not path.is_file() or path.name in SKIP_FILES:
            continue
        if path.resolve() == SELF:
            continue  # このスクリプト自身は検出パターンを含むので除外
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        try:
            path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        yield path


def main():
    ap = argparse.ArgumentParser(description="公開前の個人情報チェック")
    ap.add_argument("--book", default=".", help="スキャンする本のディレクトリ（既定: カレント）")
    ap.add_argument("--blocklist", default=os.environ.get("PUBLIC_CHECK_BLOCKLIST"),
                    help="禁止語リストのファイル（1行1語、# はコメント）")
    args = ap.parse_args()
    root = Path(args.book).resolve()

    config_path = root / "public-check.json"
    allowed_numbers, allow_domains = set(), set(ALWAYS_ALLOW_DOMAINS)
    if config_path.is_file():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        allowed_numbers.update(config.get("allowed_numbers", []))
        allow_domains.update(d.lower() for d in config.get("allow_domains", []))

    blocked = []
    if args.blocklist:
        if Path(args.blocklist).is_file():
            blocked = load_blocklist(args.blocklist)
        else:
            print(f"public_check.py: error: blocklist not found: {args.blocklist}", file=sys.stderr)
            return 2
    else:
        print("WARNING: no blocklist given (--blocklist or PUBLIC_CHECK_BLOCKLIST); "
              "personal-word checks are skipped")

    findings = []
    for path in iter_files(root):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(root)
        for m in ID_RE.finditer(text):
            if m.group(0) not in allowed_numbers:
                findings.append(f"{rel}: disallowed 12-digit number {m.group(0)}")
        for m in EMAIL_RE.finditer(text):
            domain = m.group(0).rsplit("@", 1)[1].lower()
            if domain not in ALLOWED_EMAIL_DOMAINS:
                findings.append(f"{rel}: non-example email address")
        for m in URL_RE.finditer(text):
            raw = m.group(0).rstrip(".,;:!?`'")
            host = (urlsplit(raw).hostname or "").lower().rstrip(".")
            if host and not any(host == d or host.endswith("." + d) for d in allow_domains):
                findings.append(f"{rel}: non-allowlisted URL domain {host}")
        for rx in LOCAL_PATH_RES:
            for m in rx.finditer(text):
                findings.append(f"{rel}: local home path {m.group(0)}")
        lowered = text.lower()
        for word in blocked:
            if word.lower() in lowered:
                findings.append(f"{rel}: blocklisted word detected ({word})")
    if findings:
        for f in findings:
            print("FAIL: " + f)
        print(f"public_check.py: failed ({len(findings)} findings)")
        return 1
    print(f"public_check.py: passed ({sum(1 for _ in iter_files(root))} files scanned)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
