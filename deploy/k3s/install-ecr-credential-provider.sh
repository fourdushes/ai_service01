#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root." >&2
  exit 1
fi

PROVIDER_VERSION="${ECR_CREDENTIAL_PROVIDER_VERSION:-v1.36.1}"
MACHINE_ARCH="$(uname -m)"

case "${MACHINE_ARCH}" in
  aarch64|arm64)
    PROVIDER_ARCH="arm64"
    ;;
  x86_64|amd64)
    PROVIDER_ARCH="amd64"
    ;;
  *)
    echo "Unsupported architecture: ${MACHINE_ARCH}" >&2
    exit 1
    ;;
esac

PROVIDER_DIR="/var/lib/rancher/credentialprovider"
PROVIDER_BIN_DIR="${PROVIDER_DIR}/bin"
PROVIDER_CONFIG="${PROVIDER_DIR}/config.yaml"
DOWNLOAD_URL="https://storage.googleapis.com/k8s-staging-provider-aws/releases/${PROVIDER_VERSION}/linux/${PROVIDER_ARCH}/ecr-credential-provider-linux-${PROVIDER_ARCH}"

install -d -m 0755 "${PROVIDER_BIN_DIR}"
curl -fL "${DOWNLOAD_URL}" -o "${PROVIDER_BIN_DIR}/ecr-credential-provider"
chmod 0755 "${PROVIDER_BIN_DIR}/ecr-credential-provider"

cat >"${PROVIDER_CONFIG}" <<'EOF'
apiVersion: kubelet.config.k8s.io/v1
kind: CredentialProviderConfig
providers:
  - name: ecr-credential-provider
    matchImages:
      - "*.dkr.ecr.*.amazonaws.com"
      - "*.dkr.ecr.*.amazonaws.com.cn"
      - "*.dkr.ecr-fips.*.amazonaws.com"
    defaultCacheDuration: "12h"
    apiVersion: credentialprovider.kubelet.k8s.io/v1
EOF

chmod 0644 "${PROVIDER_CONFIG}"
echo "Installed ECR credential provider ${PROVIDER_VERSION} for ${PROVIDER_ARCH}."
