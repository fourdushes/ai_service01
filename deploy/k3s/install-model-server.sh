#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root on the model EC2 instance." >&2
  exit 1
fi

curl -sfL https://get.k3s.io \
  | INSTALL_K3S_EXEC="server --node-label workload=model --write-kubeconfig-mode 600" sh -

kubectl wait --for=condition=Ready node --all --timeout=180s
kubectl get nodes --show-labels

echo "Standalone model k3s cluster is ready."
