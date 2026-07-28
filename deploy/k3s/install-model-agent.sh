#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root." >&2
  exit 1
fi

if [[ -z "${K3S_URL:-}" || -z "${K3S_TOKEN:-}" ]]; then
  echo "K3S_URL and K3S_TOKEN are required." >&2
  echo "Example: K3S_URL=https://10.0.0.10:6443 K3S_TOKEN=... $0" >&2
  exit 1
fi

curl -sfL https://get.k3s.io \
  | INSTALL_K3S_EXEC="agent --node-label workload=model" \
    K3S_URL="${K3S_URL}" \
    K3S_TOKEN="${K3S_TOKEN}" \
    sh -

systemctl is-active --quiet k3s-agent
echo "Model node joined the k3s cluster."
