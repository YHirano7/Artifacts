# book.json と Markdown の書き方

## book.json

```json
{
  "title": "書名",
  "subtitle": "副題（トップページに表示する）",
  "cover_title": "表紙に\n載せる\n短い書名",
  "mini_cover_title": "サイドバー\nの表紙",
  "footer_note": "各ページの末尾に出す注意書き（省略できる）",
  "lang": "ja",
  "updated": "2026-01-01",
  "description_file": "about.md",
  "chapters": [
    {"file": "01-introduction.md", "slug": "01-introduction", "title": "はじめに", "summary": "章の要約（トップページの章カードに出す）"}
  ]
}
```

| 項目 | 必須 | 内容 |
| --- | --- | --- |
| `title` | 必須 | 書名。ページタイトルとヘッダーに出る |
| `subtitle` | 必須 | 副題 |
| `cover_title` | 任意 | トップページの表紙に出す文字。`\n` で改行する。省略すると `title` を使う |
| `mini_cover_title` | 任意 | サイドバーの小さな表紙に出す文字。`\n` で改行する。省略すると `cover_title` を使う |
| `footer_note` | 任意 | 全ページのフッターに出す注意書き。省略すると出さない |
| `lang` | 必須 | `html` 要素の `lang` |
| `updated` | 必須 | 最終更新日 |
| `description_file` | 任意 | トップページの紹介文。既定は `about.md` |
| `chapters[].file` | 必須 | `src/chapters/` 内の Markdown ファイル名 |
| `chapters[].slug` | 必須 | 出力するファイル名（`site/chapters/<slug>.html`） |
| `chapters[].title` | 必須 | 章の題名 |
| `chapters[].summary` | 必須 | 章の要約。1〜2文 |

## Markdown の拡張記法

標準の Markdown（見出し・リスト・表・強調・リンク）に加えて、次の記法が使える。

### メッセージ

```text
:::message
補足や注意を囲む。
:::

:::message alert
強い注意（料金がかかる、データが消える、など）を囲む。
:::
```

### 折りたたみ

```text
:::details 解答
JavaScript がなくても開閉できる。確認問題の解答に使う。
:::
```

`:::details` と `:::message` は入れ子にできる。

### ファイル名つきのコードブロック

````text
```yaml:samples/cfn/bucket.yaml
Resources: ...
```
````

`言語名:ファイル名` の形で書くと、コードの上にファイル名が出る。言語名は `ts`・`js`・`bash`・`yaml`・`json`・`go`・`diff`・`html`・`toml`・`ini`・`dockerfile`・`text` が使える。それ以外はハイライトなしになる。

### 図

```text
![CloudFormationの流れ：テンプレートから変更セットで差分を確かめ、スタックに反映する](../images/ch04-stack-lifecycle.png)
```

前後を空行にして、1行に画像だけを書くと図になる。代替テキストがそのままキャプションになるので、図の要点を1文で書く。画像は `src/images/` に置き、章からは `../images/` で参照する。PNG は2倍の解像度で作る前提で、表示サイズは画像の半分になる。

### 見出し

本文の見出しは `##`（h2）と `###`（h3）を使う。章の題名は `book.json` から h1 として出るので、本文に `#` は書かない。h2・h3 は自動で目次になる。

## single 形式（1つのHTML + images/）

`python tools/build.py --format single` で、章ごとのページの代わりに `<out>/index.html` 1枚（CSS・JavaScript 埋め込み）と `<out>/images/` を出力する。追加で必要なファイル（スキルの `template/src` に入っている）:

- `src/templates/single.html`：単一ページの外枠。`{{cover}}`・`{{chapters}}`・`{{page_tocs}}`・`{{side_book}}`・`{{footer}}`・`{{inline_css}}`・`{{inline_js}}` などのプレースホルダを使う。`{{side_book}}`（ミニ表紙つきのサイドバーリンク）と `{{footer}}`（サイトフッター）は chapter.html からレンダリングした1章目のページから取り込むので、本ごとのカスタマイズがそのまま反映される
- `src/assets/book-single.css`：`book.css` のあとに結合して埋め込む追加スタイル
- `src/assets/book-single.js`：ハッシュ（`#ch-<slug>`、`#top`）で章・表紙を切り替えるスクリプト。fetch は使わないので `file://` でも動く

`site` 版と同じテンプレート（index.html・chapter.html）から章・表紙の中身を抜き出して組み立てるため、両形式で見た目は揃う。

### リンクの書き換えルール

single 形式では、出力内の `href`・`src` を次のように書き換える。

| 元の参照 | 変換後 |
| --- | --- |
| `chapters/<slug>.html`・`<slug>.html` | `#ch-<slug>`（`#見出し` つきなら `#見出し`） |
| `../index.html`・`index.html` | `#top`（`#フラグメント` つきなら `#フラグメント`） |
| `../images/x.png`・`images/x.png` | `images/x.png` |
| `#…`、`http(s)://`、`mailto:`、`tel:`、`data:` | そのまま |

それ以外の相対リンク（`../samples/x.txt` など）は `single format: unsupported relative link` でビルドが失敗する。`book.css` に相対パスの `url()` がある場合も失敗する（単一ファイルに埋め込めないため）。

## 公開前検査の設定

### public-check.json（本のディレクトリ直下、任意）

```json
{
  "allowed_numbers": ["111122223333"],
  "allow_domains": ["docs.aws.amazon.com", "aws.amazon.com", "github.com"]
}
```

- `allowed_numbers`：12桁の数字のうち、例として使ってよいもの（AWS のドキュメントで使われる架空のアカウント ID など）
- `allow_domains`：本文に書いてよい URL のドメイン。サブドメインも許可される。`example.com`・`example.org`・`example.net` は常に許可される

### 禁止語のファイル（リポジトリの外に置く）

1行に1語を書く。`#` で始まる行と空行は無視する。大文字と小文字は区別しない。

```text
# 本人の名前、ユーザー名、組織名、社内のシステム名など
```

`--blocklist <ファイル>` か、環境変数 `PUBLIC_CHECK_BLOCKLIST` で渡す。このファイルはコミットしない。

Windows の `Users` フォルダ配下や `/home/<名前>/`・`/Users/<名前>/` のようなローカルのホームパスは、禁止語のファイルがなくても検出する。
