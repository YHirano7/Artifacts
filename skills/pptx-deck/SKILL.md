---
name: pptx-deck
description: ストーリー設計→deck.json→組織のPowerPointテンプレート(.pptx)への流し込み→QAまでを一気通貫で行うワークフロー。スライド・プレゼン資料・pptxの作成や、社内テンプレートに沿ったデッキ生成に使う。テンプレの部品と編集可能なカード・KPI・工程・比較・マトリクス・ロードマップ・グラフ等の図解ライブラリを組み合わせる。
---

# 組織テンプレートへのプレゼン流し込み（ストーリー → deck.json → pptx → QA）

「まず話の流れを設計し、それを部品化して組織テンプレに写す」ための手順。テンプレのスタイルはそのまま活きるので、見た目の調整ではなく内容の設計に集中する。

組織テンプレが無いときは `templates/sample-org/` を使う。組織テンプレを置く場所は `templates/<org>/`（template.pptx + template-map.json を1組にする）。`templates/minimal-org/` は部品ギャラリーの確認用。

## 工程

### 1. 描画エンジンを確認する
```
python scripts/engine.py detect
```
Windows では PowerShell 経由で PowerPoint COM を先に確認し、使えない場合は LibreOffice を探す。ビルド自体はレンダリング無しでも実行できるが、`--render` / `--thumbs` には利用可能なエンジンが必要。確認済みの環境では `--engine powerpoint` または `--engine libreoffice` を指定でき、明示指定時は別エンジンへフォールバックしない。

- **PowerPoint**: previewは最終表示と一致する。納品PDFは `python scripts/engine.py pdf out.pptx out.pdf --engine powerpoint` で生成する。
- **LibreOffice**: フォント置換で改行・配置が変わることがある。余白を確保し、テンプレートで使うフォントを確認した上で、完成版をPowerPointで確認してもらう。
- **none**: 構造buildとQAのみでpreviewは無い。視覚確認が済んでいないことを伝え、PowerPointでの確認を依頼する。

### 2. ブリーフを作る
目的・聴衆・欲しい行動・前提（数値の根拠を含む）を短いMarkdownにまとめる。例は `examples/redmine-migration/brief.md`。

### 3. ストーリーを設計する → 本人承認（1回目）
`references/story.md` の受入基準に沿ってスライド構成を起案し、**本文作成の前に本人の承認を得る**。ここでストーリーを確定させると後戻りが最小になる。

### 4. deck.json を書く
ストーリーを `schema/deck.schema.json` に沿ったJSONに落とす。要点:
- `story` ブロックは4項目すべて必須
- コンテンツスライドは `message`（主張1文＝アクションタイトル）と `notes`（話し手メモ）が必須。`title` スロットを省略すると message がタイトルになる
- `component` は template-map.json の名前を優先し、そこに無い名前はライブラリから選ぶ。部品・variant・slots は [components.md](references/components.md) を参照

### 5. テンプレートを解析して template-map.json を作る（テンプレごとに1回・本人確認）
```
python scripts/inventory.py templates/<org>/template.pptx --json inv.json --thumbs thumbs/ --engine auto
```
レイアウト・プレースホルダ・見本スライドの図形名に加え、テーマ色・フォント、明示RGB色、キャンバス候補を確認する。テンプレにある部品は「レイアウトから生成」か「見本スライドを複製」か決めて map に書く。テンプレに無い図解はライブラリを使う。map の canvas/style は [template-mapping.md](references/template-mapping.md)、ライブラリのスタイル解決は [components.md](references/components.md) を参照する。**初回は本人に map の内容を見せて確認する。**

### 6. ビルド
```
python scripts/build.py --deck deck.json --map template-map.json -o out.pptx --strict
```
検証違反（不明なcomponent・必須スロット欠落・型違いなど）は終了コード2で止まる。テンプレの構造が使えない箇所は「補完」として描き直され、`out.pptx.build-report.json` に全件記録される（仕組みは `references/template-mapping.md` の「準拠できないときの補完」）。ライブラリ部品は補完ではなく、`--strict` でも失敗理由にならない。

### 7. QA → 自分で画像を見る → 本人承認（2回目）
```
python scripts/qa.py out.pptx --deck deck.json --map template-map.json --render preview/ --report report.json --build-report out.pptx.build-report.json --engine auto
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
| `scripts/engine.py detect|render|pdf ...` | PowerPoint / LibreOffice の判定・レンダリング |
| `scripts/inventory.py TEMPLATE.pptx [--json OUT] [--thumbs DIR] [--engine E]` | テンプレの構造・テーマ棚卸し、サムネイル生成 |
| `scripts/build.py --deck D --map M [--template T] -o OUT.pptx [--strict] [--report R]` | deck.json をテンプレに流し込んでビルド。補完は `OUT.pptx.build-report.json` に記録 |
| `scripts/qa.py OUT.pptx [--deck D --map M] [--render DIR] [--report R] [--build-report B] [--engine E]` | QA。エラー時は終了コード1。`--build-report` の補完は警告として出す |
| `scripts/make_sample_template.py [--variant sample|minimal] [-o OUT.pptx]` | sample-org または minimal-org テンプレの生成 |

レンダリングの選択は `--engine auto|powerpoint|libreoffice`。LibreOffice の実行ファイルは `SOFFICE` 環境変数 → PATH → Windows既定パスの順で解決する。

## テンプレに部品が無いとき

テンプレに図解部品が無い場合はまず [components.md](references/components.md) のライブラリから選ぶ。テンプレ独自の意匠が必要な場合だけ、テーマ色・フォント・既存図形を使った見本スライドを作り、図形名を付けて map に追加する。完成例は `examples/component-gallery/`。

## モデル別の運用

- **Opus 5.5**: ストーリーは受入基準（主張1文・見出しだけで話が通る・反論への備え・枚数範囲）だけ守らせて起案を任せる。レイアウトは map の範囲で内容に合わせて選ぶ。承認点は2回（ストーリー後・完成後）。
- **GPT-6 Luna（厳密モード）**: `references/story.md` の穴埋めフォームを全項目埋める。component は内容の型から選び、map とライブラリの優先順位は変えない。枚数上限を守る。deck.json はスキーマ検証が通るまで最大3回修正し、超えたら止めて報告。可能ならストーリーは Opus か本人が作り、Luna は deck.json 以降を担当する。

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
