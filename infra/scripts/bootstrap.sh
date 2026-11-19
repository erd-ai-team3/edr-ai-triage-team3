#!/usr/bin/env bash
# Day 2 / 인프라 1단계: Ubuntu 서버 초기 설정 및 단일 노드 k3s 설치.
# 사용: sudo bash infra/scripts/bootstrap.sh <내 공인 IPv4> <서버 공인 IPv4>
set -Eeuo pipefail

usage() {
    echo "사용법: sudo bash $0 <노트북 공인 IPv4> <서버 공인 IPv4>" >&2
    exit 2
}

[[ $# -eq 2 ]] || usage
admin_ip=$1
server_ip=$2

if [[ $EUID -ne 0 ]]; then
    echo '오류: root 권한으로 실행하세요 (sudo).' >&2
    exit 1
fi

for command_name in python3 systemctl curl; do
    command -v "$command_name" >/dev/null 2>&1 || {
        echo "오류: 필수 명령을 찾을 수 없습니다: $command_name" >&2
        exit 1
    }
done

validate_public_ipv4() {
    python3 - "$1" <<'PY'
import ipaddress
import sys

try:
    address = ipaddress.IPv4Address(sys.argv[1])
except ipaddress.AddressValueError:
    raise SystemExit(1)
raise SystemExit(0 if address.is_global else 1)
PY
}

validate_public_ipv4 "$admin_ip" || { echo '오류: 관리자 주소는 공인 IPv4여야 합니다.' >&2; exit 2; }
validate_public_ipv4 "$server_ip" || { echo '오류: 서버 주소는 공인 IPv4여야 합니다.' >&2; exit 2; }

echo '== 1/4 방화벽 (UFW)'
if ! command -v ufw >/dev/null 2>&1; then
    command -v apt-get >/dev/null 2>&1 || { echo '오류: ufw와 apt-get을 찾을 수 없습니다.' >&2; exit 1; }
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y ufw
fi

# SSH 규칙을 먼저 추가해 UFW 활성화 후 원격 접속이 끊길 위험을 줄입니다.
ufw allow 22/tcp comment 'ssh'
ufw allow 80/tcp comment 'http ingress'
ufw allow 443/tcp comment 'https ingress'

# 전체 공개 6443 규칙이 남아 있으면 제거하고, 관리자 IP 허용만 남깁니다.
while IFS= read -r rule_number; do
    [[ -n $rule_number ]] && ufw --force delete "$rule_number"
done < <(ufw status numbered | awk '/6443\/tcp/ && /ALLOW IN/ && /Anywhere/ { if (match($0, /^\[[[:space:]]*[0-9]+\]/)) { number = substr($0, RSTART, RLENGTH); gsub(/[^0-9]/, "", number); print number } }' | sort -rn)
ufw allow from "$admin_ip" to any port 6443 proto tcp comment 'kubernetes api admin only'

# k3s 기본 Pod/Service 대역에서의 내부 트래픽을 허용합니다.
ufw allow from 10.42.0.0/16 to any comment 'k3s pods'
ufw allow from 10.43.0.0/16 to any comment 'k3s services'
ufw default deny incoming
ufw default allow outgoing
ufw --force enable
ufw status verbose

echo '== 2/4 커널 설정: vm.max_map_count'
sysctl_file=/etc/sysctl.d/99-edr-ai-triage.conf
printf '%s\n' 'vm.max_map_count=262144' > "$sysctl_file"
sysctl --load "$sysctl_file"
echo "현재 값: $(sysctl -n vm.max_map_count)"

echo '== 3/4 swap 끄기'
swapoff -a
if awk '$0 !~ /^[[:space:]]*#/ && NF >= 3 && $3 == "swap" { found=1 } END { exit !found }' /etc/fstab; then
    backup="/etc/fstab.edr-ai-triage.$(date -u +%Y%m%dT%H%M%SZ).bak"
    cp -p /etc/fstab "$backup"
    temp_file=$(mktemp /etc/fstab.XXXXXX)
    trap 'rm -f "$temp_file"' EXIT
    awk '$0 !~ /^[[:space:]]*#/ && NF >= 3 && $3 == "swap" { print "# disabled by edr-ai-triage bootstrap: " $0; next } { print }' /etc/fstab > "$temp_file"
    cat "$temp_file" > /etc/fstab
    rm -f "$temp_file"
    trap - EXIT
    echo "fstab의 swap 항목을 비활성화했습니다. 백업: $backup"
fi
if [[ -n $(swapon --show --noheadings) ]]; then
    echo '오류: swap이 아직 활성화되어 있습니다.' >&2
    exit 1
fi
echo 'swap=off'

echo '== 4/4 k3s 설치'
if command -v k3s >/dev/null 2>&1; then
    echo "k3s가 이미 설치돼 있어 설치를 건너뜁니다: $(k3s --version | head -n 1)"
else
    # --tls-san을 지정해 노트북 kubectl이 서버 공인 IP로 접속할 때 인증서 검증이 되게 합니다.
    curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server --tls-san ${server_ip}" sh -
fi

echo '== 확인'
k3s kubectl get nodes
echo
echo '노트북에서 kubectl을 쓰려면 /etc/rancher/k3s/k3s.yaml을 안전하게 복사하고,'
echo "server 주소를 https://${server_ip}:6443으로 바꾸세요."
echo "가비아 보안 그룹에서도 6443/tcp를 ${admin_ip}/32로 제한하세요."
