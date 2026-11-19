
#!/usr/bin/env bash
set -euo pipefail

# 사용법:
# sudo bash infra/scripts/bootstrap.sh <관리자_공인_IP>/32
#
# 예:
# sudo bash infra/scripts/bootstrap.sh 203.0.113.10/32
#
# 주의: UFW를 실제 활성화하기 전 규칙과
# SSH 연결 유지 여부를 반드시 확인한다.

ADMIN_CIDR="${1:-}"

if [[ -z "$ADMIN_CIDR" ]]; then
  echo "사용법: sudo bash $0 <관리자_공인_IP>/32"
  exit 1
fi

if [[ "$EUID" -ne 0 ]]; then
  echo "sudo로 실행해야 합니다."
  exit 1
fi

echo "[1/4] 필수 방화벽 규칙 추가"

ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow from "$ADMIN_CIDR" to any port 6443 proto tcp

echo "[2/4] vm.max_map_count 영구 설정"

cat > /etc/sysctl.d/99-edr-opensearch.conf <<EOF
vm.max_map_count=1048576
EOF

sysctl --system >/dev/null

echo "[3/4] Swap 비활성화"

swapoff -a

# 기존 fstab 백업
cp -a /etc/fstab "/etc/fstab.edr-backup.$(date +%Y%m%d%H%M%S)"

# swap 타입의 활성 마운트 항목만 주석 처리
sed -i -E '/^[[:space:]]*[^#[:space:]].*[[:space:]]swap[[:space:]]/s/^/# EDR disabled: /' /etc/fstab

echo "[4/4] 설정 검증"

sysctl vm.max_map_count
swapon --show
ufw status verbose

echo
echo "방화벽 허용 규칙을 추가했습니다."
echo "안전 확인 전까지 UFW는 자동 활성화하지 않습니다."
echo
echo "다음 명령으로 규칙을 확인하세요:"
echo "sudo ufw show added"
echo
echo "SSH 및 k3s 네트워크 설정을 확인한 뒤"
echo "별도 작업으로 UFW 활성화를 진행하세요."
