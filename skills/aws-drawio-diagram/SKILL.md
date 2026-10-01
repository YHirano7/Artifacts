---
name: aws-drawio-diagram
description: AWS の構成図を draw.io の XML（.drawio）で描く・直す。公式の AWS4 アイコンを使い、タイトル・凡例・番号バッジのような装飾を足さない。AWS のアーキテクチャ図・VPC 図・インフラ構成図の作成や、既存の .drawio の修正に使う。Mermaid・PlantUML・Python diagrams を指定されたときは使わない。
---

# AWS 構成図を draw.io で描く

目指すのは、どのサービスがどの境界の中にあり、リクエストとデータがどこへ流れるかが図だけで読めること。見栄えのための要素は足さない。

以下は「AI 感のない」図にするための好みと、draw.io の落とし穴だけを書いている。ここに無いことは自分で判断してよい。スタイル文字列とアイコン名は `references/styles.md`。

## 構成の解釈

- 依頼どおりに動かすのに必須のもの（NAT Gateway や外向き ALB のための Internet Gateway など）は描き、足したことを伝える
- 構成の選び方で要否が変わるもの（VPC エンドポイント、踏み台など）は足さない
- リージョンの指定が無ければ会話の言語から選ぶ（日本語なら `ap-northeast-1`、枠名は「東京リージョン（ap-northeast-1）」）

## 配置

- 利用者を上端に置き、リクエストが上から下へ流れる向きにそろえる
- 枠は AWS Cloud ＞ リージョン ＞ VPC ＞ AZ ＞ サブネットの入れ子
- グローバルなサービス（CloudFront、Route 53、CloudFront 用の WAF、Lambda@Edge、IAM）は AWS Cloud の中・リージョンの外。リージョンのサービス（S3、CloudWatch、Cognito、Lambda、DynamoDB、ECR など）はリージョンの中・VPC の外で、VPC の右に縦一列に並べ、つながる相手の高さに合わせる
- AZ は横に並べ、`ap-northeast-1a` のように正式名称で書く。各 AZ の中はパブリックサブネットを上、プライベートサブネットを下
- 各 AZ の本流のアイコン（ECS、EC2、DB など）は縦一列にしてサブネットの中央に置く。NAT Gateway のような本流外のものは AZ の外側寄りに
- アイコンは 60x60。間隔は広げすぎない（図が縮んで読めなくなる）。目安はアイコンの中心どうし横 140・縦 160、間に線のラベルが入る縦は 210、ラベル付きの横線でつなぐなら「ラベル幅（日本語 12px/字）＋40」。枠の内側の余白は 20〜30、VPC と右の列の間は 60〜80。何も無い区画が目立てば詰める
- 座標は自分で決める。draw.io CLI の `--layout` は入れ子や上下の意味を崩すので使わない

## アイコン

- AWS 公式の AWS4 アイコンを使い、四角・丸・文字だけの箱で代用しない。利用者・インターネット・社内データセンターのような AWS の外のものも汎用アイコンで描く
- サービス単位のアイコン（`resourceIcon`）にそろえる。ALB/NLB も Elastic Load Balancing のアイコンで描き、種類はラベルに書く。ECS タスク・S3 バケット・インスタンス種別・DB エンジン別のような細かいアイコンは使わない
- 例外として、NAT Gateway・Internet Gateway・VPC エンドポイントのようにサービスアイコンを持たない部品は専用のシェイプで描く（VPC アイコンで代用しない）
- アイコンを色付きの枠で囲んだり、「Compute」のような役割名の枠を作ったりしない
- アイコン名は `references/styles.md` の表から選ぶ。表に無い名前を推測すると絵が出ず色の四角になるので、書き出した PNG で確かめる。確かめられなければ推測したことを伝える

## ラベル

- アイコンのラベルは常に下（`verticalLabelPosition=bottom` を変えない）。線がかかるときはラベルではなく線を直す
- AWS のサービス名は英語の正式名称（`Amazon CloudFront`、`Application Load Balancer`）。枠名・補足・線のラベルは会話の言語
- 補足はラベルの2行目に短く（「Writer」「Reader」「us-east-1 で発行」）。図から読めることは書かない
- 線には何が流れるか（「HTTPS」「静的ファイル」「読み書き」「ログ・メトリクス」）をラベルとして付け、線の `value` に書く。別のテキストにすると線を動かしたとき取り残される
- 文字の背景は透明。線のラベルは `references/styles.md` の線のスタイルをそのまま使い、横向きの線だけ `align=center` にする

## 線

- `edgeStyle=orthogonalEdgeStyle` で直角に曲げ、必ず `rounded=0`（draw.io の一般的な例は `rounded=1` を勧めるが従わない）
- アイコンの辺の中央から出し、辺の中央へ入れる（`exitX/exitY/entryX/entryY` を明示）。1つの辺に出入りする線が2本なら 0.25 と 0.75、3本なら 0.25・0.5・0.75
- 下の辺はラベルに隠れるので、ラベルの下から出し入れする。`exitPerimeter=0`（入れる側は `entryPerimeter=0`）が無いとずれない。ずらす量はラベル1行で 24、2行で 38、3行で 52

  ```text
  exitX=0.5;exitY=1;exitDy=38;exitPerimeter=0
  entryX=0.5;entryY=1;entryDy=24;entryPerimeter=0
  ```

- アイコンやラベルの文字の上に線を通さない。線どうしを同じ経路で重ねない。交差はかまわない
- 本流は実線、ログ・メトリクス・レプリケーション・関連付けは破線で色も変える。意味は線のラベルで伝え、凡例は置かない
- 同じ役割が複数あるとき（両 AZ の ECS から Writer と Reader へ、など）は組み合わせを全部描く。CloudWatch への線だけは代表1本にまとめてよいが、ラベルで送り元か「両 AZ から」と断る
- 線が集まって全部は守れないときは、省かない（依頼にあるつながりは描く）＞ 線どうしを重ねない ＞ 辺の中央から出し入れする、の順に優先する
- 矢印は呼び出し・データの向き。WAF や ACM のような設定としての関連付けは、付ける側から CloudFront へ向ける

## よく出るサービス

- ALB/NLB は1つだけ描く。2AZ なら AZ の境目・パブリックサブネットの高さに置き（`parent` は VPC、サブネットより後に書いて前面へ）、3AZ 以上なら AZ の上の段に置く
- Internet Gateway は VPC の中、AZ の枠より上の段に、ALB と同じ x で置く。インターネットからの本流は IGW を通す（CloudFront → IGW の上の辺、IGW の下の辺 → ALB の上の辺）。外向き通信は ECS → 同じ AZ の NAT Gateway → IGW の左右の辺へ、「外向き通信」とラベルを付けた実線で引く（NAT は上の辺から出す）
- ECS on Fargate は Fargate のアイコン1つで、ラベルは「Amazon ECS（Fargate）」
- Aurora は Writer と Reader を別の AZ に置き、Writer から Reader へ「レプリケーション」の破線
- WAF は経路に挟まず、CloudFront の横に置いて破線で関連付ける。ACM も CloudFront の横、リージョンの枠の外に置き「us-east-1 で発行」と添える

## 置かないもの

タイトル、サブタイトル、凡例、番号付きのバッジ、図の横の説明パネル。

## XML の落とし穴

- `.drawio` は非圧縮の mxGraphModel をそのまま書く。`<mxGraphModel adaptiveColors="auto">` とし、`background` は付けない。`id="0"` と `id="1"`（`parent="0"`）を必ず置く
- 枠とアイコンは `vertex="1"`、線は `edge="1"` と `source`/`target`（実在する id）を持つ。子の座標は親の枠の左上からの相対。id は `alb`、`ecs-1a`、`edge-alb-to-ecs-1a` のように中身が分かる名前にする
- 線のセルは自己終了タグにせず、必ず `<mxGeometry relative="1" as="geometry" />` を子に持たせる。無いと線が描かれない
- XML コメントを書かない（`--` が入ると読み込めない）。ラベルの改行は `&#xa;`、属性値の `& < > "` はエスケープ、style に `html=1`

## 確かめる

1. XML が整形式かを確かめる。`python -c "import sys, xml.dom.minidom; xml.dom.minidom.parse(sys.argv[1])" diagram.drawio`。壊れた XML でも CLI はエラーを出さず空の PNG を作るので、PNG ができたことは成功の証拠にならない
2. draw.io desktop があれば PNG に書き出して目で見る。`-e` で XML を PNG に埋め込むので、PNG のまま再編集できる

   ```sh
   drawio -x -f png -e -b 10 -o diagram.drawio.png diagram.drawio
   ```

   PATH に無ければ、macOS は `/Applications/draw.io.app/Contents/MacOS/draw.io`、Windows は `C:\Program Files\draw.io\draw.io.exe` か `%LOCALAPPDATA%\Programs\draw.io\draw.io.exe`、画面の無い Linux は `xvfb-run -a drawio ...`
3. 線とラベルの重なり、枠からのはみ出し、アイコンの絵の欠けを直して書き出し直す。CLI が無ければ目視していないことを伝える

## 既存の図を直す

描き直さずにそのファイルを直す。`<diagram>` の中身が圧縮されていれば `drawio -x -f xml -o 展開後.drawio 元.drawio` で展開する。`<mxfile>`/`<diagram>` の外枠は残し、依頼されたページと箇所だけを変え、既存の id・座標・スタイルは保つ。このスキルの決まりと違う描き方は、依頼に無ければ直さず伝えるだけにする。

## 出力

保存先の指定が無ければ、既存の図の置き場か作業ディレクトリへ、中身が分かるケバブケースの `.drawio`（例 `cloudfront-alb-ecs-aurora.drawio`）で保存する。確認用の PNG は `<名前>.drawio.png` として隣に置く。

最後に短く伝える: ファイルの場所、目視で確かめたか、足したもの・描かなかったもの、まとめた線、自分で選んだリージョンと推測したアイコン名、迷ったところ。

## ライセンス

[sagochiko/aws-drawio-diagram-skill](https://github.com/sagochiko/aws-drawio-diagram-skill)（Apache License 2.0）を再整理したもの。元にした作品と変更点は同じディレクトリの `NOTICE` にある。
