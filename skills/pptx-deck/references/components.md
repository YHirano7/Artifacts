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
| `table` | `grid` / `striped` | `header[]`, `rows[[cell]]` | `col_widths[]`, `row_header`, `emphasis_row`, `emphasis_col` | 列 2–7、行 1–10。cellは文字列か `{text, tone?, bold?}` |
| `scorecard` | `rating` / `raci` | `columns[]`, `rows[{label,cells[]}]` | `recommend[]`（列番号）, `show_total`（ratingのみ） | 列 2–6、行 2–8 |
| `timeline` | `horizontal` / `vertical` | `events[{date,label}]` | `detail`, `emphasis`（eventごと） | 2–7 |
| `tree` | `logic` | `root`, `branches[{label,children[{label}]}]` | `headers[3]`, 葉の `tag`（4文字まで） | 枝 2–4、葉は枝ごと1–3・合計9まで |
| `hub` | `hub` / `flow` | `center` と、hubは `spokes[{label}]`、flowは `left{items[]}` `right{items[]}` | `detail`, side の `title` | spokes 3–8、flowの各side 1–4 |
| `swimlane` | `swimlane` | `lanes[]`, `steps[{lane,label}]` | `col`（stepごと）, `emphasis` | lanes 2–5、steps 2–8、列 8まで |
| `action_plan` | `rows` | `rows[{issue,action,owner,due}]` | `id`（4文字まで）, `done_when`, `labels{}`, `emphasis` | 1–6 |

`body` と `detail` は文字列または文字列配列を指定できる。`comparison` の各panel `items` は文字列配列。グラフ `type` は `column` / `bar` / `line` / `pie` / `stacked_column` / `stacked_bar`。各系列の `values` はcategoriesと同数にする。roadmapの `start` / `end` / `milestones[].at` はperiodsの1始まり番号で、範囲外はbuild error。

`emphasis` は1始まりの番号で、cards/process/matrixの該当要素、comparisonの左右panelを強調する。範囲外はbuild error。roadmapは個々のbarの `"emphasis": true` で強調する。

### 業務資料向けの部品

課題からアクションまでを図でつなぐための部品。どれもネイティブの図形・表で描くので、PowerPointでもGoogleスライドでも編集できる。

- **`table`**: ライブラリの表。テンプレに `table` があればそちらが優先されるため、テンプレの無い環境で使うか、`tone` が必要なときにスライドへ `"prefer": "library"` を付ける。cellの `tone` は `positive`（主色の淡色）/ `caution`（強調色の淡色）/ `negative`（強調色の塗り）/ `neutral`（面の色）。表スタイルには頼らず、セルごとに塗りと罫線を明示するので、Googleスライドへの取り込みでも配色が崩れない。
- **`scorecard`**: 選択肢を基準で比べる評価表（`rating`）と、役割分担のRACI（`raci`）。ratingのcellは `◎` `○` `△` `×` `-` `""` で、◎3・○2・△1・×0の合計を自動で出す。`recommend` で推奨列を強調する。raciのcellは `R` `A` `C` `I` か `A/R` のような組み合わせで、行ごとに `A` をちょうど1つにする。
- **`timeline`**: 日付つきの出来事や判断ゲート。期間の重なりを見せるならroadmap、日付の点を見せるならtimeline。
- **`tree`**: 課題を原因・要因に分解するロジックツリー。葉の `tag` にアクションID（例 `A1`）を付けると、後続の `action_plan` や `roadmap` と同じ番号で話をつなげられる。
- **`hub`**: 中心と周辺の関係。`flow` は左の入力→中心→右の出力を矢印で示す（例: コンテキスト基盤に何を入れ、誰が使うか）。
- **`swimlane`**: 担当ごとのレーンで手順の受け渡しを示す。`col` を省略するとstepの順に1列ずつ右へ進む。同じ列に置いたstepは縦の矢印でつながるので、列を詰めると箱が広くなり文字が大きくなる。
- **`action_plan`**: 課題→アクション→担当→期限→完了条件を1行で結ぶ。担当と期限は1行に収まるよう自動で縮小する。2行に分けたい長い文は `\n` で区切る。

## テンプレとライブラリの優先順位

1. template-map.json にある部品（テンプレの意匠がそのまま活きる）
2. 無ければこのライブラリ。同名ならテンプレが優先される
3. テンプレの部品では表現できない場合だけ、スライドに `"prefer": "library"` を付けてライブラリで描く。build-report の `library[].forced` に記録され、qa の報告にも出る

## 文章だけのスライドを成果物にしない

template-map のcontent部品のうち、slotがすべて `text` / `list` のもの（`bullets`・`two_column` など）は「文章だけのスライド」として扱う。既定（map の `policy.text_only` が `error`）では build がエラーで止まる。引用や規程文の全文など、どうしても文章で見せる必要がある場合だけ、スライドに `text_only_reason` を書いて残す。理由は build-report の `text_only` に記録され、qa の報告に全件出る。`message` 部品は強調用なので既定で2枚まで（`policy.max_message_slides`）。

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

全componentで `lead`（導入文）と `takeaway`（結論）を任意指定できる。詳しくは [template-mapping.md](template-mapping.md) を参照。

## 見た目とfit

- 色とフォントはテンプレートのテーマから取る。色の既定は `primary=accent1`、`highlight=accent2`、`text=tx1`、`muted=tx1`、`surface=bg2`、`line=bg1`、`background=bg1`。mapの `style.palette` / `style.fonts` で上書きできる。
- 既定サイズはheading 20pt、body 16pt、caption 13pt、number 48pt、最小11pt。mapの `style.sizes` で調整できる。
- 内容が収まらない場合は最小サイズまで縮小する。最小サイズでも収まらなければbuild errorになるため、文章を短くするかスライドを分ける。

全variantの例は `examples/component-gallery/deck.json` にある。
