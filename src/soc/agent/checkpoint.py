
"""체크포인터: 에이전트 상태를 저장하는 곳.

- memory: 프로세스 종료 시 상태가 사라짐
- postgres: PostgreSQL에 상태를 영구 저장
"""
from __future__ import annotations

import atexit
import logging
from functools import lru_cache

from langgraph.checkpoint.memory import InMemorySaver

from ..config import settings

log = logging.getLogger("checkpoint")

_pool = None


def _kind() -> str:
    if settings.checkpointer != "auto":
        return settings.checkpointer

    return (
        "postgres"
        if settings.backend == "real"
        else "memory"
    )


def _close_pool() -> None:
    """프로세스 종료 시 PostgreSQL 연결 풀을 닫습니다."""
    global _pool

    if _pool is not None:
        _pool.close()
        _pool = None


atexit.register(_close_pool)


@lru_cache(maxsize=1)
def get_checkpointer():
    """설정에 따라 메모리 또는 PostgreSQL 체크포인터를 반환합니다."""
    global _pool

    kind = _kind()

    if kind == "memory":
        log.info("InMemorySaver 사용")
        return InMemorySaver()

    if kind != "postgres":
        raise ValueError(f"지원하지 않는 CHECKPOINTER: {kind}")

    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    # API 동시 요청을 위한 PostgreSQL 연결 풀
    pool = ConnectionPool(
        conninfo=settings.postgres_dsn,
        min_size=1,
        max_size=5,
        open=False,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
    )

    try:
        pool.open()
        pool.wait(timeout=10)

        saver = PostgresSaver(pool)

        # 최초 테이블 생성 및 필요한 마이그레이션
        saver.setup()

    except Exception:
        pool.close()
        log.exception("PostgreSQL Checkpointer 초기화 실패")
        raise

    _pool = pool
    log.info("PostgreSQL Checkpointer 초기화 완료")

    return saver


def ping() -> bool:
    """/readyz에서 사용: PostgreSQL 연결 가능 여부 확인."""
    if _kind() == "memory":
        return True

    try:
        import psycopg

        with psycopg.connect(
            settings.postgres_dsn,
            connect_timeout=3,
        ) as conn:
            conn.execute("SELECT 1")

        return True

    except Exception:
        log.exception("PostgreSQL 연결 확인 실패")
        return False
