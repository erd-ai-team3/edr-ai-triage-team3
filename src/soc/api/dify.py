"""Dify 외부 지식(External Knowledge API) 연결: Dify가 📘 플레이북 검색을 부를 수 있게 합니다. (3일차)

Dify 요청: POST /dify/retrieval
    {"knowledge_id": "...", "query": "...", "retrieval_setting": {"top_k": 3, "score_threshold": 0.5}}
    헤더 Authorization: Bearer <DIFY_API_KEY>
응답: {"records": [{"content", "score"(0~1), "title", "metadata"}]}
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ..config import settings

router = APIRouter()


class RetrievalSetting(BaseModel):
    top_k: int = 3
    score_threshold: float = 0.0


class RetrievalRequest(BaseModel):
    knowledge_id: str = ""
    query: str
    retrieval_setting: RetrievalSetting = Field(default_factory=RetrievalSetting)



def normalize_scores(hits: list[dict]) -> list[dict]:
    """검색 점수를 Dify가 사용하는 0~1 범위로 정규화합니다."""

    if not hits:
        return []

    # 가장 높은 검색 점수 확인
    max_score = max(
        max(float(hit.get("score", 0)), 0.0)
        for hit in hits
    )

    normalized = []

    for hit in hits:
        score = max(float(hit.get("score", 0)), 0.0)

        # 모든 점수가 0이면 0으로 유지
        new_score = (
            score / max_score if max_score > 0 else 0.0
        )

        normalized.append({
            **hit,
            "score": new_score,
        })

    return normalized



@router.post("/dify/retrieval")
def retrieval(req: RetrievalRequest, authorization: str = Header(default="")):
    if authorization != f"Bearer {settings.dify_api_key}":
        raise HTTPException(status_code=403, detail={"error_code": 1002, "error_msg": "인증 실패"})
    from ..agent.toolset import search_playbook_fn

    hits = normalize_scores(search_playbook_fn()(req.query, req.retrieval_setting.top_k))
    records = [{"content": h["text"], "score": h["score"], "title": h.get("source") or "",
                "metadata": {"source": h.get("source"), "page": h.get("page"), "category": h.get("category")}}
               for h in hits if h["score"] >= req.retrieval_setting.score_threshold]
    return {"records": records}
