"""🔍 조사 도구: 에이전트가 PC 기록을 조사할 때 부르는 함수들.

도구 계약 (docs/CONTRACT.md)
- 모든 결과의 기록 하나하나에 event_id가 있다.
- 명령줄은 앞부분만 요약해 LLM 토큰 사용량을 줄인다.
- 프로세스 조회에서는 host와 pid를 함께 사용한다.

    pytest tests/test_telemetry_tools.py -q
"""

from __future__ import annotations

from datetime import datetime, timedelta

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

    p = e.get("process") or {}

    out = {
        "event_id": e["event_id"],
        "ts": e["ts"],
        "type": e["type"],
        "pid": p.get("pid"),
        "ppid": p.get("ppid"),
        "name": p.get("name"),
        "parent_name": p.get("parent_name"),
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


# --------------------------------------------------
# LangChain 도구 등록
# --------------------------------------------------

TELEMETRY_TOOLS = [
    tool(get_process_tree),
    tool(get_process_activity),
    tool(get_host_timeline),
]



def test_summarize_preserves_parent_name():
    from soc.telemetry.tools import summarize

    event = {
        "event_id": "evt-test-001",
        "ts": "2026-11-18T09:00:00Z",
        "type": "process",
        "process": {
            "pid": 1234,
            "ppid": 600,
            "name": "powershell.exe",
            "parent_name": "ccmexec.exe",
            "cmdline": "powershell.exe -NoProfile",
            "user": "SYSTEM",
            "signed": True,
        },
    }

    result = summarize(event)

    assert result["event_id"] == "evt-test-001"
    assert result["name"] == "powershell.exe"
    assert result["parent_name"] == "ccmexec.exe"
    assert result["ppid"] == 600


def test_summarize_missing_parent_name():
    from soc.telemetry.tools import summarize

    event = {
        "event_id": "evt-test-002",
        "ts": "2026-11-18T09:01:00Z",
        "type": "process",
        "process": {
            "pid": 5678,
            "name": "cmd.exe",
        },
    }

    result = summarize(event)

    assert result["parent_name"] is None
    assert result["name"] == "cmd.exe"
