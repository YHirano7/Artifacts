# Zenn本風の静的HTMLドキュメント（テンプレート）

Markdown で書いた章を、Zenn の本に似たレイアウトの静的HTMLにするための雛形です。

## 読む

- `site/index.html` をブラウザで開くだけで読めます。`site/` ごと Web サーバーで配信してもかまいません
- `site/` に入っているのは `index.html` と `images/` だけです。フォルダごと渡せば、どこでも読めます
- JavaScript が有効なら章を1つずつ切り替えて表示し、無効なら全章を縦に並べた1ページになります

## 書く・作り直す

```bash
pip install -r tools/requirements.txt   # 初回のみ
python tools/build.py                   # src/ から site/ を作り直す
```

- 章は `src/chapters/` に Markdown で置き、`src/book.json` に登録します
- 図解は `infographics/` に HTML で作り、`tools/render-infographics.sh` で PNG にして `src/images/` に置きます

```bash
CHROME=/path/to/chrome bash tools/render-infographics.sh infographics/ch01-book-structure.html
```

## 検査

```bash
python tools/check.py --strict     # 構成・外部参照・リンク・HTML構造・章の型
python tools/browser_check.py      # ブラウザでの自動確認（Playwright が必要）
python tools/public_check.py       # 公開前の個人情報チェック
```

禁止語（名前・ユーザー名など）をチェックする場合は、リポジトリの外に置いたファイルで渡します。

```bash
python tools/public_check.py --blocklist ~/.config/public-blocklist.txt
```

## 構成

```text
src/book.json      書名・表紙・章の一覧
src/about.md       表紙の「この本について」
src/chapters/      章の本文（Markdown）
src/images/        図解 PNG
src/templates/     book.html・cover.html・chapter.html
src/assets/        book.css・book.js（index.html に埋め込まれる）
infographics/      図解の元 HTML
tools/             ビルド・検査スクリプト
site/              ビルド結果（index.html + images/）。配布するのはここ
```
