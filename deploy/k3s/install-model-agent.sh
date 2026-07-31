#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root on the model EC2 instance." >&2
  exit 1
fi

if [[ -z "${K3S_URL:-}" || -z "${K3S_TOKEN:-}" ]]; then
  echo "K3S_URL and K3S_TOKEN are required." >&2
  echo "Example: sudo env K3S_URL=https://172.31.11.27:6443 K3S_TOKEN=... $0" >&2
  exit 1
fi

if [[ "${K3S_URL}" != https://*:* ]]; then
  echo "K3S_URL must look like https://<web-private-ip>:6443." >&2
  exit 1
fi

if systemctl is-active --quiet k3s; then
  echo "A standalone k3s server is already running on this instance." >&2
  echo "Do not join it as an agent until the standalone server is removed." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"${SCRIPT_DIR}/install-ecr-credential-provider.sh"

curl -sfL https://get.k3s.io \
  | INSTALL_K3S_EXEC="agent --node-label workload=model --node-taint workload=model:NoSchedule" \
    K3S_URL="${K3S_URL}" \
    K3S_TOKEN="${K3S_TOKEN}" \
    sh -

systemctl is-active --quiet k3s-agent
echo "Model node joined the web k3s cluster as a dedicated worker."
echo "The existing Docker model container was not stopped."
