"""📘 4단계 저장: kb-playbooks 인덱스의 매핑을 정하고 청크를 넣습니다."""
from __future__ import annotations

from ..config import settings
from ..osclient import bulk_index, get_client


def index_body() -> dict:
    # 벡터 검색을 켜고, 단일 노드 개발 환경에 맞춰 샤드와 복제본을 지정합니다.
    return {
        "settings": {
            "index": {
                "knn": True,
                "number_of_shards": 1,
                "number_of_replicas": 0,
            }
        },
        "mappings": {
            "properties": {
                # 본문은 전문 검색, 임베딩은 코사인 유사도 검색에 사용합니다.
                "id": {"type": "keyword"},
                "text": {"type": "text"},
                "embedding": {
                    "type": "knn_vector",
                    "dimension": settings.embed_dim,
                    "method": {
                        "name": "hnsw",
                        "engine": "nmslib",
                        "space_type": "cosinesimil",
                    },
                },
                # 파일명·페이지·요소 종류는 검색 결과의 출처 표시에 사용합니다.
                "source": {"type": "keyword"},
                "page": {"type": "integer"},
                "category": {"type": "keyword"},
                "chunk_index": {"type": "integer"},
                # 원본 표 HTML은 저장하되 검색 대상에는 넣지 않습니다.
                "text_as_html": {"type": "text", "index": False},
            }
        },
    }


def ensure_index(client=None, recreate: bool = False) -> None:
    client = client or get_client()
    if client.indices.exists(index=settings.index_kb):
        if not recreate:
            return
        # 재생성 요청일 때만 기존 인덱스와 내용을 삭제합니다.
        client.indices.delete(index=settings.index_kb)
    client.indices.create(index=settings.index_kb, body=index_body())


def save(records: list[dict], vectors: list[list[float]], client=None) -> int:
    client = client or get_client()
    # 문서와 임베딩을 짝지어 같은 id로 저장해 재적재 시 중복을 막습니다.
    docs = [{k: v for k, v in r.items()} | {"embedding": vec} for r, vec in zip(records, vectors, strict=True)]
    return bulk_index(client, settings.index_kb, docs, id_field="id")
