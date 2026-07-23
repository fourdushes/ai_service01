# HearO AI Final Report API

진료 대화를 OpenAI 모델로 정리해 환자용 최종 보고서를 반환하는 Flask API입니다.

## API

- `GET /health`
- `POST /api/final-report`
- 기본 포트: `5000`

## 로컬 실행

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

## Docker 로컬 테스트

```bash
docker build -t hearo-model:v2-local .
docker run --rm \
  -p 5000:5000 \
  --env-file .env \
  hearo-model:v2-local
```

```bash
curl http://127.0.0.1:5000/health
```

## ECR 빌드 및 Push

기존 EC2가 ARM64이므로 이미지를 `linux/arm64`로 빌드합니다.

```bash
chmod +x deploy/*.sh
./deploy/build-push.sh v2-$(git rev-parse --short HEAD)
```

## Secrets Manager

EC2에는 다음 Secret이 필요합니다.

- `hearo/model/openai-api-key`

EC2 Role에 `deploy/ec2-model-policy.json`의 권한을 반영합니다. 키를 이미지, Git, EC2 파일에 저장하지 않습니다.

## 기존 EC2 교체

`deploy/deploy-ec2.sh`를 EC2에 복사한 뒤 빌드에 사용한 동일 태그를 전달합니다.

```bash
chmod +x deploy-ec2.sh
./deploy-ec2.sh v2-<commit-sha>
```

스크립트는 새 이미지를 먼저 `127.0.0.1:5001`에서 실행하고 실제 OpenAI 요약 요청까지 검증합니다. 성공하면 기존 `hearo-model` 컨테이너를 중지하고 새 이미지를 포트 `5000`에 배포합니다. 최종 health check가 실패하면 이전 컨테이너를 복구합니다.

## 백엔드 연동 형식

```http
POST /api/final-report
Content-Type: application/json
```

```json
{
  "conversation": [
    {"speaker": "patient", "text": "허리가 아파요."},
    {"speaker": "doctor", "text": "검사가 필요합니다."}
  ]
}
```
