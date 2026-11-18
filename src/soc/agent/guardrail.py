
"""가드레일: LLM의 판정을 그대로 믿지 않고 기계적으로 검증합니다. (2일차 1-2, 운전 📘)

01 문서 4장의 '근거 추적'과 01번 정책 PDF 3장의 판정 기준을 코드로 옮긴 것입니다.

    pytest tests/test_guardrail.py -q
"""

from __future__ import annotations


def check_evidence_exists(
    verdict: dict,
    seen_event_ids: list[str],
    alert: dict,
) -> list[str]:
    """판정 근거가 실제 조회 기록 또는 알림 근거에 존재하는지 확인합니다."""

    # 실제 조회한 이벤트와 알림에 포함된 이벤트
    known_ids = set(seen_event_ids) | set(
        alert.get("event_ids", [])
    )

    problems = []

    for event_id in verdict.get("evidence_event_ids", []):
        if event_id not in known_ids:
            problems.append(f"조회하지 않은 근거: {event_id}")

    return problems


def check_malicious_needs_two(verdict: dict) -> list[str]:
    """악성 판정은 서로 다른 근거가 최소 2개 필요합니다."""

    if verdict.get("verdict") != "malicious":
        return []

    evidence_ids = verdict.get("evidence_event_ids", [])

    # 중복 ID는 하나의 근거로 계산
    unique_ids = set(evidence_ids)

    if len(unique_ids) < 2:
        return [
            "악성 판정에는 서로 다른 근거 2개 이상이 필요합니다."
        ]

    return []


def check(
    verdict: dict,
    seen_event_ids: list[str],
    alert: dict,
) -> dict:
    """G-1과 G-2 검증 결과를 통합합니다."""

    problems = (
        check_evidence_exists(verdict, seen_event_ids, alert)
        + check_malicious_needs_two(verdict)
    )

    return {
        "ok": not problems,
        "problems": problems,
    }
