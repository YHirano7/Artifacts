import * as cdk from "aws-cdk-lib";
import { Match, Template } from "aws-cdk-lib/assertions";
import { KmsStack } from "../lib/kms-stack";
import { CertIssuerStack } from "../lib/cert-issuer-stack";
import { PipelineStack } from "../lib/pipeline-stack";

function kmsStack() {
  const app = new cdk.App();
  return new KmsStack(app, "KmsStack");
}

function certStack(context?: Record<string, string>) {
  const app = new cdk.App({ context });
  const kms = new KmsStack(app, "KmsStack");
  return new CertIssuerStack(app, "CertIssuerStack", {
    caSigningKey: kms.caSigningKey,
    dataKey: kms.dataKey,
  });
}

test("DataKey はローテーション有効・CaSigningKey は署名専用の非対称キー", () => {
  const t = Template.fromStack(kmsStack());
  // 対称キーは既定値なので KeySpec がテンプレートに出ない。
  t.hasResourceProperties("AWS::KMS::Key", { EnableKeyRotation: true });
  t.hasResourceProperties("AWS::KMS::Key", {
    KeySpec: "ECC_NIST_P256",
    KeyUsage: "SIGN_VERIFY",
  });
});

test("Issuer のロールは KMS へ kms:Sign と kms:GetPublicKey だけを持つ", () => {
  const t = Template.fromStack(certStack());
  t.hasResourceProperties("AWS::IAM::Policy", {
    PolicyDocument: {
      Statement: Match.arrayWith([
        Match.objectLike({
          Action: Match.arrayWith(["kms:Sign", "kms:GetPublicKey"]),
        }),
      ]),
    },
  });
  // kms:* のような広い許可がないことも確認する。
  const policies = t.findResources("AWS::IAM::Policy");
  for (const policy of Object.values(policies)) {
    const statements = policy.Properties.PolicyDocument.Statement as Array<{ Action: unknown }>;
    for (const s of statements) {
      const actions = Array.isArray(s.Action) ? s.Action : [s.Action];
      expect(actions).not.toContain("kms:*");
    }
  }
});

test("台帳が CMK 暗号化なので Issuer には DataKey の暗号化権限がある", () => {
  const t = Template.fromStack(certStack());
  // DynamoDB が呼び出し元に代わって KMS を呼ぶため、kms:Decrypt/GenerateDataKey* が必要。
  t.hasResourceProperties("AWS::IAM::Policy", {
    PolicyDocument: {
      Statement: Match.arrayWith([
        Match.objectLike({
          Action: Match.arrayWith(["kms:Decrypt", "kms:GenerateDataKey*"]),
        }),
      ]),
    },
  });
});

test("keyAdminRoleArn を渡すと各鍵のキーポリシーに管理者文が入り暗号操作は含まない", () => {
  const adminArn = "arn:aws:iam::111122223333:role/KeyAdmin";
  const app = new cdk.App({ context: { keyAdminRoleArn: adminArn } });
  const stack = new KmsStack(app, "KmsStack");
  const t = Template.fromStack(stack);
  const keys = Object.values(t.findResources("AWS::KMS::Key"));
  expect(keys.length).toBe(2);
  const forbidden = ["kms:Sign", "kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey*"];
  for (const key of keys) {
    const stmts = key.Properties.KeyPolicy.Statement as Array<{
      Principal?: { AWS?: unknown };
      Action?: unknown;
    }>;
    const adminStmt = stmts.find(
      (s) => JSON.stringify(s.Principal?.AWS).includes(adminArn)
    );
    expect(adminStmt).toBeTruthy();
    const actions = Array.isArray(adminStmt!.Action) ? adminStmt!.Action : [adminStmt!.Action];
    for (const f of forbidden) {
      expect(actions).not.toContain(f);
    }
  }
});

test("台帳テーブルは PITR 有効、トラストストアバケットは BPA とバージョニング", () => {
  const t = Template.fromStack(certStack());
  t.hasResourceProperties("AWS::DynamoDB::Table", {
    PointInTimeRecoverySpecification: { PointInTimeRecoveryEnabled: true },
  });
  t.hasResourceProperties("AWS::S3::Bucket", {
    VersioningConfiguration: { Status: "Enabled" },
    PublicAccessBlockConfiguration: {
      BlockPublicAcls: true,
      BlockPublicPolicy: true,
      IgnorePublicAcls: true,
      RestrictPublicBuckets: true,
    },
  });
});

test("コンテキスト未指定なら API Gateway リソースを作らない", () => {
  const t = Template.fromStack(certStack());
  t.resourceCountIs("AWS::ApiGateway::RestApi", 0);
  t.resourceCountIs("AWS::ApiGateway::DomainName", 0);
});

test("コンテキスト指定時は mTLS 設定の DomainName と無効化済み既定エンドポイント", () => {
  const stack = certStack({
    apiDomainName: "api.example.com",
    apiCertificateArn:
      "arn:aws:acm:ap-northeast-1:111122223333:certificate/00000000-0000-0000-0000-000000000000",
  });
  const t = Template.fromStack(stack);
  t.hasResourceProperties("AWS::ApiGateway::DomainName", {
    SecurityPolicy: "TLS_1_2",
    MutualTlsAuthentication: Match.objectLike({ TruststoreUri: Match.anyValue() }),
  });
  t.hasResourceProperties("AWS::ApiGateway::RestApi", {
    DisableExecuteApiEndpoint: true,
  });
});

test("パイプラインは V2 で手動承認ステージを持ち、ステージ順と RunOrder が正しい", () => {
  const app = new cdk.App();
  const kms = new KmsStack(app, "KmsStack");
  const stack = new PipelineStack(app, "PipelineStack", { artifactKey: kms.dataKey });
  const t = Template.fromStack(stack);
  t.hasResourceProperties("AWS::CodePipeline::Pipeline", {
    PipelineType: "V2",
    Stages: Match.arrayWith([
      Match.objectLike({
        Name: "Approve",
        Actions: Match.arrayWith([
          Match.objectLike({ ActionTypeId: Match.objectLike({ Category: "Approval" }) }),
        ]),
      }),
    ]),
  });
  const pipelines = Object.values(t.findResources("AWS::CodePipeline::Pipeline"));
  const stages = (pipelines[0].Properties as { Stages: Array<{ Name: string; Actions: Array<{ Name: string; RunOrder?: number }> }> }).Stages;
  expect(stages.map((s) => s.Name)).toEqual([
    "Source",
    "Build",
    "PrepareChangeSet",
    "Approve",
    "Deploy",
  ]);
  const deployActions = stages[4].Actions;
  const order = Object.fromEntries(deployActions.map((a) => [a.Name, a.RunOrder]));
  expect(order["Execute-KmsStack"]).toBe(1);
  expect(order["Execute-CertIssuerStack"]).toBe(2);
});
