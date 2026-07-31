# Model CD: join the existing web k3s cluster

GitHub Actions tests the model, pushes an ARM64 image to ECR, and updates
`k8s/hearo-model.yaml`. The existing Argo CD on the web EC2 detects the Git change,
but deployment remains `OutOfSync` until an operator approves **Sync**.

## Topology

- Web EC2 (`172.31.11.27`): existing k3s server and Argo CD
- Model EC2: k3s agent labelled and tainted `workload=model`
- No second k3s server or Argo CD is installed on the model EC2
- The current Docker model on public port 5000 remains running during migration

After migration, the backend in the `hearo` namespace calls the model through
`http://hearo-model:5000`. Remove the model Elastic IP and public port 5000 only
after this internal call has been verified.

## 1. Security groups

Use security-group references rather than public CIDRs.

On the web EC2 security group, allow:

- TCP 6443 from the model EC2 security group

On both EC2 security groups, allow traffic from the other EC2 security group:

- UDP 8472 for Flannel VXLAN
- TCP 10250 for kubelet communication

Never expose TCP 6443, UDP 8472, or TCP 10250 to `0.0.0.0/0`.

## 2. Get the join token

Run on the web EC2:

```bash
sudo cat /var/lib/rancher/k3s/server/node-token
```

Treat this token as a secret. Do not commit or paste it into GitHub.

## 3. Verify the model EC2 IAM role

The attached `HearoModelEc2Role` must allow these ECR actions:

- `ecr:GetAuthorizationToken`
- `ecr:BatchCheckLayerAvailability`
- `ecr:GetDownloadUrlForLayer`
- `ecr:BatchGetImage`

The install script configures the kubelet ECR credential provider, which uses this
instance role and rotates the temporary ECR authorization automatically.

## 4. Join the model EC2

Clone or update this repository on the model EC2, then run:

```bash
sudo env \
  K3S_URL=https://172.31.11.27:6443 \
  K3S_TOKEN='<TOKEN_FROM_WEB_EC2>' \
  ./deploy/k3s/install-model-agent.sh
```

This does not stop the existing Docker container. On the web EC2, verify:

```bash
sudo kubectl get nodes -o wide --show-labels
```

The model node must be `Ready` and show `workload=model`.

## 5. Create the runtime secret

Create this on the web k3s server. The value is stored in Kubernetes, not Git:

```bash
sudo kubectl create namespace hearo --dry-run=client -o yaml \
  | sudo kubectl apply -f -

sudo kubectl --namespace hearo create secret generic hearo-model-secret \
  --from-literal=openai-api-key='<OPENAI_API_KEY>' \
  --from-literal=ai-service-api-key='<AI_SERVICE_API_KEY>' \
  --dry-run=client -o yaml \
  | sudo kubectl apply -f -
```

## 6. Register the model in the existing Argo CD

Run from the repository root on the web EC2:

```bash
sudo ./deploy/argocd/install.sh
sudo kubectl get application hearo-model -n argocd
```

The Application intentionally has no `syncPolicy.automated`. Approve deployment:

`Applications -> hearo-model -> Sync -> Synchronize`

Then verify on the web EC2:

```bash
sudo kubectl get pods -n hearo -o wide
sudo kubectl get svc hearo-model -n hearo
sudo kubectl run model-health-check --rm -i --restart=Never \
  --image=curlimages/curl -- \
  curl -fsS http://hearo-model:5000/health
```

Do not stop the old Docker container or release the model Elastic IP until the
health check and a real backend request both succeed.
