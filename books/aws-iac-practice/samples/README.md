# サンプルコード

「AWSで学ぶ Infrastructure as Code 実践入門」のサンプルです。
CloudFormation テンプレート（`cfn/`）、CDK アプリ（`cdk/`）、Go 製 Lambda（`lambda/`）で構成します。

## 前提ツール

- Node.js 20 系（`npm` / `npx`）
- Go 1.23 系
- AWS CDK CLI（`npx cdk` で使います。グローバルインストール不要）
- AWS CLI（実際にデプロイする場合のみ）
- cfn-lint（`pip install cfn-lint`。テンプレートの検証用）

依存バージョンはすべて公開から7日以上経過した安定版で完全固定してあります。

## 構成

```
samples/
  cfn/
    s3-bucket.yaml      4章: パラメータ・条件・Outputs・削除保護つき S3 バケット
    kms-key.yaml        7章: 管理者と利用者を分離したカスタマーマネージドキー
  cdk/                  TypeScript CDK アプリ（1 アプリに 3 スタック）
    bin/app.ts          エントリポイント
    lib/kms-stack.ts          データ用対称キー＋CA 署名用非対称キー
    lib/cert-issuer-stack.ts  証明書発行 Lambda・台帳・mTLS API（条件付き）
    lib/pipeline-stack.ts     Codeシリーズによるデプロイパイプライン
    test/stacks.test.ts       aws-cdk-lib/assertions によるユニットテスト
  lambda/               Go モジュール（module example.com/iac-book/lambda）
    issuer/             証明書発行 Lambda
    authorizer/         API Gateway REQUEST オーソライザー
    cmd/init-ca/        CA 証明書の初期化 CLI（管理者がローカルで1回実行）
    internal/           kmssigner / certissue
  scripts/build-lambda.sh   Lambda バイナリ（bootstrap）のビルド
```

## 動かし方

### 1. Lambda のビルド（先に実行）

CDK の `lambda.Code.fromAsset` が `lambda/dist/` を参照するため、
synth より先にビルドが必要です。

```bash
bash scripts/build-lambda.sh
# → lambda/dist/issuer/bootstrap, lambda/dist/authorizer/bootstrap
```

### 2. 依存インストールとテスト

```bash
cd lambda && go vet ./... && go test ./... && cd ..
cd cdk && npm ci && npx tsc --noEmit && npm test
cfn-lint cfn/*.yaml
```

### 3. synth（AWS に接続せずテンプレートを生成）

```bash
cd cdk
CDK_DEFAULT_ACCOUNT=111122223333 CDK_DEFAULT_REGION=ap-northeast-1 npx cdk synth
```

mTLS API を含めて synth する場合は、カスタムドメイン名と
ACM 証明書 ARN をコンテキストで渡します（両方セット時のみ作成されます）。
さらに `keyAdminRoleArn` を渡すと、KMS 両キーのキーポリシーに
そのロールが鍵管理者として登録されます（暗号操作権限は含みません）。

```bash
npx cdk synth \
  -c apiDomainName=api.example.com \
  -c apiCertificateArn=arn:aws:acm:ap-northeast-1:111122223333:certificate/00000000-0000-0000-0000-000000000000 \
  -c keyAdminRoleArn=arn:aws:iam::111122223333:role/KeyAdmin
```

## 実 AWS へのデプロイについて

本書の制作環境では実デプロイは行っていません。`cdk synth` とユニットテストで検証済みです。
実際にデプロイする場合の順序:

1. `cdk bootstrap`（初回のみ。`cdk-hnb659fds-*` ロールなどが作られます）
2. `cdk deploy KmsStack`（鍵管理者ロールを分離するなら `-c keyAdminRoleArn=...` を付ける）
3. `bash scripts/build-lambda.sh` のあと `cdk deploy CertIssuerStack`
4. `go run ./lambda/cmd/init-ca -key-id <CaSigningKeyのID>` で CA 証明書を作り、
   S3 バケットの `ca/current.pem` として配置
5. mTLS を使うなら truststore を作成して `truststore.pem` としてアップロードし、
   Route 53 などで `apiDomainName` を DomainName のエイリアス先に向ける
6. `cdk deploy PipelineStack` でパイプラインを作る（以後はパイプライン経由で変更セットをデプロイ）

なお、パイプラインが作る CodeCommit リポジトリのルートは、
この `samples/` ディレクトリの中身（`cdk/`・`lambda/`・`scripts/`・`cfn/`）を
そのままプッシュした配置を想定しています。

## 費用の目安（2026年9月時点。実装前に公式ページで再確認してください）

- KMS カスタマーマネージドキー: 1 個あたり月 1 USD（このサンプルでは 2 個）
- DynamoDB / Lambda / S3 / CodeBuild / CodePipeline V2: 少量利用なら無料枠・ごく少額
- mTLS を有効にした API Gateway: リクエスト課金のみだがカスタムドメイン名が必要

## 後片付け

`cdk destroy` でスタックを削除します。ただし以下は残る設計です。

- KMS キー（`removalPolicy: RETAIN`）: 不要なら `aws kms schedule-key-deletion` で削除予約（30日待機）
- DynamoDB テーブル・S3 バケット（RETAIN）: 中身を空にしてからコンソールで削除

## 注意

- シークレットや実在のアカウント ID は含めていません。アカウント ID の例は `111122223333`、
  ドメインは `example.com`、リージョンは `ap-northeast-1` です。
- AWS へのデプロイは実行しないでください。本リポジトリは synth とテストまでを対象としています。
