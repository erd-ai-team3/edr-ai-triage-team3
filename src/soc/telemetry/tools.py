"""🔍 조사 도구: 에이전트가 PC 기록을 조사할 때 부르는 함수들.

도구 계약 (docs/CONTRACT.md)
- 모든 결과의 기록 하나하나에 event_id가 있다.
- 명령줄은 앞부분만 요약해 LLM 토큰 사용량을 줄인다.
- 프로세스 조회에서는 host와 pid를 함께 사용한다.

    pytest tests/test_telemetry_tools.py -q
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address, ip_network
from statistics import median

from langchain_core.tools import tool

from ..config import settings
from ..osclient import get_client


# --------------------------------------------------
# 공통 설정
# --------------------------------------------------

EVENTS = f"{settings.index_events}-*"

CMD_MAX = 120
MAX_ANCESTORS = 5
TIMELINE_LIMIT = 100
NETWORK_EVENT_LIMIT = 500
NETWORK_DESTINATION_LIMIT = 50
NETWORK_EVIDENCE_LIMIT = 10
MAX_NETWORK_LOOKBACK_MINUTES = 24 * 60
LAB_EXTERNAL_NETWORKS = (
    ip_network("198.51.100.0/24"),  # simulated C2 range
    ip_network("203.0.113.0/24"),   # simulated benign SaaS range
)


# --------------------------------------------------
# 공통 검색 함수
# --------------------------------------------------

def _search(body: dict) -> list[dict]:
    """OpenSearch에서 조건에 맞는 이벤트를 검색합니다."""

    res = get_client().search(
        index=EVENTS,
        body=body,
    )

    return [
        hit["_source"]
        for hit in res["hits"]["hits"]
    ]


# --------------------------------------------------
# 이벤트 요약
# --------------------------------------------------

def summarize(e: dict) -> dict:
    """이벤트를 LLM이 읽기 쉬운 형태로 요약합니다."""

    p = e.get("process", {})

    out = {
        "event_id": e["event_id"],
        "ts": e["ts"],
        "type": e["type"],
        "pid": p.get("pid"),
        "ppid": p.get("ppid"),
        "name": p.get("name"),
        "cmdline": (p.get("cmdline") or "")[:CMD_MAX],
        "user": p.get("user"),
        "signed": p.get("signed"),
    }

    if e.get("network"):
        n = e["network"]

        out["detail"] = (
            f"{n['dst_ip']}:{n['dst_port']} "
            f"({n.get('bytes_out', 0)} bytes)"
        )

    elif e.get("file"):
        f = e["file"]

        out["detail"] = (
            f"{f['action']} {f['path']}"
            + (
                f" → {f['new_path']}"
                if f.get("new_path")
                else ""
            )
        )

    elif e.get("registry"):
        r = e["registry"]

        out["detail"] = (
            f"{r['key']} = {r['value']}"
        )

    elif e.get("script_text"):
        out["detail"] = e["script_text"][:200]

    return out


# --------------------------------------------------
# 시간 처리
# --------------------------------------------------

def _parse_ts(ts: str) -> datetime:
    """ISO 형식 문자열을 datetime으로 변환합니다."""

    return datetime.fromisoformat(
        ts.replace("Z", "+00:00")
    )


def _iso(t: datetime) -> str:
    """datetime을 ISO 형식 문자열로 변환합니다."""

    return t.isoformat().replace("+00:00", "Z")


# --------------------------------------------------
# 프로세스 검색
# --------------------------------------------------

def _find_process(
    host: str,
    pid: int,
    before_ts: str | None = None,
) -> dict | None:
    """특정 PC에서 PID에 해당하는 프로세스 생성 기록을 찾습니다.

    before_ts가 지정되면 그 시각 이전(포함)에 생성된 기록 중
    가장 최근 것을 선택하여 미래의 PID 재사용 이벤트를 제외합니다.
    """

    filters = [
        {"term": {"host": host}},
        {"term": {"type": "process"}},
        {"term": {"process.pid": pid}},
    ]

    if before_ts is not None:
        filters.append({
            "range": {
                "ts": {"lte": before_ts}
            }
        })

    rows = _search({
        "size": 1,
        "sort": [
            {"ts": "desc"}
        ],
        "query": {
            "bool": {
                "filter": filters
            }
        },
    })

    return rows[0] if rows else None


# ==================================================
# TODO[REC-2] 프로세스 트리 조회
# ==================================================

def get_process_tree(host: str, pid: int) -> dict:
    """특정 PC의 프로세스 부모·자식 관계를 조사합니다.

    부모 프로세스를 최대 5단계까지 추적하고,
    대상 프로세스가 실행한 직접 자식 프로세스를 찾습니다.

    프로세스가 어떤 프로그램에서 실행되었는지,
    수상한 부모·자식 관계가 있는지 조사할 때 사용합니다.

    Args:
        host: 조사 대상 PC 이름 (예: WS-007)
        pid: 조사 대상 프로세스 PID
    """

    # 1. 조사 대상 프로세스 검색
    process = _find_process(host, pid)

    # 2. 부모 프로세스 추적
    ancestors = []

    # 순환 참조 방지
    visited = {pid}

    current = process

    for _ in range(MAX_ANCESTORS):

        if current is None:
            break

        parent_pid = current.get(
            "process", {}
        ).get("ppid")

        # 부모가 없거나 이미 조회한 PID인 경우 종료
        if parent_pid is None:
            break

        if parent_pid in visited:
            break

        visited.add(parent_pid)

        # 같은 호스트에서 자식보다 먼저 생성된 부모만 검색
        parent = _find_process(
            host=host,
            pid=parent_pid,
            before_ts=current["ts"],
        )

        if parent is None:
            break

        ancestors.append(
            summarize(parent)
        )

        current = parent

    # 3. 직접 자식 프로세스 검색
    children_rows = _search({
        "size": 100,
        "sort": [
            {"ts": "asc"}
        ],
        "query": {
            "bool": {
                "filter": [
                    {"term": {"host": host}},
                    {"term": {"type": "process"}},
                    {"term": {"process.ppid": pid}},
                ]
            }
        },
    })

    # 4. 결과 반환
    return {
        "host": host,
        "pid": pid,
        "process": (
            summarize(process)
            if process
            else None
        ),
        "ancestors": ancestors,
        "children": [
            summarize(e)
            for e in children_rows
        ],
    }


# ==================================================
# TODO[REC-3] 프로세스 활동 조회
# ==================================================

def get_process_activity(host: str, pid: int) -> dict:
    """특정 프로세스가 수행한 활동을 시간순으로 조회합니다.

    네트워크 통신, 파일 생성·변경, 레지스트리 수정,
    스크립트 실행 기록을 최대 50건 조회합니다.

    프로세스가 외부 서버에 통신했는지,
    의심스러운 파일을 생성했는지 조사할 때 사용합니다.

    Args:
        host: 조사 대상 PC 이름 (예: WS-007)
        pid: 조사 대상 프로세스 PID
    """

    # 1. 조사할 이벤트 유형
    activity_types = [
        "network",
        "file",
        "registry",
        "script",
    ]

    # 2. OpenSearch 검색
    events = _search({
        "size": 50,
        "sort": [
            {"ts": "asc"}
        ],
        "query": {
            "bool": {
                "filter": [
                    {"term": {"host": host}},
                    {"term": {"process.pid": pid}},
                    {
                        "terms": {
                            "type": activity_types
                        }
                    },
                ]
            }
        },
    })

    # 3. 이벤트 요약 후 반환
    return {
        "host": host,
        "pid": pid,
        "events": [
            summarize(e)
            for e in events
        ],
    }


# ==================================================
# TODO[REC-4] 호스트 타임라인 조회
# ==================================================

def get_host_timeline(
    host: str,
    around_ts: str,
    minutes: int = 10,
) -> dict:
    """특정 PC에서 기준 시각 전후에 발생한 이벤트를 조회합니다.

    기준 시각의 앞뒤 지정된 분 범위를 검색합니다.
    모든 이벤트 유형을 시간순으로 최대 100건 반환합니다.

    조회 결과가 100건을 초과하면 truncated=True를 반환해
    AI 에이전트가 검색 시간 범위를 줄일 수 있도록 합니다.

    Args:
        host: 조사 대상 PC 이름 (예: WS-007)
        around_ts: 기준 시각 (예: 2026-11-16T09:12:02Z)
        minutes: 기준 시각 앞뒤로 조회할 분 (기본 10)
    """

    # 1. 기준 시각 변환
    center = _parse_ts(around_ts)

    # 2. 조회 시간 범위 계산
    start = center - timedelta(
        minutes=minutes
    )

    end = center + timedelta(
        minutes=minutes
    )

    # 3. 이벤트 조회
    # 101건을 조회해 100건 초과 여부를 판단
    events = _search({
        "size": TIMELINE_LIMIT + 1,
        "sort": [
            {"ts": "asc"}
        ],
        "query": {
            "bool": {
                "filter": [
                    {"term": {"host": host}},
                    {
                        "range": {
                            "ts": {
                                "gte": _iso(start),
                                "lte": _iso(end),
                            }
                        }
                    },
                ]
            }
        },
    })

    # 4. 최대 건수 초과 여부
    truncated = (
        len(events) > TIMELINE_LIMIT
    )

    # 5. 최대 100건만 반환
    limited_events = events[:TIMELINE_LIMIT]

    return {
        "host": host,
        "from": _iso(start),
        "to": _iso(end),
        "events": [
            summarize(e)
            for e in limited_events
        ],
        "truncated": truncated,
    }


# ==================================================
# 주기적 외부 통신 요약
# ==================================================

def _is_external_ip(value: str) -> bool:
    """공인 IP와 실습용 외부 예약 IP를 외부 대상으로 취급합니다."""
    try:
        address = ip_address(value)
    except ValueError:
        return False
    return address.is_global or any(address in network for network in LAB_EXTERNAL_NETWORKS)


def _sample_network_evidence(rows: list[dict]) -> list[dict]:
    """토큰 사용량을 제한하면서 간격을 확인할 대표 연결 이벤트를 고릅니다."""
    if len(rows) <= NETWORK_EVIDENCE_LIMIT:
        selected = rows
    else:
        last_index = len(rows) - 1
        indexes = sorted({round(i * last_index / (NETWORK_EVIDENCE_LIMIT - 1))
                          for i in range(NETWORK_EVIDENCE_LIMIT)})
        selected = [rows[index] for index in indexes]

    evidence = []
    for row in selected:
        process = row.get("process", {})
        network = row.get("network", {})
        evidence.append({
            "event_id": row["event_id"],
            "ts": row["ts"],
            "pid": process.get("pid"),
            "process_name": process.get("name"),
            "dst_port": network.get("dst_port"),
        })
    return evidence


def get_network_connections(
    host: str,
    minutes: int = 30,
    around_ts: str | None = None,
) -> dict:
    """외부 IP별 반복 연결 빈도와 연결 간격을 요약합니다.

    주기적인 외부 통신(비컨/C2 가능성)이 의심될 때 사용하세요. 특히 프로세스
    활동에서 같은 외부 IP로 여러 번 접속한 흔적을 봤다면, 이 도구로 호스트의
    전체 통신을 IP별로 묶어 횟수와 간격을 비교할 수 있습니다. 한 번의 연결만
    확인하거나 파일·레지스트리 행위를 볼 때는 get_process_activity()가 적합합니다.

    minutes는 기준 시각 직전의 조회 구간입니다. 과거 알림을 조사할 때는
    around_ts에 알림 시각을 전달하세요. 생략하면 현재 UTC 시각을 기준으로 합니다.
    실제 공인 IP와 함께 시뮬레이터가 쓰는 문서용 예약 IP(198.51.100.0/24,
    203.0.113.0/24)도 실습상 외부 IP로 포함합니다.

    결과는 악성 여부를 판정하지 않습니다. 비슷한 간격의 반복은 추가 조사가
    필요한 단서일 뿐이며, 각 목적지의 evidence에 포함된 event_id를 근거로
    추적하세요. 이벤트가 500건 또는 목적지 IP가 50개를 넘으면 truncated가
    true이고, 초과한 집계는 일부 결과일 수 있습니다.

    Args:
        host: 조사 대상 PC 이름 (예: WS-007)
        minutes: 기준 시각 직전의 조회 시간(분), 1~1440 (기본 30)
        around_ts: 조회 구간 끝 시각(ISO 8601). 과거 알림 시각을 권장합니다.

    Returns:
        호스트와 조회 구간, 외부 IP별 연결 횟수·최초/최종 시각·간격 통계,
        대표 event_id 목록, 결과 잘림 여부.
    """
    if not 1 <= minutes <= MAX_NETWORK_LOOKBACK_MINUTES:
        raise ValueError(f"minutes는 1~{MAX_NETWORK_LOOKBACK_MINUTES} 범위여야 합니다.")

    end = _parse_ts(around_ts) if around_ts else datetime.now(timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    start = end - timedelta(minutes=minutes)

    events = _search({
        "size": NETWORK_EVENT_LIMIT + 1,
        # 상한에 닿으면 알림 시각에 가까운 최신 이벤트를 우선 보존합니다.
        "sort": [{"ts": "desc"}],
        "query": {
            "bool": {
                "filter": [
                    {"term": {"host": host}},
                    {"term": {"type": "network"}},
                    {"range": {"ts": {"gte": _iso(start), "lte": _iso(end)}}},
                ]
            }
        },
    })

    events_truncated = len(events) > NETWORK_EVENT_LIMIT
    events = events[:NETWORK_EVENT_LIMIT]
    by_ip: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        network = event.get("network") or {}
        dst_ip = network.get("dst_ip")
        if dst_ip and _is_external_ip(dst_ip):
            by_ip[dst_ip].append(event)

    ordered_ips = sorted(by_ip, key=lambda ip: (-len(by_ip[ip]), ip))
    destinations_truncated = len(ordered_ips) > NETWORK_DESTINATION_LIMIT
    destinations = []
    for dst_ip in ordered_ips[:NETWORK_DESTINATION_LIMIT]:
        rows = sorted(by_ip[dst_ip], key=lambda row: _parse_ts(row["ts"]))
        stamps = [_parse_ts(row["ts"]) for row in rows]
        intervals = [round((later - earlier).total_seconds(), 3)
                     for earlier, later in zip(stamps, stamps[1:])]
        interval_summary = None
        if intervals:
            interval_summary = {
                "min": min(intervals),
                "median": round(median(intervals), 3),
                "max": max(intervals),
            }
        destinations.append({
            "dst_ip": dst_ip,
            "connection_count": len(rows),
            "count_is_lower_bound": events_truncated,
            "first_seen": rows[0]["ts"],
            "last_seen": rows[-1]["ts"],
            "interval_seconds": interval_summary,
            "evidence": _sample_network_evidence(rows),
        })

    return {
        "host": host,
        "from": _iso(start),
        "to": _iso(end),
        "destinations": destinations,
        "events_truncated": events_truncated,
        "destinations_truncated": destinations_truncated,
        "truncated": events_truncated or destinations_truncated,
    }


# --------------------------------------------------
# LangChain 도구 등록
# --------------------------------------------------

TELEMETRY_TOOLS = [
    tool(get_process_tree),
    tool(get_process_activity),
    tool(get_host_timeline),
    tool(get_network_connections),
]
