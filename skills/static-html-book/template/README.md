# 静的HTML本（テンプレート）

Markdown で書いた章を、配布できる静的HTMLの本にするための雛形です。

## 読む

- `site/index.html` をブラウザで開くだけで読めます
- `site/` ごと Web サーバーで配信してもよいです
- JavaScript が無効でも、通常のリンクで全章を読めます

## 書く・作り直す

```bash
pip install -r tools/requirements.txt   # 初回のみ
python tools/build.py                   # src/ から site/ を生成
```

- 章は `src/chapters/` に Markdown で置き、`src/book.json` に登録します
- 図解は `infographics/` に HTML で作り、`tools/render-infographics.sh` で PNG にして `src/images/` に置きます

```bash
CHROME=/path/to/chrome bash tools/render-infographics.sh infographics/ch01-book-structure.html
```

## 検査

```bash
python tools/check.py --strict     # リンク・HTML構造・章の型を検査
python tools/public_check.py       # 公開前の個人情報チェック
```

禁止語（名前・ユーザー名など）をチェックする場合は、リポジトリの外に置いたファイルで渡します。

```bash
python tools/public_check.py --blocklist ~/.config/public-blocklist.txt
```

## 構成

```text
src/book.json      書名・表紙・章の一覧
src/about.md       トップページの紹介文
src/chapters/      章の本文（Markdown）
src/images/        図解 PNG
src/templates/     HTML テンプレート
src/assets/        book.css・book.js
infographics/      図解の元 HTML
tools/             ビルド・検査スクリプト
site/              ビルド結果（配布するのはここ）
```
