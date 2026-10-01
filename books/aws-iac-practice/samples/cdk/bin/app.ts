#!/usr/bin/env node
// サンプルアプリのエントリポイント。3つのスタックを1つの App にまとめる。
import * as cdk from "aws-cdk-lib";
import { KmsStack } from "../lib/kms-stack";
import { CertIssuerStack } from "../lib/cert-issuer-stack";
import { PipelineStack } from "../lib/pipeline-stack";

const app = new cdk.App();

// 環境は CLI の CDK_DEFAULT_ACCOUNT / CDK_DEFAULT_REGION から取る。
const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION,
};

const kms = new KmsStack(app, "KmsStack", { env });
const issuer = new CertIssuerStack(app, "CertIssuerStack", {
  env,
  caSigningKey: kms.caSigningKey,
  dataKey: kms.dataKey,
});
issuer.addDependency(kms);
const pipeline = new PipelineStack(app, "PipelineStack", {
  env,
  artifactKey: kms.dataKey,
});
pipeline.addDependency(kms);

app.synth();
