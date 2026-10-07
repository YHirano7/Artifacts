---
name: static-html-book
description: Zenn の「本」に似たレイアウト（チャプター一覧・本文カード・目次の3列）の技術書・ドキュメントを、index.html 1枚と images/ だけの静的HTMLとして作るワークフロー。Zenn のサービスや zenn-cli は使わない。JavaScript が有効なら章を1つずつ切り替えて表示し、無効なら全章を縦に並べた1ページで読める。file:// で開いても HTTP で配信しても動く。章立ての設計、Markdown（:::message・:::details など Zenn 風の記法）での執筆、図解PNG、ビルド、構成・リンク検査、公開前の個人情報チェック、ブラウザでの自動確認までを扱う。「Zenn風のドキュメント」「Zenn本みたいな技術書」「HTMLの入門書・社内向け教材・ハンズオン資料を配布したい」「サーバーなしで読めるドキュメント」と言われたときに使う。
---

# Zenn本風の静的HTMLドキュメントを作る

Markdown で書いた章を、Zenn の本に似たレイアウトの HTML にする。レイアウトを寄せるだけで、Zenn のサービス・アカウント・zenn-cli・Zenn のリポジトリ構成（`books/<slug>/config.yaml` など）は使わない。

## 出力の約束

出来上がる `site/` は、次の2つだけでできている。

```text
site/
├── index.html   表紙＋全章（CSS・JavaScript を埋め込み済み）
└── images/      本文から参照している画像だけ
```

| 読者の環境 | 表示 |
| --- | --- |
| JavaScript 有効（`file://`・HTTP とも） | 表紙（`#top`）か1章だけを表示し、`#ch-<slug>` のハッシュで再読み込みなしに切り替える。戻る／進む、読んでいた位置の復元、目次の現在位置、読書進捗、コードのコピー、←／→キーが使える |
| JavaScript 無効・JS の途中で例外が起きた・印刷 | 表紙のあとに全章を縦に並べた1ページ。サイドバーと「このチャプターの目次」のリンクはページ内ジャンプになる。折りたたみは `details` で開閉する |
| 375px 幅 | 1列。JS 有効ならメニューからドロワーを開き、無効なら表紙のチャプター一覧にジャンプする |

- 外部の CDN・画像・Web フォントは使わない。別ファイルの CSS・JS も出さない
- 章どうしのリンクは `#ch-<slug>`・`#見出しID` に、画像は `images/` に書き換える。それ以外の相対リンク（`../samples/x.txt` など）はビルドエラーにする
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
- 文章は一文一義にし、主語と述語を近づける。公式ドキュメントの訳語をそのまま使わず、読者が普段使う言葉に直す。用語は初出で一言説明する

使える記法（`:::message`、`:::details`、`::::details` の入れ子、ファイル名つきコードブロック、図の幅指定とキャプション）は `references/book-format.md` にまとめてある。数式・Mermaid・リンクカードのように JavaScript や外部サービスが要る記法は使わない。図は PNG にする。

### 5. 図解を作る

図解の元になる HTML を `infographics/` に置き、PNG にする。デザインは infographic-png スキルに従う。

- 1枚で伝えるメッセージは1つ。要素名を並べるだけの図にせず、流れ・因果・対応関係を描く
- 1280×720 の HTML を、2倍の解像度（2560×1440）の PNG にする
- 外部の画像・フォント・CDN は使わない。アイコンは inline SVG か CSS で描く

```bash
CHROME=/path/to/chrome bash tools/render-infographics.sh infographics/ch01-roadmap.html
# コンテナや root で動かすとき
CHROME=/path/to/chrome CHROME_FLAGS="--no-sandbox" bash tools/render-infographics.sh ...
```

Windows の Git Bash では `bash` が WSL を指すことがあるので、`sh tools/render-infographics.sh ...` で実行する。PNG ができたら必ず自分で開き、はみ出し・重なり・文字化け・不要な折り返しがないか確かめる。

### 6. ビルドして検査する

```bash
python tools/build.py              # src/ から site/（index.html + images/）を作り直す
python tools/check.py --strict     # 構成・外部参照・リンク・HTML構造・章の型
python tools/browser_check.py      # ブラウザでの自動確認（Playwright が必要）
python tools/public_check.py --blocklist ~/.config/public-blocklist.txt
```

- `build.py` は `site/` を作り直す。HTTP サーバーで配信している間は、サーバーを止めてから実行する（Windows ではフォルダを削除できずに失敗する）
- `check.py` は、`site/` に `index.html` と `images/` の画像以外のファイルがあるとエラーにする。参照されていない画像は警告にする
- `browser_check.py` は、`file://`・HTTP・JavaScript 無効・375px 幅・JS 失敗時の5つを Chromium で操作する。使えない環境では終了コード 2 で止まるので、`references/browser-validation.md` の手順で手動確認する
- `public_check.py` は、許可していない12桁の数字（AWS アカウント ID など）、`example.com` 以外のメールアドレス、許可リストにない URL のドメイン、禁止語を検出する。設定は `references/book-format.md` の「公開前検査の設定」を参照
- 禁止語（本人の名前、組織名、ユーザー名、ローカルのパスなど）は、リポジトリの外に置いたファイルで渡す。**禁止語のリストそのものを公開リポジトリにコミットしない**。分割した文字列や難読化した形でも、名前が復元できるならコミットしない

### 7. ブラウザで確かめる

`browser_check.py` の結果（「N件中X件PASS」と表）を確かめ、FAIL を直す。そのうえで、機械では分からない見た目を自分の目で確かめる。少なくとも次の画面をスクリーンショットで見る。

- JavaScript 有効の表紙と、図・コード・表を含む章（1400px 幅）
- JavaScript 無効の全体（表紙から最後の章まで縦に並ぶこと）
- 375px 幅の章

### 8. 公開する

- `site/` はビルド済みのままコミットする。読者がビルドしなくても読めるようにするため。フォルダごと渡せば、どこでも読める
- `node_modules`、ビルドの中間生成物、ローカルの設定ファイルはコミットしない
- コミットの前に `public_check.py` をもう一度実行する

## ディレクトリ構成

```text
<本のディレクトリ>/
├── README.md               読み方・ビルド方法・注意事項
├── public-check.json       公開前検査の許可リスト（任意）
├── src/
│   ├── book.json           書名・表紙・章の一覧
│   ├── about.md            表紙の「この本について」
│   ├── chapters/*.md       章の本文
│   ├── images/*.png        図解（2560×1440）
│   ├── templates/          book.html（外枠）・cover.html（表紙）・chapter.html（章1つ分）
│   └── assets/             book.css・book.js（どちらも index.html に埋め込まれる）
├── infographics/           図解の元 HTML（1280×720）
├── samples/                サンプルコード（任意。本文からはリンクせず、パスを文字で示す）
├── tools/                  scripts/ からコピーしたビルド・検査スクリプト
└── site/                   ビルド結果（index.html + images/）。配布するのはここ
```

## 品質チェック

- [ ] 構成（読者・章立て・サンプル）を本文の前に本人に見せ、承認を得たか
- [ ] 仕様・料金・提供状況を公式ドキュメントの原文で確かめ、変わりやすい情報に確認時期を書いたか
- [ ] 各章に「この章で分かること」「まとめ」、確認問題と折りたたんだ解答、図解が1枚以上あるか
- [ ] 図解の PNG を全部自分で開いて確かめたか
- [ ] `build.py`・`check.py --strict`・`browser_check.py`・`public_check.py --blocklist ...` がすべて成功したか
- [ ] `site/` が `index.html` と `images/` だけになっているか
- [ ] JavaScript 有効・無効・375px 幅のスクリーンショットを自分の目で確かめたか
- [ ] 禁止語のリストや個人情報が、コミットするファイルに含まれていないか
