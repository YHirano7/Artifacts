# テンプレート解析 → template-map.json

組織テンプレを部品として使えるようにする対応表。テンプレごとに1回作り、本人確認を取る。スキーマは `schema/template-map.schema.json`。

## 手順

1. `python scripts/inventory.py TEMPLATE.pptx --json inv.json --thumbs thumbs/` で棚卸しする。レイアウト一覧（名前・プレースホルダの idx/型/位置）、各スライドの図形（名前・種類・位置・本文冒頭）、ノート欄が分かる。`--thumbs` のPNGは自分で見て、どのスライドが何の見本か確認する。
2. 使いたい部品（表紙・目次・区切り・箇条書き・表・組織図・タイムライン等）ごとに、次のどちらかで作る方法を決める。

## source の2方式

- `{"layout": "<レイアウト名>"}` — そのスライドレイアウトから新規作成。`slots` の `target` はプレースホルダの **idx（整数）**。text/list はそのまま流し込み、table/orgchart/timeline/chart はプレースホルダの位置を描画範囲（region）として使い、描画後にプレースホルダを消す。
- `{"sample_slide": <テンプレ内の1始まりの番号>}` — そのスライドを丸ごと複製し、中身を差し替える。`target` は図形の**名前（文字列）**。名前が無い・重複している図形は狙えないので、テンプレ側で図形名を整理する（選択ウィンドウかpython-pptx）。

見本スライドがテンプレに無ければ、テーマの色・フォント・既存図形を複製して1枚作ってよい。位置・サイズは build が region 図形のbboxを使うため、見本スライドの配置がそのまま品質になる。

## スロット型

| type | 値 | 対象 |
|---|---|---|
| `text` | 文字列（`\n`で段落分割） | プレースホルダ/図形 |
| `list` | 文字列の配列（1項目=1段落） | 同上 |
| `table` | `{"header":[..], "rows":[[..]], "col_widths":[..]?}` | 表のgraphicFrame / レイアウトのプレースホルダ |
| `orgchart` | `{"name","role"?,"children":[..]}` 最大3段 | region図形・SmartArt・プレースホルダ＋`node_prototype`（省略可） |
| `timeline` | `[{"label","period","detail"?}]` | 同上 |
| `chart` | `{"type"?, "categories":[..], "series":[{"name","values":[..]}], "number_format"?}` | グラフのgraphicFrame / プレースホルダ |

- `required: true` で必須化できる。`kind: "structural"`（表紙・目次・区切り・まとめ）のスライドは `message`/`notes` 不要、`"content"` は両方必須。
- orgchart/timeline は region（描画範囲）と node_prototype（複製元の図形）を使う。node_prototype を省略するとテーマスタイルのノード（角丸・accent1・白文字）を自動生成する。build後に region/prototype は出力から除去される。
- chart の `type` は `column|bar|line|pie|stacked_column|stacked_bar`。見本モードではテンプレのグラフ種が優先（一致しない type を書くと補完で新しいグラフを作り直す → 後述）。レイアウトモードでは必須。
- `connector_color` はテーマ色名（accent1等）。`table_style_id` は表スタイルのGUID（省略時はテンプレの既定表スタイル）。

## 対応しているテンプレの作り

| テンプレの作り | 対応状況 |
|---|---|
| 見本スライドの複製（sample_slide） | 対応。図形名を一意に付けること |
| レイアウト＋プレースホルダ（layout） | 対応。table/orgchart/timeline/chart も ph の位置を region に使う |
| グループ内の図形 | 対応。名前で再帰検索、座標はグループ変換を適用した絶対位置 |
| node_prototype がグループ（箱＋アイコン等） | 対応。子図形は等比縮小、文字はテキストを持つ子へ順に配分 |
| SmartArt（グラフィック枠）を region にする | 対応。枠と中身は消して自前のノードを描く（中身の編集はしない） |
| テンプレのグラフ（chart graphicFrame） | 対応。データだけ差し替え、書式はテンプレのまま |
| 表スタイル | `table_style_id` またはテンプレ既定（ppt/tableStyles.xml）を引き継ぐ |

## 未対応

- SmartArt の中身をそのまま編集する（データ差し替え等）は未対応。region として使い、上に自前の図形を描く。
- 埋め込みOLEオブジェクト（Excelシート等）の編集は未対応。
- 動画・音声は未対応（複製はされるが検査対象外）。
- 複数スライドマスターのテンプレは未検証。

## 準拠できないときの補完

テンプレの構造が忠実に使えない場合、build はスライドの枠（タイトル・装飾・位置）を保ったまま、未対応の中身だけを描き直す。完全な忠実さは求めず、**ずれは必ず記録して本人に報告する**のが原則。

- **枠は残す、中身だけ描き直す**。たとえば表スロットの対象がOLE埋め込み・画像・SmartArt等だった場合、そのbboxにネイティブの表を新しく描く。
- **スタイルは「同種の見本 → テーマ」の順に借りる**。表なら、テンプレ内の既存の表の明示配色（ヘッダ・帯・罫線）→ その表の `tableStyleId` → `ppt/tableStyles.xml` の既定 → テーマ色から合成、の順。グラフならテンプレの系列色を順に引き継ぎ、無ければテーマ色。
- 補完が起きるのはテンプレの能力差だけ: 表対象がOLE/画像/図形/2行未満の表、レイアウトモードで表スタイルを解決できない、orgchart/timeline の region がOLE/画像等、`node_prototype` が画像・OLE・グラフィック枠、グラフの種がテンプレと不一致、グラフ対象がグラフでない、など。
- **契約エラーは補完しない**: 不明な component/slot、必須スロット欠落、値の型違い、map にある図形名がテンプレに無い、名前重複、map が指す `node_prototype` がスライド上に無い、などは今まで通り終了コード2で失敗する。
- 補完は1件ごとに `out.pptx.build-report.json`（`--report` で変更可）に記録され、qa.py に `--build-report` で渡すと警告として一覧できる。`build.py --strict` を付けると補完が1件でもあれば終了コード2で失敗する（ブランド厳格運用・Copilot厳密モード向け）。

## その他のフィールド

- `placeholder_markers`: テンプレの見本文字（「〇〇」「サンプル」等）。QAで残存を検査する。
- `notes_instructions`: 見本スライドのノート欄に書かれた指示を写す（inventoryの出力から拾う）。ストーリー設計時の参考情報。
- `slide_size`: [幅, 高さ]（インチ）。inventoryの値を写す。

## 落とし穴

- **プレースホルダ idx は 0/1 とは限らない**。footer・日付・スライド番号の idx（10/11/12）と取り違えないこと。inventory の出力で確認する。
- 見本スライドの図形を消し忘れると出力に残る。region/prototype 図形は build が消すが、それ以外の装飾図形は残るので、見本スライドには必要なものだけ置く。
- 表の列数は deck 側で増減できるが、行の高さ・文字サイズは見本の1行目（データ行）の書式を引き継ぐ。見本の行が詰まっていれば全部詰まる。
- テンプレを修正したら map と見本スライドの整合を確認し直す。図形名の変更は map を壊す。
