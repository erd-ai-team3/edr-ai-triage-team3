# 도구 계약

> 1일차에 함께 정합니다. **혼자 바꾸지 않습니다.** 바꾸려면 상대에게 먼저 말하고, 이 표와 `src/soc/mocks.py`를 같이 고친 뒤 변경 이력에 적습니다.

🔍 기록 담당: 이상준  📘 문서 담당: 김규연  (둘 다 이름을 적으면 계약 성립)

## 도구 목록

| 도구 | 만드는 사람 | 입력 | 출력 (꼭 있어야 하는 칸) | 결과 개수 상한 | 실패하면 |
|---|---|---|---|---|---|
| `get_process_tree(host, pid)` | 🔍 | | `event_id`, … | | |
| `get_process_activity(host, pid)` | 🔍 | | `event_id`, … | | |
| `get_host_timeline(host, around_ts, minutes)` | 🔍 | | `event_id`, … | | |
| `get_network_connections(host, minutes=30, around_ts=None)` | 📘 | `host: str`, `minutes: int` (1~1440), `around_ts: str \| None` (기본 현재 UTC) | `from`, `to`, `destinations`(IP별 `connection_count`, `count_is_lower_bound`, `first_seen`, `last_seen`, `interval_seconds`(이벤트 2건 미만이면 null), `evidence[].event_id`), `truncated` | 최대 500개 이벤트 집계, 외부 IP 50개, IP당 근거 이벤트 10개 | 결과 없으면 `destinations: []`; 입력 오류는 `ValueError`, 검색 오류는 예외; `truncated=true`면 집계 일부일 수 있음 |
| `search_playbook(query, k)` | 📘 | query: str, k: int = 3 | `text`, `source`(파일 이름), `page`, `category`, `score` | 최대 5개 (기본 3개) | 검색 결과 없으면 [], 실행 오류 시 예외 발생 |

## 꼭 합의할 것
- 🔍 텔레메트리 도구의 모든 결과에는 **`event_id`**가 있다. → 가드레일이 판정 근거를 추적하는 데 씁니다 (2일차 `G-1`).
- 📘 플레이북 검색 결과에는 **`source`(파일 이름)**가 있다. → 권고에 출처를 붙이는 데 씁니다.

## 변경 이력

| 바꾼 것 | 이유 | 둘 다 동의 |
|---|---|---|
| `get_network_connections(host, minutes, around_ts)` 추가 | 주기적인 외부 IP 연결을 횟수·간격으로 조사하고 실제 이벤트 ID를 추적 | 완료 (문서 담당·기록 담당 동의) |
