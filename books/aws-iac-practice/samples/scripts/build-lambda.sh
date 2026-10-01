#!/usr/bin/env bash
# Lambda 用の Go バイナリをビルドする。
# provided.al2023 カスタムランタイムではハンドラ名は常に "bootstrap"。
# arm64 向け・CGO なし・lambda.norpc（RPC コントローラを省略）で軽くする。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../lambda"

for name in issuer authorizer; do
  GOOS=linux GOARCH=arm64 CGO_ENABLED=0 \
    go build -tags lambda.norpc -trimpath -o "dist/${name}/bootstrap" "./${name}"
  echo "built lambda/dist/${name}/bootstrap"
done
