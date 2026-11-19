# 런북: 우리가 겪은 장애와 찾는 법

**프로젝트:** EDR AI Triage Lab — Team 3  
**환경:** Windows 11 / Docker Compose / Ubuntu 24.04 / k3s / OpenSearch / PostgreSQL  
**정리 범위:** 인프라 0단계 ~ 2단계  
**작성:** 🔍 기록 담당

> 이 문서는 실제 실습 중 발생한 문제와 해결 과정을 기록한 것이다. 새벽 당번이 장애를 확인하고 복구할 수 있도록 증상, 명령어, 출력, 원인, 조치 순서로 작성한다.
>
> 별도로 출제한 장애가 아닌 경우에는 '실습 중 실제 발생'로 표시한다. 복구 시간과 팀원 간 진단 후 나눔은 확인된 내용만 기록한다.

---

## 공통 1차 확인

### Kubernetes 리소스 상태

```bash
sudo k3s kubectl -n soc get pods,svc,ingress,pvc,jobs
sudo k3s kubectl -n soc get events --sort-by=.lastTimestamp | tail -20
```

### 노드 및 워크로드 상태

```bash
sudo k3s kubectl get nodes
sudo k3s kubectl -n soc get deploy,sts,pvc,svc
sudo k3s kubectl -n soc get pods -o wide
```

### Pod 장애 진단

```bash
sudo k3s kubectl -n soc describe pod <POD_NAME>
sudo k3s kubectl -n soc logs <POD_NAME> --tail=100
```

### 로컬 Docker 상태

Windows PowerShell:

```powershell
docker compose ps
docker compose logs --tail=50 opensearch
docker compose logs --tail=50 postgres
```

---

# 0단계. 로컬 Docker Compose 환경 구축

## 구축 내용

Windows 개발 PC에서 EDR AI Triage Lab의 기본 인프라를 Docker Compose로 실행했다.

| 구성 요소 | 이미지 및 버전 | 포트 |
|---|---|---|
| OpenSearch | 2.19.1 | 9200 |
| OpenSearch Dashboards | 2.19.1 | 5601 |
| PostgreSQL | 16 | 5432 |

OpenSearch는 단일 노드로 구성했으며, 실습용으로 보안 플러그인을 비활성화했다.

### 최종 확인 결과

```text
NAME                        SERVICE                 STATUS
edr-opensearch              opensearch              Up
edr-opensearch-dashboards   opensearch-dashboards   Up
edr-postgres                postgres                Up
```

OpenSearch HTTP 요청 결과:

```text
HTTP/1.1 200 OK

"cluster_name": "docker-cluster"
"status": "yellow"
"number_of_nodes": 1
"active_primary_shards": 13
"unassigned_shards": 2
```

단일 노드에서 미할당 복제 샤드가 존재할 수 있으므로 `yellow` 자체가 서비스 장애를 의미하지는 않는다.

---

## [0-1] PowerShell에서 jq 명령어 실행 실패

**구분:** 실습 중 실제 발생  
**출제:** 해당 없음  
**진단:** 🔍 기록 담당  
**복구까지 걸린 시간:** 미측정

### 증상

OpenSearch 클러스터 상태를 조회하려고 했으나 `jq` 명령어를 찾을 수 없다는 오류가 발생했다.

### 확인 명령과 출력

```powershell
curl -s localhost:9200/_cluster/health | jq .status
```

실제 출력:

```text
jq : 'jq' 용어가 cmdlet, 함수, 스크립트 파일
또는 실행할 수 있는 프로그램 이름으로
인식되지 않습니다.

FullyQualifiedErrorId : CommandNotFoundException
```

### 원인

`jq`는 Linux에서 자주 사용하는 JSON 처리 도구지만, Windows PowerShell에는 기본으로 설치되어 있지 않았다.

### 조치

PowerShell에 내장된 `Invoke-RestMethod`를 이용하도록 변경했다.

```powershell
(Invoke-RestMethod "http://localhost:9200/_cluster/health").status
```

### 진단 후 나눔

- **진단자:** OpenSearch 장애가 아니라 명령어 실행 환경 차이로 발생한 오류임을 확인했다.
- **출제자:** 실제 출제 장애가 아니므로 별도 의견 미기록
- **다음에 같은 증상을 보면 처음 칠 명령:**

```powershell
Get-Command jq -ErrorAction SilentlyContinue
```

### 재발 방지

Windows PowerShell용 명령어와 Ubuntu Bash용 명령어를 구분하여 기록한다.

PowerShell에서는 JSON 처리 시 `Invoke-RestMethod`, `ConvertFrom-Json` 등을 우선 사용한다.

### 고장 예상표와 비교

0단계 공식 깨 보기 목록에는 없는 문제였다. OS 환경에 따른 명령어 호환성 문제로 별도 기록했다.

---

## [0-2] OpenSearch 연결 실패 및 연결 종료

**구분:** 실습 중 실제 발생  
**출제:** 해당 없음  
**진단:** 🔍 기록 담당  
**복구까지 걸린 시간:** 미측정

### 증상

OpenSearch API에 연결할 수 없다는 오류가 발생했다.

이후 재시도에서는 연결이 예기치 않게 닫혔다는 오류가 발생했다.

### 확인 명령과 출력

```powershell
(Invoke-RestMethod "http://localhost:9200/_cluster/health").status
```

첫 번째 오류:

```text
Invoke-RestMethod : 원격 서버에 연결할 수 없습니다.
```

두 번째 오류:

```text
Invoke-RestMethod : 기본 연결이 닫혔습니다.
예기치 않게 연결이 닫혔습니다.
```

Docker 상태 확인:

```powershell
docker compose ps
```

실제 확인 결과:

```text
edr-opensearch              Up 45 seconds
edr-opensearch-dashboards   Up 45 seconds
edr-postgres                Up 44 seconds
```

HTTP 요청 확인:

```powershell
curl.exe -v http://localhost:9200/_cluster/health
```

결과:

```text
HTTP/1.1 200 OK
status: yellow
number_of_nodes: 1
active_primary_shards: 13
unassigned_shards: 2
```

HTTPS 요청 확인:

```powershell
curl.exe -k -v https://localhost:9200/_cluster/health
```

결과:

```text
curl: (35) schannel:
SEC_E_INVALID_TOKEN
```

### 원인

최종적으로 HTTP API는 정상 동작했다.

Docker 컨테이너의 실행 시간이 짧았던 점을 고려하면 OpenSearch 초기화 과정에서 연결을 시도했을 가능성이 있다.

HTTPS 요청 실패는 현재 OpenSearch가 HTTP로 서비스되는 설정과 관련된다.

초기 연결 실패의 정확한 내부 원인은 로그로 확정하지 못했다.

### 조치

Docker 컨테이너 상태와 HTTP 요청 결과를 확인했다.

```powershell
docker compose ps
curl.exe -v http://localhost:9200/_cluster/health
```

정상 HTTP 응답을 확인한 뒤 기존 설정을 유지했다.

데이터 삭제나 볼륨 초기화는 수행하지 않았다.

### 진단 후 나눔

- **진단자:** 서버가 실행 중인지 확인하지 않고 API 요청만 반복한 점이 진단을 늦출 수 있음을 확인했다.
- **출제자:** 실제 출제 장애가 아니므로 별도 의견 미기록
- **다음에 같은 증상을 보면 처음 칠 명령:**

```powershell
docker compose ps
```

### 재발 방지

- 컨테이너의 `Up` 상태와 애플리케이션의 준비 상태를 구분한다.
- OpenSearch의 HTTP API가 준비됐는지 확인한 뒤 후속 작업을 수행한다.
- HTTP/HTTPS 설정을 확인한다.
- 데이터 보존이 필요한 경우 `docker compose down -v`를 사용하지 않는다.

### 고장 예상표와 비교

0단계 공식 목록의 포트 충돌, `vm.max_map_count` 문제와 직접 일치하지 않는다. 애플리케이션 준비 상태 확인 사례로 기록했다.

---

# 1단계. Ubuntu 서버 및 k3s 배포

## 구축 내용

가비아 Ubuntu 서버에 k3s를 설치하고, `soc` Namespace에 첫 API Deployment와 Service를 배포했다.

### 서버 사양

| 항목 | 실제 측정 |
|---|---|
| CPU | 4 vCPU |
| 전체 메모리 | 15Gi |
| 사용 가능 메모리 | 약 14Gi |
| 디스크 전체 | 48G |
| 디스크 여유 | 44G |
| Swap | 0B |
| Kubernetes | v1.37.2+k3s1 |

### Kubernetes 노드

```bash
sudo k3s kubectl get nodes
```

실제 출력:

```text
NAME        STATUS   ROLES           AGE   VERSION
edr-team3   Ready    control-plane   43h   v1.37.2+k3s1
```

### API 배포

- Namespace: `soc`
- Deployment: `api`
- Service: `api`
- 이미지: `ghcr.io/erd-ai-team3/edr-ai-triage-team3:lab-v1`
- API Service 포트: 80
- 초기 환경변수: `BACKEND=memory`

---

## [1-1] SSH 개인키 파일 경로 오류

**구분:** 실습 중 실제 발생  
**출제:** 해당 없음  
**진단:** 🔍 기록 담당  
**복구까지 걸린 시간:** 미측정

### 증상

Ubuntu 서버에 SSH로 접속하려 했으나 개인키 파일을 찾지 못했다.

### 확인 명령과 출력

Windows PowerShell:

```powershell
ssh -i .\edr-team3-key.pem ubuntu@<SERVER_IP>
```

실제 오류:

```text
Warning: Identity file .\edr-team3-key.pem
not accessible: No such file or directory.

ubuntu@<SERVER_IP>'s password:
```

### 원인

현재 PowerShell 경로는 프로젝트 폴더였지만, SSH 개인키는 사용자 홈 폴더에 있었다.

상대 경로 `.\edr-team3-key.pem`을 사용하면서 잘못된 위치에서 파일을 검색했다.

### 조치

개인키 경로 확인:

```powershell
Test-Path "$HOME\edr-team3-key.pem"
```

SSH 접속 시 절대 경로 사용:

```powershell
ssh -i "$HOME\edr-team3-key.pem" ubuntu@<SERVER_IP>
```

이후 Ubuntu 서버에 접속해 k3s 관리 명령을 실행했다.

### 진단 후 나눔

- **진단자:** SSH 인증 문제로 생각하기 전에 파일 경로를 확인해야 한다는 점을 배웠다.
- **출제자:** 별도 의견 미기록
- **다음에 같은 증상을 보면 처음 칠 명령:**

```powershell
Test-Path "$HOME\edr-team3-key.pem"
```

### 재발 방지

- SSH 개인키는 홈 디렉터리 또는 별도의 보안 디렉터리에서 관리한다.
- 접속 명령에는 절대 경로를 사용한다.
- 개인키를 Git 저장소에 커밋하지 않는다.
- 개인키 파일 권한을 제한한다.

### 고장 예상표와 비교

공식 1단계 목록의 GHCR 이미지 오류나 kubeconfig 주소 오류와는 다른 SSH 클라이언트 파일 경로 문제였다.

---

## [1-2] k3s kubeconfig 권한 부족

**구분:** 실습 중 실제 발생  
**출제:** 해당 없음  
**진단:** 🔍 기록 담당  
**복구까지 걸린 시간:** 미측정

### 증상

Ubuntu 일반 사용자로 `kubectl get nodes`를 실행했지만 kubeconfig 파일 접근 권한이 없었다.

### 확인 명령과 출력

```bash
kubectl get nodes
```

실제 출력:

```text
Unable to read /etc/rancher/k3s/k3s.yaml

error loading config file:
"/etc/rancher/k3s/k3s.yaml":
permission denied
```

### 원인

k3s의 기본 kubeconfig 파일에 일반 사용자 `ubuntu`의 읽기 권한이 없었다.

### 조치

관리자 권한으로 실행했다.

```bash
sudo k3s kubectl get nodes
```

정상 출력:

```text
edr-team3   Ready   control-plane   43h   v1.37.2+k3s1
```

일반 사용자로 `kubectl`을 사용해야 하는 경우에는 kubeconfig를 홈 디렉터리에 별도로 복사할 수 있다.

```bash
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown "$(id -u):$(id -g)" ~/.kube/config
chmod 600 ~/.kube/config
```

해당 복사 명령의 실제 실행 여부는 별도로 기록되지 않았다.

### 진단 후 나눔

- **진단자:** Kubernetes 서비스 자체의 문제와 kubeconfig 접근 권한 문제를 구분했다.
- **출제자:** 별도 의견 미기록
- **다음에 같은 증상을 보면 처음 칠 명령:**

```bash
sudo k3s kubectl get nodes
```

### 재발 방지

kubeconfig 접근 권한을 사전에 확인하고, 인증 정보를 외부에 공유하지 않는다.

### 고장 예상표와 비교

공식 목록의 kubeconfig 주소 오류와는 다르게 파일 읽기 권한 부족 문제였다.

---

## [1-3] API Pod가 없는 상태

**구분:** 실습 중 실제 발생  
**출제:** 해당 없음  
**진단:** 🔍 기록 담당  
**복구까지 걸린 시간:** 미측정

### 증상

`soc` Namespace에 API Service는 존재했지만 Pod가 보이지 않았다.

### 확인 명령과 출력

```bash
sudo k3s kubectl get pods -n soc
```

실제 출력:

```text
No resources found in soc namespace.
```

Service 확인:

```bash
sudo k3s kubectl get svc -n soc
```

```text
NAME   TYPE        CLUSTER-IP     PORT(S)
api    ClusterIP   10.43.75.255   80/TCP
```

Deployment 확인:

```bash
sudo k3s kubectl -n soc get deployments
```

```text
NAME   READY   UP-TO-DATE   AVAILABLE
api    0/0     0            0
```

상세 출력:

```text
Replicas: 0 desired | 0 updated |
0 total | 0 available | 0 unavailable
```

### 원인

API Deployment가 삭제된 것이 아니라 `replicas=0`으로 설정돼 있었다.

따라서 Kubernetes는 정상적으로 Pod를 0개 유지하고 있었다.

누가 언제 복제본 수를 0으로 설정했는지는 확인되지 않았다.

### 조치

Deployment 복제본을 1개로 변경했다.

```bash
sudo k3s kubectl -n soc scale deployment/api --replicas=1
```

Pod 상태 확인:

```bash
sudo k3s kubectl -n soc get pods -o wide
```

실제 확인 결과:

```text
NAME                   READY   STATUS    RESTARTS
api-75c865dd87-g6v8v   1/1     Running   0
```

### 진단 후 나눔

- **진단자:** Service가 존재하더라도 Pod가 없으면 애플리케이션에 연결할 수 없다는 점을 확인했다. Pod 로그보다 Deployment의 복제본 수를 먼저 확인하는 것이 효과적이었다.
- **출제자:** 별도 의견 미기록
- **다음에 같은 증상을 보면 처음 칠 명령:**

```bash
sudo k3s kubectl -n soc get deployments,replicasets,pods
```

### 재발 방지

- Deployment의 `READY`, `DESIRED`, `AVAILABLE`을 함께 확인한다.
- Scale Down 작업은 팀원에게 공유한다.
- 서비스 장애 발생 시 Service뿐 아니라 EndpointSlice와 Pod 상태를 함께 확인한다.

### 고장 예상표와 비교

1단계 공식 목록에는 없는 사례였다. 4단계 워커의 `replicas=0` 장애와 유사한 원리다.

---

# 2단계. OpenSearch StatefulSet + PVC 구축

## 구축 내용

Kubernetes에 OpenSearch를 StatefulSet으로 배포하고 PersistentVolumeClaim을 연결했다.

목표는 Pod를 삭제하더라도 동일한 PVC를 사용해 기존 데이터를 유지하는 것이었다.

### 배포 리소스

파일: `infra/k8s/20-opensearch.yaml`

| 리소스 | 이름 | 역할 |
|---|---|---|
| StatefulSet | `opensearch` | OpenSearch Pod 관리 |
| Headless Service | `opensearch-headless` | StatefulSet의 안정적인 DNS 주소 |
| ClusterIP Service | `opensearch` | 내부 애플리케이션 연결 |
| PVC | `opensearch-data-opensearch-0` | 영구 데이터 저장 |

### 설정값

| 항목 | 설정 |
|---|---|
| 이미지 | OpenSearch 2.19.1 |
| Replicas | 1 |
| CPU Request | 500m |
| CPU Limit | 2 |
| Memory Request | 2Gi |
| Memory Limit | 4Gi |
| JVM Heap | 2Gi |
| PVC | 10Gi |
| StorageClass | local-path |
| Readiness Probe | `/_cluster/health?local=true` |

### 서버 환경 확인

```bash
nproc
free -h
df -h /
sudo k3s kubectl get storageclass
sysctl vm.max_map_count
```

실제 확인 결과:

```text
CPU: 4
Memory: 15Gi
Swap: 0B
Disk: 48G / Available: 44G

StorageClass: local-path (default)
vm.max_map_count = 1048576
```

OpenSearch의 요구 기준인 `262144`보다 `vm.max_map_count`가 높게 설정되어 있었다.

---

## [2-1] Kubernetes 매니페스트 경로 오류

**구분:** 실습 중 실제 발생  
**출제:** 해당 없음  
**진단:** 🔍 기록 담당  
**복구까지 걸린 시간:** 미측정

### 증상

OpenSearch YAML을 작성한 뒤 Ubuntu 서버에서 배포하려 했지만 파일을 찾을 수 없었다.

### 확인 명령과 출력

```bash
sudo k3s kubectl apply -f infra/k8s/20-opensearch.yaml
```

실제 출력:

```text
error: the path "infra/k8s/20-opensearch.yaml" does not exist
```

### 원인

YAML 파일은 Windows 개발 PC의 Git 프로젝트에 작성돼 있었지만 Ubuntu 서버에는 같은 파일이 존재하지 않았다.

로컬 PC와 Ubuntu 서버가 서로 다른 파일 시스템이라는 점을 고려하지 못했다.

### 조치

Windows에서 파일 존재 여부를 확인하고 SCP로 Ubuntu 서버에 전송했다.

Windows PowerShell:

```powershell
Test-Path "C:\project\edr-ai-triage-lab\infra\k8s\20-opensearch.yaml"
```

```powershell
scp -i "$HOME\edr-team3-key.pem" `
  .\infra\k8s\20-opensearch.yaml `
  ubuntu@<SERVER_IP>:/home/ubuntu/
```

Ubuntu 서버에서 YAML 검사:

```bash
sudo k3s kubectl apply --dry-run=client -f ~/20-opensearch.yaml
```

실제 출력:

```text
service/opensearch-headless created (dry run)
service/opensearch created (dry run)
statefulset.apps/opensearch created (dry run)
```

### 진단 후 나눔

- **진단자:** 파일을 Windows에서 생성한 것과 Ubuntu 서버에 존재하는 것을 혼동했다. 명령어 실행 위치와 파일 경로를 먼저 확인해야 했다.
- **출제자:** 별도 의견 미기록
- **다음에 같은 증상을 보면 처음 칠 명령:**

```bash
ls -l ~/20-opensearch.yaml
```

### 재발 방지

- Git 프로젝트에서 매니페스트 원본을 관리한다.
- 서버에는 Git Pull 또는 SCP를 이용해 전달한다.
- `kubectl apply` 전 파일 경로를 확인한다.
- 가능하면 `--dry-run=client`로 먼저 검증한다.

### 고장 예상표와 비교

2단계 공식 깨 보기 목록에는 없는 파일 배포 경로 오류였다.

---

## [2-2] OpenSearch Pod Running이지만 Ready가 되지 않음

**구분:** 실습 중 실제 발생한 일시적 상태  
**출제:** 해당 없음  
**진단:** 🔍 기록 담당  
**복구까지 걸린 시간:** 별도 조치 없음

### 증상

OpenSearch StatefulSet을 배포한 직후 Pod가 `Running`이었지만 `READY`가 `0/1`이었다.

### 확인 명령과 출력

```bash
sudo k3s kubectl -n soc get pods -o wide
```

실제 출력:

```text
NAME                   READY   STATUS    RESTARTS   AGE
api-75c865dd87-g6v8v   1/1     Running   0          32m
opensearch-0           0/1     Running   0          47s
```

### 원인

Pod의 컨테이너는 실행됐지만 readinessProbe를 통과하지 않은 상태였다.

OpenSearch 초기화가 진행 중이었을 가능성이 높으며, 실제로 시간이 지난 뒤 Ready 상태로 전환되었다.

### 조치

설정을 변경하거나 Pod를 강제로 삭제하지 않고 상태를 다시 확인했다.

```bash
sudo k3s kubectl -n soc get pods -o wide
```

이후 실제 출력:

```text
NAME                   READY   STATUS    RESTARTS   AGE
api-75c865dd87-g6v8v   1/1     Running   0          33m
opensearch-0           1/1     Running   0          98s
```

OpenSearch API 확인:

```bash
sudo k3s kubectl -n soc exec opensearch-0 -- \
  curl -fsS http://localhost:9200/_cluster/health
```

실제 결과:

```text
cluster_name: docker-cluster
status: green
number_of_nodes: 1
active_primary_shards: 3
active_shards: 3
unassigned_shards: 0
active_shards_percent_as_number: 100.0
```

### 진단 후 나눔

- **진단자:** `Running`과 `Ready`는 서로 다른 상태라는 것을 확인했다. 애플리케이션 초기화 중일 때는 불필요하게 재시작하지 않고 readinessProbe 결과를 확인해야 한다.
- **출제자:** 별도 의견 미기록
- **다음에 같은 증상을 보면 처음 칠 명령:**

```bash
sudo k3s kubectl -n soc describe pod opensearch-0
```

### 재발 방지

- OpenSearch의 초기화 시간을 고려해 readinessProbe를 설정한다.
- `Running`만 확인하지 않고 `READY`까지 확인한다.
- 준비 상태가 계속 실패하면 Pod Events와 애플리케이션 로그를 조사한다.

### 고장 예상표와 비교

2단계 공식 목록의 OOM, PVC Pending, 커널 설정 오류와 직접 일치하지 않는다. 정상적인 초기화 과정에서 Ready 상태가 늦게 전환된 사례로 기록했다.

---

## [2-3] StatefulSet Pod 재생성 및 PVC 데이터 영속성 검증

**구분:** 정상 기능 검증 실험  
**운전:** 🔍 기록 담당  
**검증 결과:** 완료 보고  
**복구까지 걸린 시간:** 미측정

### 목적

OpenSearch Pod를 삭제하더라도 PVC에 저장된 데이터가 유지되는지 확인한다.

### 확인 명령

PVC 확인:

```bash
sudo k3s kubectl -n soc get pvc
```

별도 테스트 인덱스에 문서 저장:

```bash
sudo k3s kubectl -n soc exec opensearch-0 -- \
  curl -fsS -X PUT \
  "http://localhost:9200/pvc-persistence-test/_doc/test-001?refresh=true" \
  -H "Content-Type: application/json" \
  -d '{"message":"PVC persistence test","value":123}'
```

저장 전 문서 수 확인:

```bash
sudo k3s kubectl -n soc exec opensearch-0 -- \
  curl -fsS http://localhost:9200/pvc-persistence-test/_count
```

Pod 삭제:

```bash
sudo k3s kubectl -n soc delete pod opensearch-0
```

StatefulSet 복구 확인:

```bash
sudo k3s kubectl -n soc rollout status statefulset/opensearch --timeout=180s
```

Pod 재생성 후 문서 조회:

```bash
sudo k3s kubectl -n soc exec opensearch-0 -- \
  curl -fsS http://localhost:9200/pvc-persistence-test/_doc/test-001
```

### 결과

사용자가 2단계 영속성 테스트 완료를 보고했다.

따라서 **Pod 재생성 후 데이터 유지 검증을 완료한 것으로 기록**한다.

단, 최종 `_count` 및 문서 조회의 실제 출력 원문은 이 기록에 제공되지 않았으므로 임의로 작성하지 않는다.

### 원리

StatefulSet은 `opensearch-0`이라는 안정적인 Pod 이름과 PVC 연결을 제공한다.

Pod가 삭제되더라도 기존 PVC가 유지되면 새로 생성된 Pod가 같은 볼륨을 다시 사용하여 저장 데이터를 읽을 수 있다.

### 진단 후 나눔

- **진단자:** Pod 삭제와 PVC 삭제는 서로 다른 작업이라는 점을 확인했다. 데이터 보존 검증 시 Pod만 삭제해야 한다.
- **출제자:** 실제 의견 미기록
- **다음에 데이터가 사라진 것처럼 보이면 처음 칠 명령:**

```bash
sudo k3s kubectl -n soc get sts,pvc,pods
```

### 재발 방지

- StatefulSet Pod 삭제와 PVC 삭제를 구분한다.
- PVC 삭제 전 데이터 백업을 확인한다.
- `local-path` StorageClass의 ReclaimPolicy가 `Delete`라는 점을 기록한다.
- Pod 재생성 이후 저장된 문서 수를 비교한다.
- 단일 노드의 PVC는 노드 자체가 손실됐을 때의 복구를 보장하지 않으므로 운영 환경에서는 별도 백업이 필요하다.

### 고장 예상표와 비교

2단계의 핵심 성공 조건인 StatefulSet Pod 재생성과 데이터 유지 검증에 해당한다.

공식 장애 주입 목록인 `2-1`~`2-5` 중 특정 장애를 출제·복구한 기록은 아직 없다.

---

# 인프라 0~2단계 최종 요약

| 단계 | 구축 내용 | 현재 결과 | 추가 확인 |
|---|---|---|---|
| 0단계 | Docker Compose 기반 OpenSearch·Postgres | 로컬 연결 확인 | 공식 깨 보기 여부 |
| 1단계 | Ubuntu + k3s + API Deployment | Node Ready, API 1/1 Running | 공식 깨 보기 및 RUNBOOK 팀 리뷰 |
| 2단계 | OpenSearch StatefulSet + PVC | Pod 1/1, Cluster green, 영속성 테스트 완료 보고 | 실제 출력 보존 및 공식 깨 보기 |

## 핵심 학습 내용

### 0단계 — 로컬 컨테이너 운영

Docker 컨테이너 실행 상태와 실제 서비스 준비 상태는 다르다.

OpenSearch API가 응답하지 않는 경우에는 Docker 상태, 로그, 포트 및 HTTP/HTTPS 설정을 순서대로 확인해야 한다.

### 1단계 — Kubernetes 리소스 관계

Deployment는 원하는 Pod 개수를 관리하고, ReplicaSet은 실제 Pod 생성을 담당한다.

Service가 남아 있어도 Deployment의 복제본이 0개면 연결할 Pod가 없으므로 API 서비스가 동작하지 않는다.

### 2단계 — StatefulSet과 PVC

StatefulSet은 상태가 있는 애플리케이션에 안정적인 Pod 식별자를 제공하고, PVC는 데이터를 Pod 생명주기와 분리한다.

따라서 Pod를 삭제하고 재생성하더라도 같은 PVC를 연결하면 데이터를 유지할 수 있다.

---


### 3단계 — PostgreSQL + Secret + ConfigMap**

### [3-1] PostgreSQL Pod 재생성 및 데이터 영속성 검증

**구분:** 정상 기능 검증 실험  
**담당:** 인프라 3단계  
**복구까지 걸린 시간:** 미측정

- **증상:** PostgreSQL Pod를 삭제했을 때 데이터 손실 없이 자동 복구되는지 검증해야 했다.
- **확인 명령과 실제 출력:**

```bash
sudo k3s kubectl -n soc get pvc postgres-data-postgres-0
# postgres-data-postgres-0   Bound   ...   5Gi   RWO   local-path

sudo k3s kubectl -n soc delete pod postgres-0
# pod "postgres-0" deleted from soc namespace

sudo k3s kubectl -n soc rollout status statefulset/postgres --timeout=180s
# Waiting for 1 pods to be ready...
# partitioned roll out complete: 1 new pods have been updated...

sudo k3s kubectl -n soc get pods,pvc
# postgres-0   1/1   Running   0   15s
# postgres-data-postgres-0   Bound   ...   5Gi
```

Pod 재생성 전후 SQL 조회:

```sql
SELECT * FROM persistence_test;
```

실제 출력:

```text
 id |       message
----+---------------------
  1 | PostgreSQL PVC test
(1 row)
```

- **원인:** 장애가 아닌 의도적인 Pod 삭제 실험이다. StatefulSet이 Pod를 자동으로 재생성하고 기존 PVC를 다시 연결했다.
- **조치:** 별도 수동 복구 없이 StatefulSet이 `postgres-0`을 재생성했다. 이후 데이터베이스에 접속해 기존 데이터를 확인했다.
- **진단 후 나눔:**
  - 진단자: Pod의 생명주기와 PVC의 생명주기가 서로 다르다는 것을 확인했다.
  - 출제자: 실제 의견 미기록
  - 다음에 같은 증상을 보면 처음 칠 명령: `sudo k3s kubectl -n soc get sts,pods,pvc`
- **재발 방지:** StatefulSet과 PVC 상태를 함께 모니터링한다. PVC 삭제 전 백업 여부를 확인한다.
- **고장 예상표와 비교:** PostgreSQL 영속성 검증 항목에 해당한다. 고장 예상표와의 구체적인 비교는 별도 기록이 필요하다.

**결론:** PostgreSQL Pod를 삭제한 뒤에도 기존 PVC가 유지됐으며, 데이터 1건이 정상적으로 조회됐다.


 ## 4단계 — Kubernetes 장애 복구 실험 결과

**실험일:** 2026-11-19  
**환경:** Ubuntu / k3s / `soc` 네임스페이스  
**대상:** API, Worker, Generator Deployment

```bash
1. 전체 상태 확인
sudo k3s kubectl -n soc get pods

2. Deployment 상태 확인
sudo k3s kubectl -n soc get deployments

3. 문제 Pod의 이벤트 확인
sudo k3s kubectl -n soc describe pod <POD_NAME>

4. 로그 확인
sudo k3s kubectl -n soc logs deployment/<DEPLOYMENT_NAME> --tail=100

5. 자동 복구 여부 확인
sudo k3s kubectl -n soc rollout status \
  deployment/<DEPLOYMENT_NAME> --timeout=180s
```

### 1. Worker Pod 자동 복구

- 기존 Pod: `worker-6557bb4547-mgbwz`
- 장애 주입: `kubectl delete pod -l app=worker`
- 복구된 Pod: `worker-6557bb4547-kprjq`
- 결과: `1/1 Running`, 재시작 0회
- Health 확인: `heartbeat 0s ago`
- PostgreSQL 체크포인트: 172건 조회

**판정:** 통과. Deployment가 Worker를 자동 재생성했고 PostgreSQL 체크포인트 저장소에 접근할 수 있었음.

### 2. API Pod 자동 복구

- 기존 Pod: `api-6c7b99d678-mqv8d`
- 장애 주입: `kubectl delete pod -l app=api`
- 복구된 Pod: `api-6c7b99d678-zxbkr`
- 결과: `1/1 Running`, 재시작 0회
- `/healthz`: `status=ok`, `backend=real`
- `/readyz`: OpenSearch 및 PostgreSQL 모두 정상
- Service Endpoint: `10.42.0.31:8000`
- Worker에서 `http://api/readyz` 접근 성공

**판정:** 통과. API Pod 재생성, 저장소 연결, Kubernetes Service를 통한 접근이 복구됨.

### 3. Generator Pod 자동 복구

- 기존 Pod: `generator-58b5577cbc-4r4f2`
- 장애 주입: `kubectl delete pod -l app=generator`
- 복구된 Pod: `generator-58b5577cbc-kqwvc`
- 결과: `1/1 Running`, 재시작 0회
- OpenSearch Bulk 요청: HTTP 200
- 복구 전 이벤트: 5,825건
- 복구 후 이벤트: 5,866건
- 이벤트 증가량: 41건

**판정:** 통과. Generator가 재시작된 후 이벤트 생성 및 OpenSearch 적재를 재개함.

### 4. 종합 결과

API, Worker, Generator의 Pod 삭제 실험에서 Kubernetes Deployment가 새 Pod를 자동으로 생성했으며, 각 서비스의 핵심 동작을 확인함.

**검증 범위:** Pod 단위 복구 및 애플리케이션 연결 정상화.

**미검증 범위:** 노드 장애, 디스크 장애, 처리 중 작업의 무손실 재개, 장시간 부하 상황에서의 복구.
