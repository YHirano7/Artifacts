import * as cdk from "aws-cdk-lib";
import * as codebuild from "aws-cdk-lib/aws-codebuild";
import * as codecommit from "aws-cdk-lib/aws-codecommit";
import * as codepipeline from "aws-cdk-lib/aws-codepipeline";
import * as cpactions from "aws-cdk-lib/aws-codepipeline-actions";
import * as iam from "aws-cdk-lib/aws-iam";
import * as kms from "aws-cdk-lib/aws-kms";
import * as s3 from "aws-cdk-lib/aws-s3";
import { Construct } from "constructs";

const CHANGE_SET_NAME = "iac-book-pipeline";
// パイプラインが変更セットを作るスタック。先に鍵、次に証明書発行機能の順でデプロイする。
const DEPLOY_STACKS = ["KmsStack", "CertIssuerStack"];

export interface PipelineStackProps extends cdk.StackProps {
  // アーティファクトバケットの暗号化に使うデータキー（KmsStack から受け取る）。
  artifactKey: kms.IKey;
}

// CodeCommit → CodeBuild → 変更セット作成 → 手動承認 → 変更セット実行のパイプライン。
// パイプライン自身の更新は自動化せず、管理者が手動で cdk deploy する。
// CodeCommit リポジトリのルートは samples/ ディレクトリの中身と同じ配置
// （cdk/, lambda/, scripts/, cfn/）を想定する。
export class PipelineStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: PipelineStackProps) {
    super(scope, id, props);

    const repo = new codecommit.Repository(this, "Repo", {
      repositoryName: "iac-book-sample",
      description: "IaC book sample repository",
    });

    // パイプラインのアーティファクト置き場。KmsStack のデータキーで暗号化する。
    const artifactKey = props.artifactKey;
    const artifactBucket = new s3.Bucket(this, "ArtifactBucket", {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      encryptionKey: artifactKey,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    const buildProject = new codebuild.PipelineProject(this, "BuildProject", {
      environment: {
        buildImage: codebuild.LinuxBuildImage.AMAZON_LINUX_2023_5,
      },
      buildSpec: codebuild.BuildSpec.fromObject({
        version: "0.2",
        phases: {
          install: {
            "runtime-versions": { nodejs: "22", golang: "1.25" },
            commands: ["npm ci --prefix cdk"],
          },
          build: {
            commands: [
              "bash scripts/build-lambda.sh",
              "cd cdk && npx tsc --noEmit && npm test && npx cdk synth",
            ],
          },
        },
        artifacts: {
          files: ["cdk/cdk.out/**/*", "cdk/package.json", "cdk/package-lock.json"],
        },
      }),
    });

    // 変更セットの作成だけを行うプロジェクト。実行はパイプラインのアクションに任せる。
    const prepareProject = new codebuild.PipelineProject(this, "PrepareChangeSet", {
      environment: {
        buildImage: codebuild.LinuxBuildImage.AMAZON_LINUX_2023_5,
      },
      buildSpec: codebuild.BuildSpec.fromObject({
        version: "0.2",
        phases: {
          install: { "runtime-versions": { nodejs: "22" }, commands: ["npm ci --prefix cdk"] },
          build: {
            commands: [
              `cd cdk && npx cdk deploy --app cdk.out ${DEPLOY_STACKS.join(" ")} ` +
                `--method=prepare-change-set --change-set-name ${CHANGE_SET_NAME} ` +
                `--require-approval never`,
            ],
          },
        },
      }),
    });
    // cdk deploy がブートストラップで作られるロールを引き受けられるようにする。
    prepareProject.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["sts:AssumeRole"],
        resources: [
          `arn:${this.partition}:iam::${this.account}:role/cdk-hnb659fds-*-${this.account}-${this.region}`,
        ],
      })
    );

    const sourceOutput = new codepipeline.Artifact();
    const buildOutput = new codepipeline.Artifact();

    new codepipeline.Pipeline(this, "Pipeline", {
      pipelineType: codepipeline.PipelineType.V2,
      artifactBucket,
      stages: [
        {
          stageName: "Source",
          actions: [
            new cpactions.CodeCommitSourceAction({
              actionName: "Source",
              repository: repo,
              branch: "main",
              output: sourceOutput,
            }),
          ],
        },
        {
          stageName: "Build",
          actions: [
            new cpactions.CodeBuildAction({
              actionName: "TestAndSynth",
              project: buildProject,
              input: sourceOutput,
              outputs: [buildOutput],
            }),
          ],
        },
        {
          stageName: "PrepareChangeSet",
          actions: [
            new cpactions.CodeBuildAction({
              actionName: "PrepareChangeSet",
              project: prepareProject,
              input: buildOutput,
            }),
          ],
        },
        {
          stageName: "Approve",
          actions: [
            new cpactions.ManualApprovalAction({
              actionName: "ApproveChangeSet",
            }),
          ],
        },
        {
          stageName: "Deploy",
          // KmsStack → CertIssuerStack の順に実行する。
          actions: DEPLOY_STACKS.map(
            (stackName, i) =>
              new cpactions.CloudFormationExecuteChangeSetAction({
                actionName: `Execute-${stackName}`,
                stackName,
                changeSetName: CHANGE_SET_NAME,
                runOrder: i + 1,
              })
          ),
        },
      ],
    });
  }
}
