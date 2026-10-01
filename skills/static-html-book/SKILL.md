---
name: static-html-book
description: Zennの「本」に似たレイアウトの技術書を、外部サービスに依存しない静的HTMLとして作るワークフロー。章立ての設計、Markdown執筆、各章の図解PNG、ビルド、リンク・構造の検査、公開前の個人情報チェック、ブラウザでの確認までを扱う。file:// で直接開いても、HTTPで配信しても、JavaScriptが無効でも読める。学習用ドキュメント・社内向け入門書・ハンズオン教材を、公開リポジトリやアーティファクトとして配布したいときに使う。
---

# 静的HTMLの技術書を作る（Zenn本風レイアウト）

Markdown で書いた章を、Zenn の本に似た3列レイアウトの HTML にするための手順。Zenn のサービスやアカウントは使わない。出来上がった `site/` をそのまま配布でき、サーバーなしでも読める。

## 仕上がりの要件

- 出力は2つの形式から選べる
  - `site`：章ごとのHTML。`site/index.html` を `file://` で開いても、HTTP で配信しても読める
  - `single`：1つの `index.html`（CSS・JavaScript 埋め込み）と `images/` だけ。フォルダ1つで配布できる。JavaScript が有効なら `file://` でも再読み込みなしで章を切り替えられ、無効なら全章が1ページに縦に並ぶ
- JavaScript が無効でも、通常のリンクで全章を行き来できる。目次・確認問題の解答・モバイルのメニューは `details` と checkbox で開閉する
- JavaScript が有効なら、ページを再読み込みせずに章を切り替える（`site` は HTTP 配信時のみ、`file://` では通常のリンク遷移に戻る。`single` は `file://` でも使える）。目次の現在位置ハイライト、読書進捗、コードのコピー、←／→キーでの章移動も使える
- 外部の CDN・画像・Web フォントは使わない。リンクはすべて相対パスにする
- 公開リポジトリに置けるよう、個人情報・実在のアカウント ID・内輪の表現を含めない

## 工程

### 1. 雛形を用意する

```bash
cp -r <このスキル>/template <本のディレクトリ>
mkdir -p <本のディレクトリ>/tools
cp <このスキル>/scripts/* <本のディレクトリ>/tools/
pip install -r <このスキル>/scripts/requirements.txt
```

スクリプトも本のディレクトリにコピーしておく。こうしておくと、配布先でもスキルなしでビルドし直せる。以降のコマンドは本のディレクトリで実行する。

### 2. 構成を決める → 本人の承認を得る

本文を書く前に、次の3点を決めて本人に見せる。

- **読者**：何を知っていて、何を知らないか。「中堅エンジニアだが、この分野は初級〜中級」のように、経験と分野の知識を分けて書く
- **章立て**：基礎（概念・道具）→ 実践（題材を最後まで作り切る）→ 運用・次の一歩、の順にする。実践の章は、読者が業務で出会う題材を選ぶ
- **サンプル**：実践の章で使うコード・設定。どこまで検証するか（構文チェック、ユニットテスト、実環境へのデプロイ）も決めておく

決まったら `src/book.json` を書く。項目は `references/book-format.md` を参照。

### 3. 事実を確かめてから書く

- 仕様・上限値・料金・提供状況は、公式ドキュメントの原文（英語版）で確かめる。機械翻訳の日本語版だけを根拠にしない
- 料金や提供状況のように変わりやすい情報には、確認した時期を書き、読者に最新情報の確認を促す
- サンプルのコードは、本文に載せる前に実際に動かす（lint・テスト・ビルド）。動かせない部分は、そのことを本文に書く

### 4. 章を書く

各章は `references/chapter-guide.md` の型で書く。要点は次のとおり。

- 冒頭に「この章で分かること」、末尾に「まとめ」と確認問題2〜3問（解答は `:::details` で折りたたむ）
- 図解を1枚以上入れる
- 文章は一文一義にし、主語と述語を近づける。公式ドキュメントの訳語をそのまま使わず、読者が普段使う言葉に直す（例：「プロビジョニングする」→「作る」、「〜することができます」→「〜できます」）。用語は初出で一言説明する

Markdown の拡張記法（`:::message`、`:::details`、ファイル名つきのコードブロック、図）は `references/book-format.md` にまとめてある。

### 5. 図解を作る

図解の元になる HTML を `infographics/` に置き、PNG にする。デザインは html-infographic（または infographic-png）スキルに従う。

- 1枚で伝えるメッセージは1つ。要素名を並べるだけの図にせず、流れ・因果・対応関係を描く
- 1280×720 の HTML を、2倍の解像度（2560×1440）の PNG にする
- 外部の画像・フォント・CDN は使わない。アイコンは inline SVG か CSS で描く

```bash
CHROME=/path/to/chrome bash tools/render-infographics.sh infographics/ch01-roadmap.html
```

Windows の Git Bash では `bash` が WSL を指すことがあるので、`sh tools/render-infographics.sh ...` で実行する。

PNG ができたら必ず自分で開き、はみ出し・重なり・文字化けがないか確かめる。

### 6. ビルドして検査する

```bash
python tools/build.py                 # src/ から site/ を生成する
python tools/build.py --format single # src/ から single/（1HTML + images/）を生成する
python tools/check.py --strict        # リンク切れ・画像・HTML構造・章の型を検査する
python tools/check.py --strict --site single  # single 版も同じように検査できる
python tools/public_check.py          # 公開前の検査
```

- `build.py` は出力ディレクトリを作り直す。`site/` を HTTP サーバーで配信している間は、サーバーを止めてから実行する（Windows ではフォルダを削除できずに失敗する）
- `single` 形式では、章や画像へのリンクは `#アンカー` と `images/` に書き換えられる。それ以外の相対リンク（`../samples/x.txt` など）はエラーになる
- `public_check.py` は、許可していない12桁の数字（AWS アカウント ID など）、`example.com` 以外のメールアドレス、許可リストにない URL のドメイン、禁止語を検出する。設定は `references/book-format.md` の「公開前検査の設定」を参照
- 禁止語（本人の名前、組織名、ユーザー名、ローカルのパスなど）は、リポジトリの外に置いたファイルで渡す。**禁止語のリストそのものを公開リポジトリにコミットしない**。分割した文字列や難読化した形でも、名前が復元できるならコミットしない

```bash
python tools/public_check.py --blocklist ~/.config/public-blocklist.txt
```

### 7. ブラウザで確かめる

`references/browser-validation.md` のチェックリストに沿って確かめる。少なくとも次の4つの環境で確認する。

- HTTP 配信 + JavaScript 有効
- `file://` + JavaScript 有効
- JavaScript 無効
- 375px 幅

章リンクの連打や、アンカーを挟んだ「戻る／進む」のように、遷移が重なる操作も試す。

### 8. 公開する

- `site/`（または `single/`）はビルド済みのままコミットする。読者がビルドしなくても読めるようにするため。`single/` は `index.html` と `images/` だけなのでフォルダごと配布しやすい
- `node_modules`、ビルドの中間生成物、ローカルの設定ファイルはコミットしない
- コミットの前に `public_check.py` をもう一度実行する

## ディレクトリ構成

```text
<本のディレクトリ>/
├── README.md               読み方・ビルド方法・注意事項
├── public-check.json       公開前検査の許可リスト（任意）
├── src/
│   ├── book.json           書名・章の一覧
│   ├── about.md            トップページの紹介文
│   ├── chapters/*.md       章の本文
│   ├── images/*.png        図解（2560×1440）
│   ├── templates/          index.html・chapter.html・single.html
│   └── assets/             book.css・book.js・book-single.css・book-single.js
├── infographics/           図解の元 HTML（1280×720）
├── samples/                サンプルコード（任意）
├── tools/                  scripts/ からコピーしたビルド・検査スクリプト
├── site/                   ビルド結果・章ごとのHTML版（配布するのはここ）
└── single/                 ビルド結果・1つのHTML版（index.html + images/）
```

## 品質チェック

- [ ] 構成（読者・章立て・サンプル）を本文の前に本人に見せ、承認を得たか
- [ ] 仕様・料金・提供状況を公式ドキュメントの原文で確かめ、変わりやすい情報に確認時期を書いたか
- [ ] 各章に「この章で分かること」「まとめ」、確認問題と折りたたんだ解答、図解が1枚以上あるか
- [ ] 図解の PNG を全部自分で開いて確かめたか
- [ ] `build.py`・`check.py --strict`・`public_check.py --blocklist ...` がすべて成功したか（`single` を配布するなら `build.py --format single` と `check.py --strict --site single` も）
- [ ] ブラウザで、HTTP・`file://`・JavaScript 無効・375px 幅の4つを確かめたか（`single` ならハッシュ遷移・戻る／進む・表紙表示も）
- [ ] 禁止語のリストや個人情報が、コミットするファイルに含まれていないか
