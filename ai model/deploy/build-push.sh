#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <image-tag>" >&2
  exit 1
fi

REGION="ap-northeast-2"
ACCOUNT_ID="225989329853"
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
REPOSITORY="hearo-model"
TAG="$1"
IMAGE="${REGISTRY}/${REPOSITORY}:${TAG}"

aws ecr get-login-password --region "${REGION}" \
  | docker login --username AWS --password-stdin "${REGISTRY}"

docker buildx build \
  --platform linux/arm64 \
  --tag "${IMAGE}" \
  --push \
  .

echo "Pushed ${IMAGE}"
