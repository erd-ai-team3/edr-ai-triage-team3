# 결정 기록 (발표 대본)

> "무엇을 했나"보다 **"왜 그렇게 했고, 무엇을 포기했나"**. 가능하면 숫자로 적습니다.

## 🔍 기록 담당

### 데이터 관찰 (1일차)
<!-- 공격 시나리오 하나의 기록을 시간순으로. pid → ppid 족보 -->

### text vs keyword (1일차)
<!-- 03 문서 1장의 질문에 대한 내 답과, 실제로 정한 매핑 -->

## 📘 문서 담당

### 📘 파싱 관찰 (1일차): PDF 9종
실행: `python -m soc.kb.inspect --strategy fast` · 기본 파싱 기준선

| 파일 | 요소 수 | 깨진 것 / 관찰 | 고른 파싱 방법 | 판단 / 후속 확인 |
|---|---:|---|---|---|
| `01_response_policy_tables.pdf` | 78 | Table 0, Title 50, NarrativeText 13 | `fast` | Table 요소 0개. 구조화된 표로 보존되지 않았고, 셀 내용은 원문과 대조 필요 |
| `02_playbook_credential_dump.pdf` | 21 | NarrativeText 9, Title 8 | `fast` | 고장 예상과 비교할 기준 결과 확보 |
| `03_playbook_ransomware_header_footer.pdf` | 31 | Header 4, Footer 2 감지 | `fast` | 본문에 머리말·꼬리말이 섞일 수 있어 제거 검토 |
| `04_playbook_macro_powershell_code.pdf` | 41 | Title 18, NarrativeText 12 | `fast` | 코드 블록 분류 여부는 후속 확인 |
| `05_newsletter_two_column.pdf` | 43 | Title 30, NarrativeText 12 | `fast` | 2단 읽기 순서가 보존되는지 후속 확인 |
| `06_false_positive_guide_scanned.pdf` | 0 | 요소 추출 실패 | `fast` | 이미지 스캔이라 OCR 필요 (`ocr_only` 전략 검토) |
| `07_weekly_report_chart.pdf` | 34 | UncategorizedText 14 | `fast` | 차트 숫자와 표 구조를 후속 확인 |
| `08_analyst_notes_attack_en.pdf` | 22 | NarrativeText 13, Title 9 | `fast` | 영문 문서도 본문 요소로 분류되는지 확인 |
| `09_response_matrix_complex_tables.pdf` | 237 | Table 0, Title 128, UncategorizedText 64 | `fast` | Table 요소 0개라 구조화된 표로 인식되지 않음. 셀 내용은 원문 대조, `hi_res`와 비교 |

**고장 예상표 확인:** 03에서 Header 4개와 Footer 2개가 감지되어 예상한 요소가 존재했다. 06은 요소 0개로 스캔본 추출 실패 예상이 맞았다. 09는 Table 요소가 0개라 표 구조 인식 문제 가능성이 있다. 실제 셀 구조는 추가 확인이 필요하다.

**결론:** `fast`는 텍스트 중심 문서의 기준선으로 유지한다. 01과 09는 `hi_res`에서 Table 요소가 각각 2개와 5개 검출되어 표 보존에 유리했다. 06은 `ocr_only`로 텍스트를 추출했지만 오인식과 글자 간격 오류가 보여 후처리가 필요하다.

### 새로 반영: 파일별 파싱 전략 가설 검증
| 파일명 | `fast` 결과 | 성능이 더 나을 것으로 예상한 전략 (가설) | 실행 결과 및 `fast` 대비 관찰 |
|---|---|---|---|
| `01_response_policy_tables.pdf` | 78개, Table 0개 | `hi_res` | 16개, Table 2개. `fast`보다 표 요소가 추출됨 |
| `02_playbook_credential_dump.pdf` | 21개 | — (`fast` 유지) | 21개 요소 추출. 별도 전략 비교 가설 없음 |
| `03_playbook_ransomware_header_footer.pdf` | 31개, Header 4개, Footer 2개 | — (`fast` 유지) | 머리말·꼬리말은 `fast`에서 감지하고 후처리로 제거 |
| `04_playbook_macro_powershell_code.pdf` | 41개 | — (`fast` 유지) | 코드 텍스트 정확성은 원문과 별도 대조 필요 |
| `05_newsletter_two_column.pdf` | 43개 | `hi_res` | 14개 추출. 제목과 본문을 추출했으며 열 순서는 원문과 추가 대조 필요 |
| `06_false_positive_guide_scanned.pdf` | 0개 | `ocr_only` | 9개 추출. `fast`보다 텍스트가 나왔지만 한국어 글자 분리와 오인식이 있어 후처리 필요 |
| `07_weekly_report_chart.pdf` | 34개 | `hi_res` | 11개, Table 1개, Image 1개. `fast`에서 없던 표·이미지 요소 추출 |
| `08_analyst_notes_attack_en.pdf` | 22개 | — (`fast` 유지) | 22개 요소로 영문 본문 추출. 별도 전략 비교 가설 없음 |
| `09_response_matrix_complex_tables.pdf` | 237개, Table 0개 | `hi_res` | 19개, Table 5개. `fast`보다 표 요소가 추출됨 |

검증 환경: Tesseract 5.4.0.20240606, Poppler 25.07.0-0, 한국어 학습 데이터 `kor.traineddata`.

### 청킹 값 (1일차) + 🔍 교차 실험 (2일차)
파일별 파싱 전략을 고정하고 `new_after_n_chars=600`에서 `max_characters`를 비교했다. 각 조건에서 인덱스를 재생성하고 21문항으로 Recall@3를 평가했다.

| max_characters | new_after_n_chars | 청크 수 | Recall@3 (키워드) | Recall@3 (벡터) | Recall@3 (hybrid) |
|---:|---:|---:|---:|---:|---:|
| 600 | 600 | 31 | 0.905 | 0.857 | 0.810 |
| **800 (선택)** | 600 | **30** | **0.952** | **0.857** | **0.857** |
| 1000 | 600 | 30 | 0.952 | 0.857 | 0.857 |
| 1200 | 600 | 30 | 0.952 | 0.857 | 0.857 |

800, 1000, 1200자는 모든 검색 방식에서 같은 Recall@3를 냈다. 그중 800자는 600자보다 키워드와 hybrid Recall@3가 높고, 1000·1200자와 점수가 같으면서 청크는 30개로 적다. 따라서 현재 선택값은 파일별 파싱, `max_characters=800`, `new_after_n_chars=600`이다. 이전 `fast` 단일 전략의 600자 결과는 아래 기준선에 과거 기준점으로 남겼다.

| 검색 방식 | Recall@3 | 21문항 중 실패 문항 |
|---|---:|---|
| 키워드 | 0.952 | k14 |
| 벡터 | 0.857 | k10, k14, k21 |
| hybrid (RRF) | 0.857 | k10, k13, k14 |

문서별 hybrid 결과: 01 3/3, 02 1/1, 03 2/2, 04 1/1, 05 2/2, 06 0/1, 07 2/2, 08 0/2, 09 7/7. 총 18/21로 Recall@3는 0.857이다.

## 👥 함께

### 가드레일 실패 처리 (2일차)
**선택:** 검증 실패 시 재조사를 최대 2회 시도하고, 그래도 실패하면 판정을 `suspicious`로 낮춰 사람 검토를 표시한다 (`GUARDRAIL_ON_FAIL=retry`, `MAX_GUARDRAIL_RETRIES=2`).

**이유:** 근거가 빠졌거나 실제 조회 기록과 맞지 않을 때 한정된 재조사 기회를 주면 추가 증거로 판정을 보완할 수 있다. 재시도 뒤에도 근거가 검증되지 않으면 악성 판정을 그대로 내보내지 않고 확인되지 않은 근거를 제외해 사람에게 넘긴다. 재시도 상한은 조사 반복에 따른 지연과 비용을 제한한다.

### 프로브 설계표 (2일차, 인프라 4단계)
| | API | 워커 |
|---|---|---|
| liveness | | |
| readiness | | |
| 종료 유예 | | |

### 평가: 기준점(2일차)과 최종(3일차)
| 지표 | 기준점 | 최종 | 바뀐 이유 |
|---|---|---|---|
| RAG Recall@3 | 0.857 (21문항 중 18문항, k=3) | | |
| 판정 정확도 | 0.750 (12건 중 9건, seed 기본값 42) | | |
| 지어낸 근거 비율 | 0.000 (0/12) | | |
| 승인 요청 비율 | 0.583 (12건 중 7건) | | |
| 응답 속도 | 평균 23.15초, 최대 46.71초 | | |
| 알림당 비용 | $0.00464 | | |

실행 설정: `TELEMETRY_TOOLS=real`, `KB_TOOLS=real`, 파일별 파싱, `max_characters=800`, `new_after_n_chars=600`.

### 틀린 사례 분석 (2일차)
| 사례 | 어느 단계에서 틀렸나 (도구 / RAG / 판정) | 근거 |
|---|---|---|
| `al-e44004f618a7` — `it_inventory_script` (정답 benign, 판정 suspicious) | 판정 (잠정) | 실제 IT 자산 수집 스크립트와 외부 통신을 조회했지만, 모델은 `ExecutionPolicy Bypass`와 통신을 위험 신호로 보고 정상 업무 맥락보다 의심 요소에 무게를 뒀다. 오탐 유도용 정상 시나리오를 benign으로 구분하지 못한 사례다. |
| `al-a30de1f7496b` — `it_inventory_script` (정답 benign, 판정 suspicious) | 판정 (잠정) | PowerShell의 `-ExecutionPolicy Bypass`와 외부 IP 통신을 위험 신호로 강조하고, 정상 IT 자산 수집 스크립트로 보인다는 맥락은 언급하면서도 최종 판정을 suspicious로 내렸다. 정상 시나리오의 업무 맥락을 최종 판정에 반영하지 못한 오탐이다. |

### 고도화 선정 (3일차)
| 고도화 | 만든 사람 | 영역 (내 / 상대) | 근거 (약한 숫자, 틀린 사례, 예상 못 한 고장) | 증명할 숫자 | 원래 담당자 동의 |
|---|---|---|---|---|---|
| | | | | | |

**고르지 않은 후보와 이유**
-

### 숫자 해석 (3일차)
| | 🔍 기록 담당 | 📘 문서 담당 |
|---|---|---|
| 내 영역 숫자의 변화와 원인 | | |
| 상대가 한 질문과 내 답 | | |

**함께 내린 결론**
- 가장 효과가 컸던 변경과 그 이유:
- 아직 남은 약점과 더 할 일:
