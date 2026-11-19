
"""📘 PDF 적재 파이프라인: 파싱 → 필터링 → 청킹 → 임베딩 → 저장.

사용 예시:
    python -m soc.kb.ingest --dry-run
    python -m soc.kb.ingest
    python -m soc.kb.ingest --max-characters 500

k3s에서는 kb-ingest Job으로 실행합니다 (인프라 6단계).

안전장치:
- PDF가 없으면 중단
- PDF별 청크가 0개이면 중단
- 전체 청크가 0개이면 중단
- 임베딩 생성과 개수 검증 후 인덱스 재생성
- Dry-run에서는 임베딩과 OpenSearch 저장을 수행하지 않음
"""

from __future__ import annotations

import argparse
import time
from collections import Counter

from ..config import settings
from .chunk import make_chunks, to_records
from .parse import drop_header_footer, iter_pdfs, parse_pdf


def build_records(
    strategy: str | None,
    max_characters: int | None,
) -> list[dict]:
    """모든 PDF에서 청크 레코드를 생성합니다."""

    records: list[dict] = []
    pdf_count = 0

    for pdf in iter_pdfs():
        pdf_count += 1
        start = time.time()

        # 1. PDF 파싱
        elements = parse_pdf(pdf, strategy)

        # 2. 머리말과 꼬리말 제거
        elements = drop_header_footer(elements)

        if not elements:
            raise RuntimeError(
                f"{pdf.name}: 파싱 결과가 비어 있습니다. "
                "PDF 또는 OCR 설정을 확인하세요."
            )

        # 3. 청킹 및 레코드 생성
        chunks = make_chunks(elements, max_characters)
        recs = to_records(chunks, pdf.name)

        # 4. PDF별 청크 검증
        if not recs:
            raise RuntimeError(
                f"{pdf.name}: 청크가 0개입니다. "
                "KB 적재를 중단합니다."
            )

        # 5. 텍스트 내용 검증
        for i, record in enumerate(recs, start=1):
            text = record.get("text", "")

            if not isinstance(text, str) or not text.strip():
                raise RuntimeError(
                    f"{pdf.name}: {i}번째 청크의 "
                    "텍스트가 비어 있습니다."
                )

        records.extend(recs)

        kinds = Counter(
            record["category"] for record in recs
        )

        elapsed = time.time() - start

        print(
            f"{pdf.name:45s} "
            f"요소 {len(elements):4d} → "
            f"청크 {len(recs):3d} "
            f"{dict(kinds)} "
            f"({elapsed:.1f}초)",
            flush=True,
        )

    # 6. PDF 존재 여부 확인
    if pdf_count == 0:
        raise RuntimeError(
            "PDF 파일이 없습니다. "
            f"경로를 확인하세요: {settings.kb_pdf_dir}"
        )

    print(
        f"\n[INFO] PDF 처리 완료: "
        f"{pdf_count}개, 청크 {len(records)}개",
        flush=True,
    )

    return records


def main() -> None:
    """KB 적재 파이프라인을 실행합니다."""

    ap = argparse.ArgumentParser(
        description="EDR AI Triage Lab KB 적재 파이프라인"
    )

    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="파싱과 청킹만 실행하고 임베딩·저장은 생략",
    )

    ap.add_argument(
        "--strategy",
        default=None,
        help=f"기본: {settings.parse_strategy}",
    )

    ap.add_argument(
        "--max-characters",
        type=int,
        default=None,
        help=f"기본: {settings.chunk_max_characters}",
    )

    ap.add_argument(
        "--show",
        type=int,
        default=3,
        help="Dry-run에서 미리 볼 청크 수",
    )

    a = ap.parse_args()

    # 1. PDF 파싱 및 청킹
    records = build_records(
        a.strategy,
        a.max_characters,
    )

    print(
        f"\n청크 합계 {len(records)}개",
        flush=True,
    )

    # 2. 전체 청크 검증
    if not records:
        raise RuntimeError(
            "KB 청크가 0개입니다. "
            "인덱스 재생성을 중단합니다."
        )

    # 3. Dry-run: 미리보기 후 종료
    if a.dry_run:
        print(
            "[DRY-RUN] 임베딩 및 OpenSearch 저장을 생략합니다.",
            flush=True,
        )

        for record in records[: a.show]:
            print("-" * 60)

            print(
                f"[{record['source']} "
                f"p.{record['page']} "
                f"{record['category']}]\n"
                f"{record['text'][:400]}"
            )

        return

    # 실제 적재
    from .embed import embed_texts
    from .index import ensure_index, save

    # 4. 임베딩 먼저 생성
    print(
        f"[INFO] 임베딩 생성 시작: {len(records)}개",
        flush=True,
    )

    vectors = embed_texts(
        [record["text"] for record in records]
    )

    # 5. 임베딩 개수 검증
    if len(vectors) != len(records):
        raise RuntimeError(
            "임베딩 개수가 청크 개수와 일치하지 않습니다. "
            f"청크={len(records)}, 임베딩={len(vectors)}"
        )

    if any(len(vector) == 0 for vector in vectors):
        raise RuntimeError(
            "빈 임베딩 벡터가 생성되었습니다. "
            "인덱스 재생성을 중단합니다."
        )

    # 6. 인덱스 재생성
    # 주의: 기존 KB 인덱스가 삭제됩니다.
    print(
        f"[WARN] 인덱스 '{settings.index_kb}' 재생성 시작",
        flush=True,
    )

    ensure_index(recreate=True)

    # 7. OpenSearch 저장
    n = save(records, vectors)

    if n != len(records):
        raise RuntimeError(
            "저장된 청크 개수가 예상과 다릅니다. "
            f"예상={len(records)}, 저장={n}"
        )

    print(
        f"[SUCCESS] '{settings.index_kb}'에 "
        f"{n}개 청크 저장 완료",
        flush=True,
    )


if __name__ == "__main__":
    main()
