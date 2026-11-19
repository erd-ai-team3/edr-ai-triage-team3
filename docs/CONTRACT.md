# 도구 계약

🔍 기록 담당: (본인 이름)  
📘 문서 담당: (팀원 이름)

## 도구 목록

| 도구 | 만드는 사람 | 입력 | 출력 (꼭 있어야 하는 칸) | 결과 개수 상한 | 실패하면 |
|---|---|---|---|---|---|
| `get_process_tree(host, pid)` | 🔍 기록 담당 | `host: str`, `pid: int` | `host`, `pid`, `process`, `ancestors`, `children`, `note`. 이벤트 객체에는 `event_id` 필수 | 부모 10개, 자식 50개 (제안) | 조회 불가와 기록 없음 구분, 오류 정보 반환 |
| `get_process_activity(host, pid)` | 🔍 기록 담당 | `host: str`, `pid: int` | `host`, `pid`, `events`. 각 이벤트에 `event_id` 필수 | 이벤트 100개 (제안) | 조회 실패 시 오류 정보 반환, 정상 조회 결과가 없으면 빈 목록 |
| `get_host_timeline(host, around_ts, minutes)` | 🔍 기록 담당 | `host: str`, `around_ts: str`, `minutes: int = 10` | `host`, `from`, `to`, `events`, `truncated`. 각 이벤트에 `event_id` 필수 | 이벤트 200개 (제안) | 조회 실패 시 오류 정보 반환, 결과 제한 시 `truncated=true` |
| `get_network_connections(host, minutes=30, around_ts=None)` | 📘 문서 담당| `host: str`, `minutes: int` (1~1440), `around_ts: str \| None` (기본 현재 UTC) | `from`, `to`, `destinations`(IP별 `connection_count`, `count_is_lower_bound`, `first_seen`, `last_seen`, `interval_seconds`(이벤트 2건 미만이면 null), `evidence[].event_id`), `truncated` | 최대 500개 이벤트 집계, 외부 IP 50개, IP당 근거 이벤트 10개 | 결과 없으면 `destinations: []`; 입력 오류는 `ValueError`, 검색 오류는 예외; `truncated=true`면 집계 일부일 수 있음 |
| `search_playbook(query, k)` | 📘 문서 담당 | `query: str`, `k: int = 3` | 각 검색 결과에 `text`, `source`, `page`, `category`, `score` | `k`개, 최대 10개 (제안) | 검색 결과가 없으면 빈 목록, 검색 시스템 장애는 오류로 구분 |

## 꼭 합의할 것

1. 텔레메트리 도구에서 반환하는 각 이벤트에는 반드시 `event_id`가 있어야 한다.
2. 플레이북 검색 결과에는 반드시 `source`(파일 이름)가 있어야 한다.
3. PID만으로 프로세스를 식별하지 않고 호스트와 실행 시각도 함께 확인한다.
4. 검색 결과가 없는 경우와 검색 자체가 실패한 경우를 구분한다.
5. 결과 개수 상한과 오류 반환 형식은 두 담당자가 합의한 뒤 확정한다.

## 변경 이력

| 바꾼 것 | 이유 | 둘 다 동의 |
|---|---|---|
| 결과 개수 상한 및 실패 정책 추가 제안 | 과도한 검색 결과와 검색 실패 상황에 대비 | 합의 대기 |