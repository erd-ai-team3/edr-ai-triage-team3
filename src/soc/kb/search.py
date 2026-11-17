"""📘 플레이북 검색 (RAG의 R): 키워드 검색 + 벡터 검색을 RRF로 합칩니다.

- 키워드(BM25): 질문의 단어가 그대로 들어 있는 조각을 잘 찾음. 한국어 질문 → 영어 문서는 못 찾음
- 벡터(kNN)   : 뜻이 비슷한 조각을 찾음. 정확한 숫자·이름은 놓치기도 함
- RRF        : 두 검색의 점수는 단위가 달라 더할 수 없으니, 순위로 합칩니다. 1 / (60 + 순위)를 더함

도구 계약: search_playbook(query, k) → [{"source", "page", "category", "text", "score"}]
"""
from __future__ import annotations

from langchain_core.tools import tool

from ..config import settings
from ..osclient import get_client
from .embed import embed_query

RRF_K = 60


def _hits(res: dict) -> list[dict]:
    out = []
    for h in res["hits"]["hits"]:
        s = h["_source"]
        out.append({"id": h["_id"], "source": s.get("source"), "page": s.get("page"),
                    "category": s.get("category"), "text": s.get("text", ""), "score": h.get("_score")})
    return out


def keyword_search(query: str, k: int = 10) -> list[dict]:
    # 본문에서 질문의 단어가 일치하는 청크를 BM25로 찾습니다.
    body = {"size": k, "_source": {"excludes": ["embedding"]}, "query": {"match": {"text": query}}}
    return _hits(get_client().search(index=settings.index_kb, body=body))


def vector_search(query: str, k: int = 10) -> list[dict]:
    # 질문을 임베딩한 뒤 의미가 가까운 청크를 k-NN으로 찾습니다.
    body = {"size": k, "_source": {"excludes": ["embedding"]},
            "query": {"knn": {"embedding": {"vector": embed_query(query), "k": k}}}}
    return _hits(get_client().search(index=settings.index_kb, body=body))


def rrf_fuse(result_lists: list[list[dict]], top_n: int) -> list[dict]:
    """여러 검색 결과를 순위로 합칩니다. 결과 하나하나에는 "id"가 있습니다."""
    # 각 검색의 점수 단위는 다르므로, 점수 대신 순위의 역수를 합산합니다.
    if top_n <= 0:
        return []

    fused: dict[str, dict] = {}
    for results in result_lists:
        seen: set[str] = set()
        for rank, hit in enumerate(results, start=1):
            doc_id = hit.get("id")
            if doc_id is None:
                raise ValueError("검색 결과에 문서 id가 없습니다.")
            doc_id = str(doc_id)
            if doc_id in seen:
                continue
            seen.add(doc_id)
            if doc_id not in fused:
                fused[doc_id] = dict(hit, score=0.0)
            # 한 청크가 두 검색에 모두 나오면 각 순위 기여분을 누적합니다.
            fused[doc_id]["score"] += 1 / (RRF_K + rank)

    return sorted(fused.values(), key=lambda hit: hit["score"], reverse=True)[:top_n]


def search(query: str, k: int = 3, mode: str = "hybrid") -> list[dict]:
    """mode: keyword / vector / hybrid. 평가(rag_eval)에서 세 방식을 비교합니다."""
    if mode == "keyword":
        return keyword_search(query, k)
    if mode == "vector":
        return vector_search(query, k)
    # 개별 검색에서 넉넉히 후보를 모은 뒤 RRF로 최종 k개를 고릅니다.
    n = max(k * 3, 10)
    return rrf_fuse([keyword_search(query, n), vector_search(query, n)], top_n=k)


def search_playbook(query: str, k: int = 3) -> list[dict]:
    """회사의 대응 플레이북·정책 문서에서 질문과 관련된 조각을 찾습니다.
    판정 기준, 조치별 승인권자, 공격 유형별 대응 절차, 오탐 예외 규정을 확인할 때 씁니다.
    결과마다 source(파일 이름)가 있으니, 권고에는 반드시 출처를 붙이세요.

    Args:
        query: 찾을 내용 (예: "LSASS 덤프 대응 승인권자")
        k: 돌려받을 조각 수 (기본 3)
    """
    # 에이전트 계약에 필요한 출처·본문·점수만 반환합니다.
    return [{key: h[key] for key in ("source", "page", "category", "text", "score")} for h in search(query, k)]


KB_TOOLS = [tool(search_playbook)]
