
"""📘 PDF 파싱: Unstructured + pdftotext + Tesseract OCR.

PDF를 Unstructured 요소(Element) 목록으로 변환합니다.

파싱 전략:
- fast: PDF 텍스트 계층 기반 파싱
- hi_res: 레이아웃 분석 및 표 구조 추출
- ocr_only: Unstructured OCR

fast 전략의 자동 대체 경로:
1. Unstructured fast
2. pdftotext
3. Tesseract OCR (300 DPI, kor+eng, PSM 4)

스캔 PDF에서 텍스트를 추출할 수 없는 경우
Tesseract를 이용해 OCR을 수행합니다.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from ..config import settings


def iter_pdfs(root: str | Path | None = None):
    """PDF 디렉터리에서 PDF 파일을 이름순으로 조회합니다."""
    pdf_dir = Path(root or settings.kb_pdf_dir)

    for path in sorted(pdf_dir.glob("*.pdf")):
        yield path


def _text_to_elements(text: str, page_number: int) -> list:
    """텍스트를 Unstructured 요소로 변환하고 페이지 번호를 지정합니다."""
    from unstructured.partition.text import partition_text

    if not text.strip():
        return []

    elements = partition_text(text=text)

    for element in elements:
        element.metadata.page_number = page_number

    return elements


def _parse_with_pdftotext(path: Path) -> list:
    """pdftotext로 텍스트를 추출한 뒤 Unstructured 요소로 변환합니다."""

    result = subprocess.run(
        [
            "pdftotext",
            "-layout",
            "-enc",
            "UTF-8",
            str(path),
            "-",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )

    elements = []

    # 폼 피드(\f)를 기준으로 PDF 페이지를 구분합니다.
    pages = result.stdout.split("\f")

    for page_number, page_text in enumerate(pages, start=1):
        elements.extend(
            _text_to_elements(page_text, page_number)
        )

    return elements


def _page_number(path: Path) -> int:
    """pdftoppm이 생성한 이미지 파일명에서 페이지 번호를 추출합니다."""
    match = re.search(r"-(\d+)$", path.stem)

    if not match:
        raise ValueError(
            f"페이지 번호를 확인할 수 없습니다: {path.name}"
        )

    return int(match.group(1))


def _parse_with_tesseract(path: Path) -> list:
    """스캔 PDF를 300 DPI + Tesseract PSM 4로 처리합니다."""

    elements = []

    with tempfile.TemporaryDirectory() as tmp:
        output_prefix = Path(tmp) / "page"

        # PDF의 모든 페이지를 PNG 이미지로 변환합니다.
        subprocess.run(
            [
                "pdftoppm",
                "-r",
                "300",
                "-png",
                str(path),
                str(output_prefix),
            ],
            check=True,
            capture_output=True,
        )

        # 파일명 숫자를 기준으로 페이지 순서를 정렬합니다.
        image_paths = sorted(
            Path(tmp).glob("page-*.png"),
            key=_page_number,
        )

        if not image_paths:
            raise RuntimeError(
                f"{path.name}: PDF 이미지 변환 결과가 없습니다."
            )

        for image_path in image_paths:
            page_number = _page_number(image_path)

            result = subprocess.run(
                [
                    "tesseract",
                    str(image_path),
                    "stdout",
                    "-l",
                    "kor+eng",
                    "--psm",
                    "4",
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            page_elements = _text_to_elements(
                result.stdout,
                page_number,
            )

            elements.extend(page_elements)

            print(
                f"[OCR] {path.name} "
                f"p.{page_number}: 요소 {len(page_elements)}개",
                flush=True,
            )

    return elements


def parse_pdf(
    path: str | Path,
    strategy: str | None = None,
) -> list:
    """PDF를 Unstructured 요소 목록으로 변환합니다."""

    from unstructured.partition.auto import partition

    path = Path(path)
    strategy = strategy or settings.parse_strategy

    # 1단계: Unstructured 기본 파싱
    elements = partition(
        filename=str(path),
        strategy=strategy,
        languages=["kor", "eng"],
        infer_table_structure=(strategy == "hi_res"),
    )

    if elements:
        print(
            f"[INFO] {path.name}: "
            f"Unstructured {strategy} 요소 {len(elements)}개",
            flush=True,
        )
        return elements

    # fast 전략에서만 자동 대체 파싱을 수행합니다.
    if strategy != "fast":
        print(
            f"[WARN] {path.name}: "
            f"{strategy} 파싱 결과가 비어 있습니다.",
            flush=True,
        )
        return elements

    # 2단계: pdftotext
    print(
        f"[WARN] {path.name}: "
        "fast 파싱 결과 0개, pdftotext 실행",
        flush=True,
    )

    elements = _parse_with_pdftotext(path)

    if elements:
        print(
            f"[INFO] {path.name}: "
            f"pdftotext 요소 {len(elements)}개 생성",
            flush=True,
        )
        return elements

    # 3단계: Tesseract OCR
    print(
        f"[WARN] {path.name}: "
        "pdftotext 결과 0개, Tesseract OCR 실행",
        flush=True,
    )

    elements = _parse_with_tesseract(path)

    print(
        f"[INFO] {path.name}: "
        f"OCR 요소 {len(elements)}개 생성",
        flush=True,
    )

    return elements


def drop_header_footer(elements: list) -> list:
    """Header와 Footer로 분류된 요소를 제거합니다."""
    return [
        element
        for element in elements
        if getattr(element, "category", None)
        not in {"Header", "Footer"}
    ]
