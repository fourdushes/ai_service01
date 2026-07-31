#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root on the web k3s server." >&2
  exit 1
fi

if ! kubectl get namespace argocd >/dev/null 2>&1; then
  echo "Argo CD is not installed in this cluster." >&2
  echo "Install Argo CD on the web k3s server before registering the model." >&2
  exit 1
fi

kubectl apply --filename "$(dirname "$0")/hearo-model-application.yaml"

echo "Registered hearo-model in the existing Argo CD with manual sync."
