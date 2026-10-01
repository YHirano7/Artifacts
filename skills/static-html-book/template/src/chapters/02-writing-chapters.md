## この章で分かること

- 章で使える拡張 Markdown 記法
- ビルドと検査の実行方法
- 公開前にやるべきチェック

## 章の書き方

章は `src/chapters/` に Markdown で置き、`src/book.json` の一覧に登録します。標準の Markdown に加えて、補足・折りたたみ・ファイル名つきコードブロック・図が使えます。

![本ができるまで：Markdown の章と画像を build.py がまとめて site/ に出力する](../images/ch01-book-structure.png)

:::message
1行に画像だけを書くと、キャプションつきの図になります。画像は `src/images/` に置きます。
:::

:::message alert
テンプレートのプレースホルダ（`{{...}}` の形式）はテンプレート側だけで使います。本文の HTML 出力にそのまま残るとビルドが失敗します。
:::

## 記法の例

ファイル名つきのコードブロックは、言語名のあとに `:` とファイル名を続けます。

```yaml:config/book.yaml
title: サンプルの本
lang: ja
```

長い内容は折りたたみに入れられます。メッセージとの入れ子もできます。

:::details 例：手順の詳細
1. `src/chapters/` に `.md` ファイルを追加します
2. `book.json` の `chapters` に登録します
3. ビルドして確認します

:::message
番号は `book.json` の並び順に付きます。ファイル名の番号と合わせておくと管理しやすいです。
:::
:::

表は自動で横スクロール用の枠に入ります。

| 項目 | 必須 | 内容 |
| --- | --- | --- |
| `title` | 必須 | 書名 |
| `summary` | 必須 | 章の要約 |

### ビルドと検査

```bash
python tools/build.py
python tools/check.py --strict
python tools/public_check.py
```

`check.py --strict` は、「この章で分かること」と「まとめ」の見出し、図が1枚以上あることを検査します。

## まとめ

- `:::message`、`:::details`、ファイル名つきコードブロック、図が使える
- `check.py --strict` で章の型を機械的に検査できる
- 公開前に `public_check.py` で個人情報が残っていないか調べる

## 確認問題

1. `:::details 解答` の中に `:::message` を書けますか。
2. 図に使う画像はどこに置きますか。

:::details 解答
1. 書けます。`:::details` と `:::message` は入れ子にできます。
2. `src/images/` に置き、章からは `../images/` で参照します。
:::
