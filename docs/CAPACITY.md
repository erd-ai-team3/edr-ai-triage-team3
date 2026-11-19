# 용량 산정 (4 vCPU / 15 GiB 서버 기준)

> 2일차 인프라 2단계를 시작하기 전에 계산합니다. 2단계 운전자(🔍 기록 담당)가 주도하고, 📘 문서 담당이 검토합니다. 아래 워크로드 값은 배포 전 서버 실측을 바탕으로 한 계획 추정치입니다.

## 배포 전 Ubuntu 실측

| 항목 | 값 |
|---|---:|
| CPU 코어 | 4 |
| 메모리 전체 | 15 GiB |
| 메모리 사용 중 | 1.2 GiB |
| 메모리 free | 13 GiB |
| buff/cache | 1.2 GiB |
| 메모리 available | 14 GiB |
| Swap | 0 B |

## 워크로드 산정

| 워크로드 | 종류 | CPU req | Mem req / limit | 힙 | 근거 |
|---|---|---:|---:|---:|---|
| OS + k3s + Traefik | 시스템 | 500m (운영 여유) | 2 GiB (운영 여유) | - | 4 vCPU 중 500m, 15 GiB 중 2 GiB를 노드 OS·k3s에 남긴다는 계획 가정. 파드 requests가 아니며, CPU 한계와 메모리 예산 계산에만 사용 |
| opensearch | StatefulSet | 500m | 2 GiB / 4 GiB | 2 GiB | CPU limit 2 CPU. 단일 검색 노드에 4 GiB 상한을 배정(서버 메모리의 약 27%). 힙은 limit의 절반으로 두고 나머지 2 GiB는 JVM 외부 메모리 여유로 둠 |
| postgres | StatefulSet | 100m | 256 MiB / 1 GiB | - | CPU limit 500m. 단일 실습 DB의 초기 상한으로 두고, limit 합계가 노드 예산에 들어가도록 설정 |
| api | Deployment | 100m | 128 MiB / 512 MiB | - | CPU limit 250m. 단일 API 파드의 낮은 초기 예산으로 설정 |
| worker | Deployment | 200m | 256 MiB / 1 GiB | - | CPU limit 500m. 처리 작업을 API보다 높게 잡되 단일 노드 CPU 안에서 제한 |
| generator | Deployment | 100m | 256 MiB / 512 MiB | - | CPU limit 250m. 단일 generator의 낮은 초기 예산으로 설정 |
| kb-ingest (일시적) | Job | 200m | 512 MiB / 1 GiB | - | CPU limit 500m. Job 실행 중 추가되는 예산으로 계산 |
| **합계 / 여유** | | 상시 1,000m req + 500m 운영 여유; Job 실행 시 1,200m req + 500m 운영 여유 | 상시 2.875 GiB req / 7 GiB limit; Job 실행 시 3.375 GiB req / 8 GiB limit. 운영 여유 포함 limit 예산 9 / 10 GiB | | CPU limit 합계는 상시 3.5 CPU, Job 실행 시 4 CPU이며 500m 운영 여유를 더하면 4 / 4.5 CPU. 4 vCPU 기준 상시는 여유 0, Job 실행 시 500m 초과(112.5% overcommit). 메모리는 Job 실행 시 운영 여유 포함 10 GiB로, 15 GiB에서 약 5 GiB가 남음 |

> 워크로드별 requests와 limits는 서버 하드웨어에 맞춘 시작 추정치입니다. 배포 전 출력만으로 각 서비스의 실제 수요를 알 수는 없으므로, 2단계 배포 후 파드별 사용량과 부하를 확인해 조정합니다.
