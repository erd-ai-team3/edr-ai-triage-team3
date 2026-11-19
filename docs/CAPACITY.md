# 용량 산정 (16GB 서버 기준)

> 2일차 인프라 2단계를 시작하기 전에 계산합니다. 2단계 운전자(🔍 기록 담당)가 주도하고, 📘 문서 담당이 검토합니다.

| 워크로드 | 종류 | CPU req | Mem req / limit | 힙 | 근거 |
|---|---|---|---|---|---|
| OS + k3s + Traefik | - | 별도 확보 | 별도 확보 | - | 실측: `free -h`, `kubectl top` |
| opensearch | StatefulSet | 500m | 2Gi / 4Gi | 1Gi | 검색·인덱싱 처리, JVM 힙 확보 |
| postgres | StatefulSet | 100m | 256Mi / 1Gi | - | 체크포인트·분석 결과 저장 |
| api | Deployment | 100m | 128Mi / 512Mi | - | FastAPI 요청 처리 |
| worker | Deployment | 250m | 512Mi / 2Gi | - | AI 분석 및 백그라운드 작업 |
| generator | Deployment | 100m | 128Mi / 512Mi | - | EDR 이벤트 생성 |
| kb-ingest (일시적) | Job | 100m | 256Mi / 512Mi | - | 지식 데이터 수집·색인, 임시 산정 |
| **합계 / 여유** | - | **상시 1050m / 여유 2950m** | **상시 3024Mi / 8Gi, 여유 약 13Gi / 8Gi** | **1Gi** | 4 vCPU·16Gi 기준, OS·k3s 제외, Job 실행 시 별도 추가 |