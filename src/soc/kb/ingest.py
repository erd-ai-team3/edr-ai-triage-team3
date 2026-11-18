"""📘 PDF 적재 파이프라인: 파싱 → 머리말·꼬리말 제거 → 청킹 → 임베딩 → 저장

    python -m soc.kb.ingest --dry-run          # 청크 미리보기 (임베딩·저장 안 함)
    python -m soc.kb.ingest                     # 인덱스를 새로 만들고 전부 적재
    python -m soc.kb.ingest --max-characters 500   # 청킹 값을 바꿔 다시 적재 (2일차 교차 실험)

k3s에서는 같은 명령이 kb-ingest Job으로 실행됩니다 (인프라 6단계).
"""
from __future__ import annotations

import argparse
import time
from collections import Counter

from ..config import settings
from .chunk import make_chunks, to_records
from .parse import drop_header_footer, iter_pdfs, parse_pdf


FILE_STRATEGIES = {
    "01_response_policy_tables.pdf": "hi_res",
    "02_playbook_credential_dump.pdf": "fast",
    "03_playbook_ransomware_header_footer.pdf": "fast",
    "04_playbook_macro_powershell_code.pdf": "fast",
    "05_newsletter_two_column.pdf": "hi_res",
    "06_false_positive_guide_scanned.pdf": "ocr_only",
    "07_weekly_report_chart.pdf": "hi_res",
    "08_analyst_notes_attack_en.pdf": "fast",
    "09_response_matrix_complex_tables.pdf": "hi_res",
}


def _strategy_for(pdf, strategy: str | None) -> str:
    selected_strategy = strategy or settings.parse_strategy
    if selected_strategy == "per-file":
        return FILE_STRATEGIES.get(pdf.name, "fast")
    return selected_strategy


def build_records(strategy: str | None, max_characters: int | None) -> list[dict]:
    records: list[dict] = []
    for pdf in iter_pdfs():
        t = time.time()
        selected_strategy = _strategy_for(pdf, strategy)
        elements = drop_header_footer(parse_pdf(pdf, selected_strategy))
        recs = to_records(make_chunks(elements, max_characters), pdf.name)
        records += recs
        kinds = Counter(r["category"] for r in recs)
        print(f"{pdf.name:45s} 전략 {selected_strategy:7s} 요소 {len(elements):4d} → 청크 {len(recs):3d} {dict(kinds)}  ({time.time() - t:.1f}초)")
    return records


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--strategy", default=None, help=f"fast / hi_res / ocr_only / per-file (기본: {settings.parse_strategy})")
    ap.add_argument("--max-characters", type=int, default=None, help=f"기본: {settings.chunk_max_characters}")
    ap.add_argument("--show", type=int, default=3, help="--dry-run에서 미리 볼 청크 수")
    a = ap.parse_args()

    records = build_records(a.strategy, a.max_characters)
    print(f"\n청크 합계 {len(records)}개")
    if a.dry_run:
        for r in records[: a.show]:
            print("-" * 60)
            print(f"[{r['source']} p.{r['page']} {r['category']}]\n{r['text'][:400]}")
        return

    from .embed import embed_texts
    from .index import ensure_index, save

    ensure_index(recreate=True)          # 청킹 값이 바뀌면 예전 청크가 남지 않게 새로 만듭니다
    vectors = embed_texts([r["text"] for r in records])
    n = save(records, vectors)
    print(f"'{settings.index_kb}'에 {n}개 저장")


if __name__ == "__main__":
    main()
