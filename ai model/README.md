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

## GitHub Actions CI/CD

`main` 브랜치에 애플리케이션 코드가 push되면 다음 작업을 자동으로 수행합니다.

1. Python 의존성 설치, 문법 검사, `/health` 테스트
2. GitHub OIDC를 통한 AWS 인증
3. ARM64 Docker 이미지를 `hearo-model` ECR 저장소에 commit SHA 태그로 push
4. `k8s/hearo-model.yaml`의 이미지 태그 변경 및 bot commit
5. Argo CD가 Git 변경을 감지하여 모델 워크로드 배포

GitHub 저장소에 다음 값을 등록해야 합니다.

- Actions secret `AWS_ROLE_ARN`: ECR push 권한이 있는 GitHub OIDC IAM Role ARN
- Actions variable `AWS_REGION`: `ap-northeast-2`
- Actions variable `AWS_ACCOUNT_ID`: `225989329853`

모델용 Kubernetes 노드에는 다음 라벨을 추가합니다.

```bash
kubectl label node <model-node-name> workload=model
```

최초 배포 전에 실제 OpenAI 키를 클러스터에 직접 등록합니다. Secret 파일은 Git에
커밋하지 않습니다.

```bash
kubectl create secret generic hearo-model-secret \
  --from-literal=openai-api-key='<OPENAI_API_KEY>' \
  --from-literal=ai-service-api-key='<AI_SERVICE_API_KEY>'
```

`AI_SERVICE_API_KEY` 인증을 사용하지 않는 환경에서는 두 번째 `--from-literal`을
생략할 수 있습니다.

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
X-AI-Service-Key: <AI_SERVICE_API_KEY를 설정한 경우>
```

```json
{
  "wardUserId": "ward-001",
  "archiveId": 1,
  "allChatText": "환자: 허리가 아파요.\n의사: 검사가 필요합니다."
}
```

`AI_SERVICE_API_KEY`가 비어 있으면 API 인증을 생략합니다. 값을 설정하면
`X-AI-Service-Key` 요청 헤더가 반드시 일치해야 합니다.
