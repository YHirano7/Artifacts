# book.json・Markdown・テンプレートの書き方

## book.json

```json
{
  "title": "書名",
  "subtitle": "副題（表紙に表示する）",
  "cover_title": "表紙に\n載せる\n短い書名",
  "mini_cover_title": "サイドバー\nの表紙",
  "cover_sub": "表紙の下端に出す一言（省略できる）",
  "footer_note": "ページの末尾に出す注意書き（省略できる）",
  "lang": "ja",
  "updated": "2026-01-01",
  "description_file": "about.md",
  "chapters": [
    {"file": "01-introduction.md", "slug": "01-introduction", "title": "はじめに", "summary": "章の要約（表紙のチャプター一覧に出す）"}
  ]
}
```

| 項目 | 必須 | 内容 |
| --- | --- | --- |
| `title` | 必須 | 書名。ページタイトル・トップバー・表紙に出る |
| `subtitle` | 必須 | 副題 |
| `cover_title` | 任意 | 表紙の絵に出す文字。`\n` で改行する。省略すると `title` を使う |
| `mini_cover_title` | 任意 | サイドバーの小さな表紙に出す文字。2〜3行・各5文字程度に収める。省略すると `cover_title` を使う |
| `cover_sub` | 任意 | 表紙の絵の下端に出す一言。省略すると出さない |
| `footer_note` | 任意 | フッターに出す注意書き。省略すると出さない |
| `lang` | 任意 | `html` 要素の `lang`。既定は `ja` |
| `updated` | 必須 | 最終更新日 |
| `description_file` | 任意 | 表紙の「この本について」。既定は `about.md` |
| `chapters[].file` | 必須 | `src/chapters/` 内の Markdown ファイル名 |
| `chapters[].slug` | 必須 | 章のアンカー名（`#ch-<slug>`）。英数字・`-`・`_` だけ。重複はエラー |
| `chapters[].title` | 必須 | 章の題名 |
| `chapters[].summary` | 必須 | 章の要約。1〜2文 |

## Markdown の記法

標準の Markdown（見出し・リスト・表・強調・リンク・引用）に加えて、Zenn に似た次の記法が使える。

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

入れ子にするときは、Zenn と同じく外側のコロンを増やしてよい（同じ数のコロンどうしでも入れ子にできる）。

```text
::::details 手順の詳細
:::message
内側のメッセージ
:::
::::
```

コードブロックの中の `:::` はブロックの終わりとみなさない。

### ファイル名つきのコードブロック

````text
```yaml:samples/cfn/bucket.yaml
Resources: ...
```
````

`言語名:ファイル名` の形で書くと、コードの上にファイル名が出る。主な言語名は `ts`・`tsx`・`js`・`py`・`go`・`java`・`kotlin`・`rust`・`sql`・`bash`・`console`・`powershell`・`yaml`・`json`・`toml`・`ini`・`hcl`・`dockerfile`・`html`・`css`・`xml`・`diff`・`text`。知らない言語名はハイライトなしになる。

### 図

```text
![CloudFormationの流れ：テンプレートから変更セットで差分を確かめ、スタックに反映する](../images/ch04-stack-lifecycle.png)
```

- 前後を空行にして、1行に画像だけを書くと図になる
- 代替テキストがキャプションになるので、図の要点を1文で書く
- 画像は `src/images/` に置き、章からは `../images/` で参照する。出力では `images/` に書き換わる
- 表示サイズは画像の半分（2倍の解像度で作る前提）。幅を変えたいときは Zenn と同じく `=幅x` を付ける：`![代替テキスト](../images/x.png =560x)`
- 画像の直後の行を `*キャプション*` にすると、代替テキストとは別のキャプションを付けられる
- 本文から参照した画像だけが `site/images/` にコピーされる

### 見出し

本文の見出しは `##`（h2）と `###`（h3）を使う。章の題名は `book.json` から h1 として出るので、本文に `#` は書かない。h2・h3 には `s<章番号>-<連番>` の id が付き、自動で目次になる。

### リンク

| 書き方 | 出力 |
| --- | --- |
| `[第1章](01-introduction.html)` | `#ch-01-introduction` |
| `[節](01-introduction.html#s1-2)` | `#s1-2` |
| `[トップ](../index.html)` | `#top` |
| `[図](../images/x.png)` | `images/x.png` |
| `https://…`・`mailto:`・`#…` | そのまま |

それ以外の相対リンク（`../samples/x.txt` など）は `unsupported relative link` でビルドが失敗する。出力は `index.html` と `images/` だけなので、サンプルコードは本文にコードブロックで載せ、リポジトリ内のパスは文字で示す。

### 使わない記法

数式（KaTeX）、Mermaid、リンクカード、埋め込み（YouTube・ツイートなど）、脚注は対応しない。JavaScript や外部サービスがないと表示できないため。図は PNG にし、URL は通常のリンクにする。

## テンプレート

`src/templates/` の3つのファイルを組み合わせて `index.html` を作る。`{{name}}` がプレースホルダで、知らない名前を書くとビルドが失敗する。

| ファイル | 役割 | 主なプレースホルダ |
| --- | --- | --- |
| `book.html` | ページの外枠（head・トップバー・サイドバー・本文領域・右の目次・フッター） | `lang`・`book_title`・`book_description_plain`・`mini_cover_title`・`chapter_list`・`cover`・`chapters`・`page_tocs`・`updated`・`footer_note_html`・`inline_css`・`inline_js` |
| `cover.html` | 表紙（`#top` の中身） | `book_title`・`cover_title`・`cover_sub_html`・`book_subtitle`・`book_description`・`chapter_count`・`total_hours`・`updated`・`first_chapter_href`・`chapter_cards` |
| `chapter.html` | 章1つ分の `<section class="chapter" id="ch-…">` | `chapter_slug`・`chapter_title`・`chapter_summary`・`chapter_no`・`chapter_no_padded`・`reading_minutes`・`toc`・`body`・`pager`・`book_title` |

`book.js` は `.cover`・`.chapter`・`.toc-card[data-chapter-toc]`・`.chapter-list`・`.menu-btn`・`#scrim`・`#topbar-chapter` を前提にしている。クラス名を変えるときは両方を直す。

`src/assets/book.css` と `book.js` は `index.html` に埋め込まれる。`book.css` の `url()` は `data:` URI だけ、`@import` は使えない。

## 旧形式からの移行

以前のバージョン（章ごとの HTML と `assets/` を出す site 形式、`--format single`）で作った本は、次の手順で移行する。

1. `tools/` をこのスキルの `scripts/` で上書きする
2. `src/templates/` を、このスキルの `template/src/templates/`（`book.html`・`cover.html`・`chapter.html`）で置き換える。旧 `index.html`・`single.html` は削除する
3. `src/assets/` を `book.css`・`book.js` だけにする（`book-single.*` は削除する）。独自に変えた色などは新しい `book.css` に移す
4. 表紙のテンプレートに直接書いていた一言は `book.json` の `cover_sub` に移す
5. `python tools/build.py && python tools/check.py --strict` を実行し、古い `site/` の中身（`chapters/`・`assets/`）が消えたことを確かめる

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
