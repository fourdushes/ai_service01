# EC2 k3s + Argo CD setup

The production deployment is intentionally manual. GitHub Actions builds and pushes
the image and updates `k8s/hearo-model.yaml`; Argo CD shows the application as
`OutOfSync` until an operator selects **Sync**.

## Deployment topology

The model service uses its own standalone EC2 and k3s cluster. It is not joined to
the backend cluster. Argo CD runs in the model cluster and manages only the model
Application. The backend can be provisioned later as a separate cluster.

## Network rules

The single-node cluster does not require k3s internode ports. Allow SSH only from
the operator IP. Do not expose TCP 6443, UDP 8472, or TCP 10250 to the internet.

## Install the cluster

On the model EC2 instance:

```bash
sudo ./deploy/k3s/install-model-server.sh
```

## Private ECR access

Attach `AmazonEC2ContainerRegistryPullOnly` or an equivalent least-privilege ECR
pull policy to the model EC2 instance role. Configure the kubelet ECR credential
provider on the model node; a static ECR Docker token expires after 12 hours and
must not be used as permanent cluster configuration.

## Create the runtime secret

On the model k3s server:

```bash
sudo kubectl create namespace hearo --dry-run=client -o yaml \
  | sudo kubectl apply -f -

sudo kubectl --namespace hearo create secret generic hearo-model-secret \
  --from-literal=openai-api-key='<OPENAI_API_KEY>' \
  --from-literal=ai-service-api-key='<AI_SERVICE_API_KEY>'
```

## Install Argo CD

Run from the repository root on the model EC2 instance:

```bash
sudo ./deploy/argocd/install.sh
```

The Application does not contain `syncPolicy.automated`. A Git change therefore
does not deploy automatically. Approve a release from the Argo CD UI with:

`Applications -> hearo-model -> Sync -> Synchronize`
