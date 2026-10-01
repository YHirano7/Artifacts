import * as path from "path";
import * as cdk from "aws-cdk-lib";
import * as acm from "aws-cdk-lib/aws-certificatemanager";
import * as apigateway from "aws-cdk-lib/aws-apigateway";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as iam from "aws-cdk-lib/aws-iam";
import * as kms from "aws-cdk-lib/aws-kms";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as s3 from "aws-cdk-lib/aws-s3";
import { Construct } from "constructs";

export interface CertIssuerStackProps extends cdk.StackProps {
  caSigningKey: kms.IKey;
  dataKey: kms.IKey;
}

// クライアント証明書を発行する Lambda と、必要に応じて mTLS 対応 API を作るスタック。
export class CertIssuerStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: CertIssuerStackProps) {
    super(scope, id, props);
    const { caSigningKey, dataKey } = props;

    // 発行した証明書の台帳。失効チェックはこのテーブルを見て判定する。
    const table = new dynamodb.Table(this, "IssuedCertificates", {
      partitionKey: { name: "serial", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      encryption: dynamodb.TableEncryption.CUSTOMER_MANAGED,
      encryptionKey: dataKey,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // API Gateway がトラストストアを読むためのバケット。
    // API Gateway が truststore を読み取るので、鍵ポリシーの追加設定が不要な
    // SSE-S3 で暗号化する。バージョニングは truststore 更新時のため公式推奨。
    const truststoreBucket = new s3.Bucket(this, "TruststoreBucket", {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      versioned: true,
      enforceSSL: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // Go 製 Lambda は scripts/build-lambda.sh で dist/ にビルド済みの前提。
    const issuer = new lambda.Function(this, "IssuerFunction", {
      runtime: lambda.Runtime.PROVIDED_AL2023,
      architecture: lambda.Architecture.ARM_64,
      handler: "bootstrap",
      code: lambda.Code.fromAsset(path.join(__dirname, "../../lambda/dist/issuer")),
      environment: {
        CA_KEY_ID: caSigningKey.keyId,
        CA_CERT_BUCKET: truststoreBucket.bucketName,
        CA_CERT_KEY: "ca/current.pem",
        TABLE_NAME: table.tableName,
        MAX_VALIDITY_DAYS: "90",
        DEFAULT_VALIDITY_DAYS: "30",
      },
    });

    // 最小権限: 署名と公開鍵取得、台帳への登録、CA 証明書の読み取りだけ許可する。
    caSigningKey.grant(issuer, "kms:Sign", "kms:GetPublicKey");
    table.grant(issuer, "dynamodb:PutItem");
    // 台帳はカスタマーマネージドキーで暗号化しているので、
    // DynamoDB が呼び出し元に代わって KMS を使うための権限も必要。
    dataKey.grantEncryptDecrypt(issuer);
    issuer.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["s3:GetObject"],
        resources: [truststoreBucket.arnForObjects("ca/current.pem")],
      })
    );

    new cdk.CfnOutput(this, "IssuerFunctionName", { value: issuer.functionName });

    // mTLS API はコンテキストでドメイン名と証明書 ARN の両方が
    // 与えられたときだけ作る。未指定なら API Gateway リソースは 0 個。
    const domainName = this.node.tryGetContext("apiDomainName") as string | undefined;
    const certificateArn = this.node.tryGetContext("apiCertificateArn") as string | undefined;
    if (domainName && certificateArn) {
      this.createMtlsApi(domainName, certificateArn, table, truststoreBucket, props.dataKey);
    }
  }

  private createMtlsApi(
    domainName: string,
    certificateArn: string,
    table: dynamodb.Table,
    truststoreBucket: s3.Bucket,
    dataKey: kms.IKey
  ): void {
    const authorizer = this.createAuthorizer(table, dataKey);
    const api = new apigateway.RestApi(this, "MtlsApi", {
      // 既定の execute-api エンドポイントを残すと mTLS を迂回できるので無効化する。
      disableExecuteApiEndpoint: true,
      deployOptions: { stageName: "v1" },
    });

    api.root.addResource("hello").addMethod(
      "GET",
      new apigateway.MockIntegration({
        integrationResponses: [
          {
            statusCode: "200",
            responseTemplates: { "application/json": '{"message":"hello"}' },
          },
        ],
        requestTemplates: { "application/json": '{"statusCode": 200}' },
        passthroughBehavior: apigateway.PassthroughBehavior.NEVER,
      }),
      {
        authorizationType: apigateway.AuthorizationType.CUSTOM,
        authorizer,
        methodResponses: [{ statusCode: "200" }],
      }
    );

    // リージョン別カスタムドメイン名＋S3 のトラストストアで mTLS を有効化する。
    const domain = new apigateway.DomainName(this, "MtlsDomainName", {
      domainName,
      certificate: acm.Certificate.fromCertificateArn(this, "ApiCertificate", certificateArn),
      endpointType: apigateway.EndpointType.REGIONAL,
      securityPolicy: apigateway.SecurityPolicy.TLS_1_2,
      mtls: {
        bucket: truststoreBucket,
        key: "truststore.pem",
      },
    });

    new apigateway.BasePathMapping(this, "MtlsBasePathMapping", {
      domainName: domain,
      restApi: api,
    });
  }

  private createAuthorizer(table: dynamodb.Table, dataKey: kms.IKey): apigateway.RequestAuthorizer {
    const authorizerFn = new lambda.Function(this, "AuthorizerFunction", {
      runtime: lambda.Runtime.PROVIDED_AL2023,
      architecture: lambda.Architecture.ARM_64,
      handler: "bootstrap",
      code: lambda.Code.fromAsset(path.join(__dirname, "../../lambda/dist/authorizer")),
      environment: { TABLE_NAME: table.tableName },
    });
    // オーソライザーは台帳の参照だけできればよい。読み取りなので Decrypt のみ。
    table.grant(authorizerFn, "dynamodb:GetItem");
    dataKey.grantDecrypt(authorizerFn);

    return new apigateway.RequestAuthorizer(this, "RequestAuthorizer", {
      handler: authorizerFn,
      identitySources: [apigateway.IdentitySource.context("resourcePath")],
      // 証明書の失効は即時反映したいので結果をキャッシュしない。
      resultsCacheTtl: cdk.Duration.seconds(0),
    });
  }
}
