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

OPENAI_SECRET_ID="hearo/model/openai-api-key"

APP_NAME="hearo-model"
CANDIDATE_NAME="hearo-model-candidate"
PREVIOUS_NAME="hearo-model-previous"

aws ecr get-login-password --region "${REGION}" \
  | docker login --username AWS --password-stdin "${REGISTRY}"

docker pull "${IMAGE}"

OPENAI_API_KEY="$(aws secretsmanager get-secret-value \
  --secret-id "${OPENAI_SECRET_ID}" \
  --query SecretString \
  --output text \
  --region "${REGION}")"

docker rm -f "${CANDIDATE_NAME}" >/dev/null 2>&1 || true

docker run -d \
  --name "${CANDIDATE_NAME}" \
  --restart no \
  -p 127.0.0.1:5001:5000 \
  -e OPENAI_API_KEY="${OPENAI_API_KEY}" \
  -e OPENAI_MODEL="gpt-4.1-mini" \
  "${IMAGE}" >/dev/null

for _ in {1..30}; do
  if curl -fsS http://127.0.0.1:5001/health >/dev/null; then
    break
  fi
  sleep 2
done

curl -fsS http://127.0.0.1:5001/health >/dev/null

curl -fsS \
  -X POST http://127.0.0.1:5001/api/final-report \
  -H 'Content-Type: application/json' \
  -d '{"wardUserId":"deploy-check","archiveId":1,"allChatText":"환자: 허리가 아파요. 의사: 무리하지 말고 통증이 심해지면 다시 방문하세요."}' \
  >/dev/null

docker rm -f "${CANDIDATE_NAME}" >/dev/null
docker rm -f "${PREVIOUS_NAME}" >/dev/null 2>&1 || true

if docker inspect "${APP_NAME}" >/dev/null 2>&1; then
  docker stop "${APP_NAME}" >/dev/null
  docker rename "${APP_NAME}" "${PREVIOUS_NAME}"
fi

if ! docker run -d \
  --name "${APP_NAME}" \
  --restart unless-stopped \
  -p 5000:5000 \
  -e OPENAI_API_KEY="${OPENAI_API_KEY}" \
  -e OPENAI_MODEL="gpt-4.1-mini" \
  "${IMAGE}" >/dev/null; then
  if docker inspect "${PREVIOUS_NAME}" >/dev/null 2>&1; then
    docker rename "${PREVIOUS_NAME}" "${APP_NAME}"
    docker start "${APP_NAME}" >/dev/null
  fi
  exit 1
fi

for _ in {1..30}; do
  if curl -fsS http://127.0.0.1:5000/health >/dev/null; then
    echo "Deployed ${IMAGE}"
    exit 0
  fi
  sleep 2
done

docker rm -f "${APP_NAME}" >/dev/null 2>&1 || true
if docker inspect "${PREVIOUS_NAME}" >/dev/null 2>&1; then
  docker rename "${PREVIOUS_NAME}" "${APP_NAME}"
  docker start "${APP_NAME}" >/dev/null
fi

echo "Deployment failed; previous container restored." >&2
exit 1
