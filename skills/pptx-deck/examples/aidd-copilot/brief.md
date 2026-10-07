# ブリーフ: AIDD導入計画（GitHub Copilot前提）

架空のSaaS企業が、導入済みのGitHub Copilotを「配っただけ」の状態から、組織として成果を出すAI駆動開発（AIDD）へ移行するための計画承認デッキ。情報の羅列ではなく、**誰が・いつまでに・何を完了させるか**を決めることに重心を置く。

## ストーリー

- purpose: 90日パイロットと、そのための体制・予算の承認を得る
- audience: CTO・開発部長・QA責任者・セキュリティ責任者
- desired_action: パイロット2チームの指名、推進チーム専任2名のアサイン、エキスパートの週2時間の確保、AIクレジット予算上限とDay90判定指標への合意
- key_message: Copilotを配るだけでは成果は増えない。最小限のコンテキストと評価で「検証できるAI開発」の仕組みを90日で作り、実測で全社展開を判断する
- 枚数上限: 20枚

## 出発点の仮説（マスター）と、リサーチによる修正

出発点の仮説は「コンテキスト基盤を作り、エキスパートの暗黙知をgrill-with-docs型のインタビューskillで形式知にし、評価基準へ組み込む」。リサーチの結果、**方向は支持されるが、盲点が3つ、仮説に無い論点が4つ**ある。デッキは仮説をそのまま主張せず、修正後の形で提示する。

| 仮説 | 支持する根拠 | 盲点（反証） | 修正 |
|---|---|---|---|
| コンテキスト基盤を作る | DORA 2025: 社内データへのAI接続（AI-accessible internal data）が効果を増幅する | ICLR 2026の評価研究: LLM生成のAGENTS.mdは成功率を下げ推論コストを20%超増やす。人手で書いても改善は約4%でコスト最大19%増 | 常時読み込む指示は最小限に絞り、追加は評価で採否を決める。詳細はskillへ分ける |
| 暗黙知をインタビューで形式知にする | AWS AI-DLC: AIが計画と質問を出し、人が重要な判断をする進め方（Mob Elaboration）。grill-with-docs: 既存資料と突き合わせて質問し、CONTEXT.md・ADRを更新する | Anthropic RCT（2026）: AIに委任する使い方では理解度テストが50%対67%で低い。暗黙知をAIへ移すほど、次のエキスパートが育たない | インタビューにジュニアを同席させ、育成の場を兼ねる |
| 評価基準に組み込む | DORA AI Capabilities Model: 小さなバッチ・強いバージョン管理が効果を増幅 | Faros AI 2025: AI高利用者はマージPR数+98%だが、レビュー時間+91%・PRサイズ+154%・バグ+9%で、会社単位の改善は有意でない。DORA 2025: AI導入は安定性の低下と相関 | 評価と同時に、PRサイズ上限とレビュー観点の統合で下流の詰まりを防ぐ |

仮説に無かった論点:

1. **費用**: 2026年6月1日からCopilotは従量課金（GitHub AI Credits）。補完以外のチャット・エージェント・code reviewがクレジットを消費し、code reviewはActions分も消費する。ライセンス費を固定費とみなす前提が崩れたため、予算上限と「マージPRあたりの消費」を指標にする
2. **セキュリティ**: 非公開データへのアクセス・外部入力（Issue等）・送信手段の3つがそろうと、プロンプトインジェクションで漏えいする（2025年のGitHub MCPの事例）。コンテキストをMCPでつなぐほど攻撃面が広がるため、ツール権限を分離する
3. **計測の罠**: METRのRCT（2025）では熟練者がAI利用で19%遅くなった一方、本人は20%速くなったと感じていた。体感アンケートでは判断せず、ベースラインを取ったうえで実測する
4. **エージェントの多様化**: GitHub Agent HQにより他社のコーディングエージェントもGitHub上で動く。Copilot専用の形式に閉じず、AGENTS.md・skillsなど共通形式で基盤を作る

## 論点の骨格（課題 → 原因 → アクション）

| 課題 | 原因 | アクション |
|---|---|---|
| AIが前提を知らない | 最小限の指示が無い／設計判断がエキスパートの頭の中 | A1 最小コンテキスト基盤 / A2 インタビューskillで暗黙知を抽出（ジュニア同席） |
| 出力を検証しきれない | 評価の基準が人依存／PRが大きくレビューが詰まる | A3 評価セットのCI組み込み / A4 PRサイズ上限とレビュー観点の統合 |
| 使い方と費用が統制されていない | 利用範囲・ツール権限が未定義／効果と費用を実測していない | A5 利用ガイド・権限分離・予算上限 / A6 実測ダッシュボード |

## 前提（会社の数値はすべて想定値）

- 会社: B2B SaaS、開発者120名、8プロダクトチーム、GitHub Enterprise Cloud
- Copilot: 全開発者にBusinessライセンス付与済み。利用は補完中心
- 利用状況（想定値）: 週1回以上の利用70%、チャット／エージェント利用30%、Copilot起点のPRを日常的に出す人10%
- パイロット候補: 請求基盤・管理画面・通知基盤・認証基盤の4チーム
- 推進体制: 推進チーム専任2名、テックリード、エキスパート6名（週2時間）、QA、セキュリティ
- 期間: 90日（13週）、Day30／60／90に判断ゲート
- 日付: 2026-10-07

## 出典（2026-10-07に確認）

- DORA 2025 レポート概要: https://cloud.google.com/blog/products/ai-machine-learning/announcing-the-2025-dora-report
- DORA AI Capabilities Model: https://cloud.google.com/blog/products/ai-machine-learning/introducing-doras-inaugural-ai-capabilities-model
- Evaluating AGENTS.md（arXiv 2602.11988 / ICLR 2026）: https://arxiv.org/abs/2602.11988
- Faros AI, The AI Productivity Paradox Report 2025: https://www.faros.ai/blog/ai-software-engineering
- METR 2025 RCT（報道）: https://techcrunch.com/2025/07/11/ai-coding-tools-may-not-speed-up-every-developer-study-shows
- Anthropic, AI assistance and coding skills: https://www.anthropic.com/research/AI-assistance-coding-skills
- AWS, AI-Driven Development Life Cycle: https://aws.amazon.com/blogs/devops/ai-driven-development-life-cycle
- GitHub Copilot is moving to usage-based billing: https://github.blog/news-insights/company-news/github-copilot-is-moving-to-usage-based-billing/
- GitHub MCP の悪用事例（Simon Willison）: https://simonwillison.net/2025/May/26/github-mcp-exploited/
- Introducing Agent HQ: https://github.blog/news-insights/company-news/welcome-home-agents/
- リポジトリのカスタム指示: https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions
- Agent Skills: https://docs.github.com/en/copilot/how-tos/use-copilot-agents/cloud-agent/create-skills
- grill-with-docs（mattpocock/skills 派生）: https://www.skills.sh/oldwinter/skills/grill-with-docs
