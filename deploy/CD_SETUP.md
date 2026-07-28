# EC2 k3s + Argo CD setup

The production deployment is intentionally manual. GitHub Actions builds and pushes
the image and updates `k8s/hearo-model.yaml`; Argo CD shows the application as
`OutOfSync` until an operator selects **Sync**.

## Required network rules

Allow these ports only between the backend and model EC2 security groups:

- TCP 6443 from the model node to the backend node
- UDP 8472 between all k3s nodes
- TCP 10250 between all k3s nodes

Do not expose UDP 8472 to the public internet.

## Install the cluster

On the backend EC2 instance:

```bash
sudo ./deploy/k3s/install-server.sh
```

On the model EC2 instance, using the backend private IP and printed server token:

```bash
sudo env \
  K3S_URL=https://<BACKEND_PRIVATE_IP>:6443 \
  K3S_TOKEN='<K3S_SERVER_TOKEN>' \
  ./deploy/k3s/install-model-agent.sh
```

## Private ECR access

Attach `AmazonEC2ContainerRegistryPullOnly` or an equivalent least-privilege ECR
pull policy to the model EC2 instance role. Configure the kubelet ECR credential
provider on the model node; a static ECR Docker token expires after 12 hours and
must not be used as permanent cluster configuration.

## Create the runtime secret

On the backend k3s server:

```bash
sudo kubectl create namespace hearo --dry-run=client -o yaml \
  | sudo kubectl apply -f -

sudo kubectl --namespace hearo create secret generic hearo-model-secret \
  --from-literal=openai-api-key='<OPENAI_API_KEY>' \
  --from-literal=ai-service-api-key='<AI_SERVICE_API_KEY>'
```

## Install Argo CD

Run from the repository root on the backend EC2 instance:

```bash
sudo ./deploy/argocd/install.sh
```

The Application does not contain `syncPolicy.automated`. A Git change therefore
does not deploy automatically. Approve a release from the Argo CD UI with:

`Applications -> hearo-model -> Sync -> Synchronize`
