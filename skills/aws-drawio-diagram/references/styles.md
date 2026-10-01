# スタイル文字列とアイコン名

draw.io の `style=` にそのまま入れる。色は AWS 公式のアイコンパッケージ（2026年7月31日版）に合わせてある。

## 入れ子の枠

AWS Cloud・リージョン・VPC・AZ は塗らない。サブネットだけ枠線なしで塗り、面の色でパブリックとプライベートを見分ける。AZ の名前は左上（中央だと上から入る線が名前を貫く）。サブネットのアイコンは `group_security_group` を使う（`group_public_subnet` と `group_private_subnet` は draw.io に無く空白になる）。

| 枠 | style |
|---|---|
| AWS Cloud | `html=1;whiteSpace=wrap;fontSize=12;shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_aws_cloud_alt;strokeColor=#000000;fillColor=none;verticalAlign=top;align=left;spacingLeft=30;fontColor=#000000;container=1;collapsible=0;recursiveResize=0` |
| リージョン | `html=1;whiteSpace=wrap;fontSize=12;shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_region;strokeColor=#00A4A6;fillColor=none;verticalAlign=top;align=left;spacingLeft=30;fontColor=#000000;dashed=1;container=1;collapsible=0;recursiveResize=0` |
| VPC | `html=1;whiteSpace=wrap;fontSize=12;shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_vpc2;strokeColor=#8C4FFF;fillColor=none;verticalAlign=top;align=left;spacingLeft=30;fontColor=#000000;container=1;collapsible=0;recursiveResize=0` |
| AZ | `fillColor=none;strokeColor=#00A4A6;dashed=1;verticalAlign=top;align=left;spacingLeft=10;fontSize=12;fontColor=#000000;whiteSpace=wrap;html=1;container=1;collapsible=0;recursiveResize=0` |
| パブリックサブネット | `html=1;whiteSpace=wrap;fontSize=12;shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_security_group;grStroke=0;strokeColor=#7AA116;fillColor=#F2F6E8;verticalAlign=top;align=left;spacingLeft=30;fontColor=#248814;container=1;collapsible=0;recursiveResize=0` |
| プライベートサブネット | `html=1;whiteSpace=wrap;fontSize=12;shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_security_group;grStroke=0;strokeColor=#00A4A6;fillColor=#E6F6F7;verticalAlign=top;align=left;spacingLeft=30;fontColor=#147EBA;container=1;collapsible=0;recursiveResize=0` |

## アイコン

`{CATEGORY_COLOR}` と `{shape_name}` を下の表から埋める。

サービスアイコン:

```text
fontColor=#16191F;fillColor={CATEGORY_COLOR};strokeColor=#ffffff;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=12;aspect=fixed;shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.{shape_name}
```

専用シェイプ（サービスアイコンを持たない部品と AWS の外のもの）:

```text
fontColor=#16191F;fillColor={CATEGORY_COLOR};strokeColor=none;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=12;aspect=fixed;shape=mxgraph.aws4.{shape_name}
```

### サービスアイコン

draw.io のパレットは ELB を Compute、API Gateway を App Integration の色にも載せているが、下の色を使う。

| カテゴリ | `{CATEGORY_COLOR}` | サービスと `{shape_name}` |
|---|---|---|
| Compute | `#ED7100` | EC2 `ec2`、Lambda `lambda` |
| Containers | `#ED7100` | Fargate `fargate`、ECS `ecs`、EKS `eks`、ECR `ecr` |
| Database | `#C925D1` | Aurora `aurora`、RDS `rds`、DynamoDB `dynamodb`、ElastiCache `elasticache` |
| Networking | `#8C4FFF` | CloudFront `cloudfront`、ELB（ALB/NLB）`elastic_load_balancing`、API Gateway `api_gateway`、Route 53 `route_53`、Transit Gateway `transit_gateway`、Direct Connect `direct_connect`、Site-to-Site VPN `site_to_site_vpn`、Global Accelerator `global_accelerator` |
| Analytics | `#8C4FFF` | Kinesis Data Streams `kinesis_data_streams`、Data Firehose `kinesis_data_firehose`、Glue `glue`、Athena `athena`、QuickSight `quicksight`、Redshift `redshift`、EMR `emr`、Lake Formation `lake_formation` |
| AI | `#01A88D` | Bedrock `bedrock`、Bedrock AgentCore `bedrock_agentcore` |
| IoT | `#7AA116` | IoT Core `iot_core` |
| App Integration | `#E7157B` | SQS `sqs`、SNS `sns`、EventBridge `eventbridge`、Step Functions `step_functions` |
| Storage | `#7AA116` | S3 `s3`、EFS `elastic_file_system` |
| Management | `#E7157B` | CloudWatch `cloudwatch_2`、CloudTrail `cloudtrail`、Systems Manager `systems_manager` |
| Security | `#DD344C` | WAF `waf`、ACM `certificate_manager_3`、Cognito `cognito`、IAM `identity_and_access_management`、KMS `key_management_service`、Secrets Manager `secrets_manager` |

### 専用シェイプ

| もの | `{CATEGORY_COLOR}` | `{shape_name}` |
|---|---|---|
| NAT Gateway | `#8C4FFF` | `nat_gateway` |
| Internet Gateway | `#8C4FFF` | `internet_gateway` |
| VPC エンドポイント | `#8C4FFF` | `endpoints` |
| Site-to-Site VPN の接続 | `#8C4FFF` | `vpn_connection` |
| カスタマーゲートウェイ | `#8C4FFF` | `customer_gateway` |
| Transit Gateway のアタッチメント | `#8C4FFF` | `transit_gateway_attachment` |
| 利用者（複数 / 1人） | `#242F3E` | `users` / `user` |
| インターネット | `#242F3E` | `internet`（絵が3種類あるのでこれに固定） |
| 社内データセンター | `#242F3E` | `corporate_data_center` |
| クライアント PC / モバイル端末 | `#242F3E` | `client` / `mobile_client` |
| オンプレミスのサーバー | `#242F3E` | `traditional_server` |
| 工場 / センサー | `#7AA116` | `factory` / `sensor` |

## 線

本流:

```text
edgeStyle=orthogonalEdgeStyle;html=1;endArrow=block;endFill=1;strokeColor=#545B64;rounded=0;labelBackgroundColor=none;verticalAlign=bottom;align=left;spacingLeft=6
```

補助の流れ（ログ、メトリクス、レプリケーション、関連付け）:

```text
edgeStyle=orthogonalEdgeStyle;html=1;endArrow=block;endFill=1;strokeColor=#E7157B;rounded=0;dashed=1;labelBackgroundColor=none;verticalAlign=bottom;align=left;spacingLeft=6
```

横向きの線（始点と終点がほぼ同じ高さ）は `align=left;spacingLeft=6` を `align=center` に置き換え、ラベルを線の上の中央に出す。縦向きの線は置き換えない（文字が線に重なる）。
