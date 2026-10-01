# AWSで学ぶ Infrastructure as Code 実践入門

CloudFormation と AWS CDK の基本から、KMS・mTLS・Code シリーズを使った実務のサンプルまでを扱う、日本語の学習用ドキュメントです。

## 読み方

`site/index.html` をブラウザで開いてください。サーバーは不要です。

- JavaScript が無効でも、通常のリンクで章を行き来できます。
- JavaScript が有効な場合は、ページを再読み込みせずに章を切り替えられます（HTTP で配信したとき）。現在位置の目次ハイライト、コードのコピー、左右キーでの章移動も使えます。

## ディレクトリ構成

| パス | 内容 |
| --- | --- |
| `site/` | ビルド済みの HTML（読むのはここ） |
| `src/` | 本文の Markdown、テンプレート、CSS・JavaScript、図解の PNG |
| `infographics/` | 図解の元になる HTML（1280×720） |
| `samples/` | CloudFormation、CDK（TypeScript）、Lambda（Go）のサンプル。詳しくは `samples/README.md` |
| `tools/` | ビルドと検査のスクリプト |

## ビルドと検査

Python 3.10 以上と、`markdown`・`pygments` パッケージが必要です。

```bash
pip install markdown pygments
python tools/build.py            # src/ から site/ を生成
python tools/check.py --strict   # リンク切れ・画像・目次の検査
python tools/public_check.py     # 公開前の検査（実在のアカウント ID やメールアドレスなど）
PUBLIC_CHECK_BLOCKLIST=/path/to/blocklist.txt python tools/public_check.py  # 名前などの禁止語も検査する
```

`public_check.py` に渡す禁止語のリスト（1行1語）は、リポジトリの外に置きます。許可する12桁の数字と URL のドメインは `public-check.json` に書きます。

図解を作り直すときは、Chrome と Pillow を用意して次を実行します。

```bash
CHROME=/path/to/chrome bash tools/render-infographics.sh infographics/ch07-key-policy.html
```

## 注意

- サンプルに出てくるアカウント ID（`111122223333`）やドメイン（`example.com`）は、すべて説明用の架空の値です。
- サンプルを実際の AWS アカウントにデプロイすると料金がかかります。料金やサービスの提供状況は変わることがあるので、公式の情報を確認してください（本文の記述は2026年9月時点）。
