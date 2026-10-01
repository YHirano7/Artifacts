import * as cdk from "aws-cdk-lib";
import * as iam from "aws-cdk-lib/aws-iam";
import * as kms from "aws-cdk-lib/aws-kms";
import { Construct } from "constructs";

// データ暗号化用の対称キーと、CA 署名用の非対称キーをまとめて作るスタック。
export class KmsStack extends cdk.Stack {
  // 他のスタック（CertIssuerStack）から参照できるように公開する。
  public readonly dataKey: kms.Key;
  public readonly caSigningKey: kms.Key;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // コンテキスト keyAdminRoleArn を渡すと、そのロールを鍵管理者として
    // キーポリシーに登録する。未指定ならデフォルトキーポリシーのみ（アカウントへ委譲）。
    const keyAdminRoleArn = this.node.tryGetContext("keyAdminRoleArn") as string | undefined;
    const admins = keyAdminRoleArn
      ? [iam.Role.fromRoleArn(this, "KeyAdminRole", keyAdminRoleArn, { mutable: false })]
      : undefined;

    this.dataKey = new kms.Key(this, "DataKey", {
      description: "IaC book sample: data encryption key",
      enableKeyRotation: true,
      pendingWindow: cdk.Duration.days(30),
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      alias: "iac-book/data",
      admins,
    });

    this.caSigningKey = new kms.Key(this, "CaSigningKey", {
      // ECC_NIST_P256 + SIGN_VERIFY: クライアント証明書に署名するためだけに使う。
      keySpec: kms.KeySpec.ECC_NIST_P256,
      keyUsage: kms.KeyUsage.SIGN_VERIFY,
      pendingWindow: cdk.Duration.days(30),
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      alias: "iac-book/client-ca",
      admins,
    });

    new cdk.CfnOutput(this, "DataKeyArn", { value: this.dataKey.keyArn });
    new cdk.CfnOutput(this, "CaSigningKeyArn", { value: this.caSigningKey.keyArn });
  }
}
