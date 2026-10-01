# 図解コンポーネント

template-map.json にない component は、このライブラリから解決する。同名がmapにもある場合はテンプレ側が優先される。ライブラリ部品は全てネイティブ図形またはpython-pptxの編集可能なチャートで、build-reportの `library` に記録される。`--strict` でもライブラリ利用は補完エラーにならない。

コンテンツスライドとして `message` と `notes` が必須。message はアクションタイトル、notes は話し手メモ。図解固有の値は `slots` に置き、variant は任意のスライド直下文字列で指定する。省略時は表の先頭variantを使う。

## 部品一覧

| component | variant | 必須slot | 任意slot | 件数制約 |
|---|---|---|---|---|
| `cards` | `header` / `outline` / `numbered` | `items[{heading,body}]` | `emphasis` | 2–6 |
| `kpi` | `tiles` / `band` | `items[{value,label}]` | `unit`, `note`（itemごと） | 1–4 |
| `process` | `chevron` / `circles` / `arrows` | `steps[{label}]` | `detail`, `emphasis` | 2–6 |
| `comparison` | `before_after` / `versus` | `left{heading,items[]}`, `right{heading,items[]}` | `emphasis` | 各items 1–6 |
| `matrix` | `matrix` | `x_axis{label,low,high}`, `y_axis{label,low,high}`, `quadrants[4]{title,items[]}` | `emphasis` | 各象限items 0–3。象限順は左上・右上・左下・右下 |
| `pyramid` | `pyramid` / `funnel` | `levels[{label}]` | `detail`（itemごと） | 2–5 |
| `cycle` | `cycle` | `steps[{label}]` | `detail`（itemごと）, `center` | 3–6 |
| `layers` | `layers` | `layers[{label,items[]}]` | — | layers 2–6、各items 1–5 |
| `roadmap` | `roadmap` | `periods[]`, `tracks[{label,bars[{start,end,label}]}]` | `milestones[{at,label}]`, bar `emphasis` | periods 2–12、tracks 1–8 |
| `message` | `banner` / `quote` | `statement` | `supports[]` | supports 0–3 |
| `checklist` | `checklist` | `items[{text}]` | itemごとの `status`（`done` / `todo` / `risk`）, `owner`, `due` | 1–8 |
| `chart` | `side` / `full` | `chart{type,categories,series}` | `points[]`（`side`のみ） | sideのpoints 1–4。`full` はpoints不可 |

`body` と `detail` は文字列または文字列配列を指定できる。`comparison` の各panel `items` は文字列配列。グラフ `type` は `column` / `bar` / `line` / `pie` / `stacked_column` / `stacked_bar`。各系列の `values` はcategoriesと同数にする。roadmapの `start` / `end` / `milestones[].at` はperiodsの1始まり番号で、範囲外はbuild error。

`emphasis` は1始まりの番号で、cards/process/matrixの該当要素、comparisonの左右panelを強調する。範囲外はbuild error。roadmapは個々のbarの `"emphasis": true` で強調する。

例:

```json
{
  "component": "cards",
  "variant": "outline",
  "message": "保守切れの構成要素を計画的に更新する",
  "slots": {
    "items": [
      {"heading": "OS", "body": "CentOS 7 / 保守終了"},
      {"heading": "DB", "body": "MySQL 5.7 / 保守終了"},
      {"heading": "アプリ", "body": "Redmine 4.2 / 更新対象外"}
    ],
    "takeaway": "段階移行で業務影響を抑える"
  },
  "notes": "対象範囲を説明する。"
}
```

## 共通slotとレイアウト

全componentで `lead`（描画域上部の導入文）と `takeaway`（下部の結論バー）を任意指定できる。指定すると本文領域を縮める。ライブラリの描画域はmapの `canvas` で設定する。未指定時は `Title Only`、次に `タイトルのみ` のlayoutを選び、タイトルplaceholder下を使う。詳しくは [template-mapping.md](template-mapping.md) を参照。

## 見た目とfit

- 色はtheme clrSchemeとmaster clrMapから解決し、通常は `schemeClr` で保持する。mapで `#RRGGBB` を明示した値だけ `srgbClr` にする。フォントはtheme major/minorのlatin・eaを明示指定する。
- palette roleの既定は `primary=accent1`、`highlight=accent2`、`text=tx1`、`muted=tx1`（淡色変換）、`surface=primary`（淡色変換）、`line=bg1`（淡色変換）、`background=bg1`。`on_primary` と `on_highlight` は背景色との相対輝度差が大きい `lt1` / `dk1` を自動選択し、mapから上書きできない。
- 文字サイズの既定はheading 16pt、body 12pt、caption 10pt、number 36pt、min 9pt。mapの `style.palette` / `style.fonts` / `style.sizes` で個別に上書きできる。`surface` を直接指定しない場合はprimary色に追従する。
- 図形は編集可能なネイティブ図形で、影なし・0.75pt線・控えめな角丸。カード・工程・タイルなど繰り返し単位は `<Component> <n>` 名のPowerPointグループにまとめる。
- fitはQAと同じ文字幅・行高の近似見積りを使い、baseサイズからminまで1pt刻みで縮小する。同種の兄弟要素は最小サイズに統一する。minでも収まらない場合はslide/component/slotの位置、必要高さと文字数の目安を含むbuild errorになる。件数上限を超えた場合はスライド分割を促す。

全variantの例は `examples/component-gallery/deck.json` にある。
