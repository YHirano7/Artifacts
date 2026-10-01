---
name: pptx-deck
description: ストーリー設計→deck.json→組織のPowerPointテンプレート(.pptx)への流し込み→QAまでを一気通貫で行うワークフロー。スライド・プレゼン資料・pptxの作成や、社内テンプレートに沿ったデッキ生成に使う。箇条書き・2段比較・表・組織図・タイムライン・グラフを部品としてテンプレ上の雛形に写す。
---

# 組織テンプレートへのプレゼン流し込み（ストーリー → deck.json → pptx → QA）

「まず話の流れを設計し、それを部品化して組織テンプレに写す」ための手順。テンプレのスタイルはそのまま活きるので、見た目の調整ではなく内容の設計に集中する。

組織テンプレが無いときは `templates/sample-org/` を使う。組織テンプレを置く場所は `templates/<org>/`（template.pptx + template-map.json を1組にする）。

## 工程

### 1. ブリーフを作る
目的・聴衆・欲しい行動・前提（数値の根拠を含む）を短いMarkdownにまとめる。例は `examples/redmine-migration/brief.md`。

### 2. ストーリーを設計する → 本人承認（1回目）
`references/story.md` の受入基準に沿ってスライド構成を起案し、**本文作成の前に本人の承認を得る**。ここでストーリーを確定させると後戻りが最小になる。

### 3. deck.json を書く
ストーリーを `schema/deck.schema.json` に沿ったJSONに落とす。要点:
- `story` ブロックは4項目すべて必須
- コンテンツスライドは `message`（主張1文＝アクションタイトル）と `notes`（話し手メモ）が必須。`title` スロットを省略すると message がタイトルになる
- `component` は template-map.json にある名前だけ使える

### 4. テンプレートを解析して template-map.json を作る（テンプレごとに1回・本人確認）
```
python scripts/inventory.py templates/<org>/template.pptx --json inv.json --thumbs thumbs/
```
レイアウト・プレースホルダ・見本スライドの図形名を棚卸しする（`--thumbs` で見た目も確認）。各コンポーネントを「レイアウトから生成」か「見本スライドを複製」か決めて `template-map.json` を書く。作り方は `references/template-mapping.md`。**初回は本人に map の内容を見せて確認する。**

### 5. ビルド
```
python scripts/build.py --deck deck.json --map template-map.json -o out.pptx
```
検証違反（不明なcomponent・必須スロット欠落・型違いなど）は終了コード2で止まる。テンプレの構造が使えない箇所は「補完」として描き直され、`out.pptx.build-report.json` に全件記録される（仕組みは `references/template-mapping.md` の「準拠できないときの補完」）。補完を認めない厳格運用では `--strict` を付ける（1件でもあれば終了コード2）。

### 6. QA → 自分で画像を見る → 本人承認（2回目）
```
python scripts/qa.py out.pptx --deck deck.json --map template-map.json --render preview/ --report report.json --build-report out.pptx.build-report.json
```
エラー0件を確認した上で、`preview/` のPNGを**必ず自分で開いて**はみ出し・重なり・見栄えを確認する。機械チェックを通っても醜いスライドはある。直す対象はdeck.json側（分量・表現）が基本で、テンプレ側は必要なときだけ。完成後に本人の承認を得る。

**本人への最終報告では補完を全件列挙する**。書式:

```
テンプレに準拠できなかった箇所（N件）:
- スライド7「移行方式」の表: 見本がExcel埋め込みのため、スライド3の表の配色で描き直しました
```

0件なら `テンプレに準拠できなかった箇所: なし` と書く。

## コマンド一覧

| コマンド | 用途 |
|---|---|
| `scripts/inventory.py TEMPLATE.pptx [--json OUT] [--thumbs DIR]` | テンプレの構造棚卸し・サムネイル生成 |
| `scripts/build.py --deck D --map M [--template T] -o OUT.pptx [--strict] [--report R]` | deck.json をテンプレに流し込んでビルド。補完は `OUT.pptx.build-report.json` に記録 |
| `scripts/qa.py OUT.pptx [--deck D --map M] [--render DIR] [--report R] [--build-report B]` | QA。エラー時は終了コード1。`--build-report` の補完は警告として出す |
| `scripts/make_sample_template.py [-o OUT.pptx]` | sample-orgテンプレの再生成 |

soffice（LibreOffice）の解決順は `SOFFICE` 環境変数 → PATH → Windows既定パス。`--render`/`--thumbs` には必要。

## テンプレに部品が無いとき

必要な種類のスライド部品がテンプレに無ければ、テンプレのデザイン（テーマ色・フォント・既存図形の複製）で見本スライドを自作してよい。PowerPointかpython-pptxで `templates/<org>/template.pptx` に1枚足して、図形に分かりやすい名前を付け、map に sample_slide コンポーネントを追加する。

## モデル別の運用

- **Opus 5.5**: ストーリーは受入基準（主張1文・見出しだけで話が通る・反論への備え・枚数範囲）だけ守らせて起案を任せる。レイアウトは map の範囲で内容に合わせて選ぶ。承認点は2回（ストーリー後・完成後）。
- **GPT-6 Luna（厳密モード）**: `references/story.md` の穴埋めフォームを全項目埋める。componentは決定表（内容の型→component）から一意に選ぶ。枚数上限を守る。deck.json はスキーマ検証が通るまで最大3回修正し、超えたら止めて報告。可能ならストーリーは Opus か本人が作り、Luna は deck.json 以降を担当する。

このモデル別運用は実測ではなく設計上の仮定。比較したいときは同じブリーフを両者で実行し、話の一貫性・テンプレ忠実度・手戻り回数を比較する。

## 品質チェック

- [ ] ストーリーの受入基準（主張1文・流れ・反論への備え・枚数）を満たし、本人承認を1回取ったか
- [ ] deck.json がスキーマ検証を通ったか（build.py が自動検証する）
- [ ] qa.py がエラー0件か
- [ ] preview PNGを全ページ自分で見て、はみ出し・重なり・文字化け・不自然な空白がないか
- [ ] 目次とセクション区切りの表題が一致しているか（qaが検査する）
- [ ] コンテンツスライドすべてにmessageとnotesがあるか
- [ ] テンプレ由来の見本文字（サンプル・〇〇等）が残っていないか（qaが検査する）
- [ ] 補完があれば build-report の内容を最終報告に全件記載したか（`テンプレに準拠できなかった箇所（N件）:` の書式）
- [ ] 完成後に本人承認を取ったか

## M365 Copilot との併用

組織がM365 Copilot（Enterprise）を持っている場合の併用方法は `references/copilot.md`。`copilot/pptx-story/` は Copilot in PowerPoint にアップロードできる可搬版（ストーリー設計だけの縮小版）。
