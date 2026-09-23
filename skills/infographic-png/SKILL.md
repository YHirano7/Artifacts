---
name: infographic-png
description: 1枚もののインフォグラフィック・図解PNGをHTML+CSSで自作し、headless ChromeでPNG化して添付・投稿するワークフロー。日次/週次サマリの図解、レポート添付図、記事・仕組みの解説図に使う。標準モード(1280x720)と、Discord等の縮小表示でも読める高密度レポートモード(1280x1100-1800、2倍解像度)をサポート。外部画像・CDN・Webフォントを参照できないネットワーク制限環境でも動作する。
---

# インフォグラフィックPNG作成（HTML+CSS → headless Chrome → PNG）

「レポートに添える1枚図解」の標準手順。デザインはネイビー図解スタイル（末尾パレットをそのまま使う）。

## 2つのサイズモード

| モード | CSS | Chrome引数 | 用途 |
|---|---|---|---|
| 標準 | `width:1280px;height:720px` | `--window-size=1280,720` | 16:9のシンプルな図解 |
| 高密度レポート | `width:1280px;height:<H>px`（Hは1100〜1800で内容量に合わせる） | `--window-size=1280,<H> --force-device-scale-factor=2` | 週次コラム等の情報量の多い図解。Discord等で縮小表示されても文字が潰れないよう2倍解像度で出力する（PNG幅2560px） |

どちらのモードでも `html,body{margin:0} body{...;overflow:hidden}` を明示し、`<H>` は `--window-size` と必ず同じ値にする。

## 工程

### 1. 内容を選ぶ
- 図解にする対象は**自分の判断で最重要のものを選ぶ**。タイトルや項目の羅列は禁止
- 記事・仕組みの解説図なら、記事本文を取得して読み、仕組み・フロー・実測値・結論を1枚にまとめる
- 出典（記事タイトル・URL等）は図内または添付メッセージに明記する
- 1枚に込めるメッセージは1つ。収まらなければ2枚目を作る（高密度モードの場合は高さ内に収める）

### 2. HTML+CSSで1枚を作成
- **外部画像・外部CDN・Webフォントの参照は禁止**（ネットワーク制限環境では読み込めず崩れる）。文字はすべてHTMLテキストとして記述
- アイコンはSVG線画のみ。図形・矢印はCSS/SVGで自作
- フォントはOS標準のゴシック系を指定: `font-family: "Noto Sans JP", "Hiragino Kaku Gothic ProN", "Yu Gothic", "Meiryo", sans-serif`
- 構造は「太字中央タイトル + タイトル下罫線 + 1行リード文 + 図解エリア」が基本形

**高密度レポートモードの追加ルール:**
- 構造は3層で階層化する:
  1. 上部に凡例（色分けの意味。例: 「共通概念 / AWS / Azure / リスク / 観測点」）
  2. 主図: テーマの仕組みをパケット/リクエストの流れとして描く
  3. 下部に補足カード群: 対応表・設計原則・判断ポイント。見出し・カード・色帯で入れ子構造を表現し、色の意味は凡例と一致させる
- 文字サイズ: 本文14〜16px、見出し18〜22px、注釈12px
- 密度: 下部・右側に80px以上の空白が残る状態はNG。空白が出たら高さを縮めるか情報を足す。逆にはみ出しもNG
- 要素名の羅列だけの図は禁止（必ず流れ・因果・対応関係を描く）

### 3. headless ChromeでPNG化

Windows:
```
chrome.exe --headless=new --disable-gpu --hide-scrollbars [--force-device-scale-factor=2] --window-size=1280,<H> --screenshot=<出力PNGの絶対パス> "file:///<HTMLの絶対パス>"
```
（Chromeのパス例: `C:\devin\chrome\chrome-win64\chrome.exe`、`C:\Program Files\Google\Chrome\Application\chrome.exe`）

Linux/macOS:
```
google-chrome --headless=new --disable-gpu --hide-scrollbars [--force-device-scale-factor=2] --window-size=1280,<H> --screenshot=<出力PNGの絶対パス> "file:///<HTMLの絶対パス>"
```
（環境に応じて `chromium` / `chromium-browser` / Chrome本体パスを使う）

`--force-device-scale-factor=2` を付けると出力PNGは指定サイズの2倍（1280→2560px幅）になる。CSSレイアウトは1280px幅のままなのでHTML側の調整は不要。

### 4. 自己チェックと高さ調整ループ（省略禁止）

生成したPNGを**必ず自分で開いて確認**する。以下の症状別に直す:

| 症状 | 対処 |
|---|---|
| 下部が切れている・フッターが見えない | `<H>` を+50〜100px増やして再生成（bodyのheightとwindow-sizeの両方） |
| 下部に80px超の空白 | `<H>` を縮めるか、カードの情報量を足す |
| 要素がはみ出す・重なる | HTML側の余白・フォントサイズ・情報量を調整。class名の衝突（同じclassを別用途で再利用）も疑う |
| 文字化け | `<meta charset="utf-8">` とファイルのUTF-8保存を確認 |

高さ調整は「body height と --window-size をセットで変える」を繰り返すだけでよい。レイアウトは固定幅フローなので、高さを変えても中身は再配置されるだけ。

### 5. 出力・添付
- PNGはレポート/メッセージにファイル添付する
- HTMLも残すと後で修正・流用しやすい

## 配信: Discord webhookへ投稿する場合

画像をDiscordに表示させるには直接アップロードが必須。**外部URLをembedsのimage.urlに指定してもDiscordが取得できず画像は表示されない**。

- 投稿はPythonの `urllib` で行う（`curl -d` はシェル経由で日本語が文字化けする）。`User-Agent: Mozilla/5.0` を付与する
- `scripts/discord_upload.py` にmultipart投稿の実装がある:
  ```
  python scripts/discord_upload.py <PNGパス> "<content>"   # 環境変数 DISCORD_WEBHOOK_URL が必要
  ```
- 手動実装する場合の要点: webhook URLに `?wait=true` を付け、multipart/form-dataでPOST。フィールド `payload_json` に `{"content": "<見出し>", "attachments": [{"id": 0, "filename": "<PNGファイル名>"}]}`（**embedsは付けない**）、フィールド `files[0]` にPNGバイナリを filename 指定で入れる
- テキストは `json.dumps({"content": text}, ensure_ascii=False).encode("utf-8")` でUTF-8エンコード
- 1メッセージ上限2000文字 → 長い場合は1800文字程度ずつ複数メッセージに分割して順次POST
- URLは `<URL>` で囲むとリンクプレビューを抑制できる

## ネイビー図解パレット

```css
:root {
  --navy-darkest: #01104b;  /* 見出し帯・チップ */
  --navy-dark:    #112274;  /* タイトル背景 */
  --blue-vivid:   #011eb6;  /* 強調・矢印・番号 */
  --blue-sky:     #2692dd;  /* サブ強調 */
  --gold:         #d4b400;  /* アクセント一点使い */
  --ink-body:     #212121;  /* 本文 */
  --gray-line:    #caccd8;  /* カード枠線 */
  --gray-band:    #f4f4f4;  /* 薄い背景面 */
  --paper:        #ffffff;  /* カード面 */
  --bg:           #e8eaf2;  /* 外周の薄青グレー */
}
```
基本は「外周グレー + 白カード面」の2層構造。1枚に使う色はネイビー系+アクセント1色まで（高密度モードで色分け凡例を使う場合は凡例用の4〜5色まで許容）。

## 品質チェック

- [ ] メッセージが1枚につき1つに絞られているか
- [ ] 外部リソース参照がゼロか（img src / CDN / webfont / @import）
- [ ] 生成後にPNGを自分で開き、はみ出し・重なり・文字化け・80px超の余白がないことを確認したか
- [ ] bodyのheightと--window-sizeが一致しているか
- [ ] 出典が明記されているか（解説図の場合）
- [ ] Discord投稿時は画像をmultipart直接アップロードしているか（外部URL参照になっていないか）
