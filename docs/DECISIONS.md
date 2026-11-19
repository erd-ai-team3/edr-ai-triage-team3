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

#### 1일차 청킹 설정 및 기준선

| max_characters | new_after_n_chars | 청크 수 | Recall@3 (키워드) | Recall@3 (벡터) | Recall@3 (hybrid) |
|---:|---:|---:|---:|---:|---:|
| **600 (선택)** | 600 | **21** | **0.905** | **0.810** | **0.905** |
| 800 | 600 | 19 | 0.905 | 0.810 | 0.810 |
| 1000 | 600 | 19 | 0.905 | 0.810 | 0.810 |
| 1200 | 600 | 19 | 0.905 | 0.810 | 0.810 |

실험 조건: `fast`, `new_after_n_chars=600`. 각 설정을 차례로 적재한 뒤 `python -m soc.eval.rag_eval --mode all`로 21문항을 평가했다.

600자에서 Hybrid Recall@3가 0.905로 가장 높아 1일차 선택값으로 결정했다.

#### 🔍 2일차 교차 실험 — 기록 담당

| max_characters | 청크 수 | Recall@3 (hybrid) | 성공 문항 |
|---:|---:|---:|---:|
| 기존 기준점 | 19 | 0.714 | 15/21 |
| 500 | 19 | **0.714** | 15/21 |
| 1000 | 19 | **0.714** | 15/21 |
| 1500 | 19 | **0.714** | 15/21 |

실험 명령:

```bash
python -m soc.kb.ingest --max-characters 500
python -m soc.eval.rag_eval

python -m soc.kb.ingest --max-characters 1000
python -m soc.eval.rag_eval

python -m soc.kb.ingest --max-characters 1500
python -m soc.eval.rag_eval
```

**실험 결과:** 세 설정 모두 Hybrid Recall@3가 0.714로 동일했다. 이번 실험에서는 청킹 최대 길이를 변경해도 검색 성공률 개선이 확인되지 않았다.

**기존 1일차 결과와 차이가 있는 점:** 1일차에는 600자에서 Hybrid Recall@3가 0.905였지만, 2일차 측정에서는 세 설정 모두 0.714였다. 특히 1000자의 결과가 서로 다르므로 PDF 파싱 전략, `new_after_n_chars`, 임베딩·검색 설정, 평가 실행 조건의 일치 여부를 확인해야 한다.

**결론:** 2일차 교차 실험 결과만으로 기존 600자 선택을 변경할 근거는 없다. 현재는 1일차 선택값 600자를 유지할 것을 권고하며, 최종 설정은 📘 문서 담당이 결정한다.

**작업 상태:** 🔍 기록 담당의 청킹 비교 실험 완료 / 📘 문서 담당 리뷰 대기


## 👥 함께

### 가드레일 실패 처리 (2일차)
선택: 검증 실패 시 재조사를 최대 2회 시도하고, 그래도 실패하면 판정을 suspicious로 낮춰 사람 검토를 표시한다 (GUARDRAIL_ON_FAIL=retry, MAX_GUARDRAIL_RETRIES=2).

이유: 근거가 빠졌거나 실제 조회 기록과 맞지 않을 때 한정된 재조사 기회를 주면 추가 증거로 판정을 보완할 수 있다. 재시도 뒤에도 근거가 검증되지 않으면 악성 판정을 그대로 내보내지 않고 확인되지 않은 근거를 제외해 사람에게 넘긴다. 재시도 상한은 조사 반복에 따른 지연과 비용을 제한한다.

### 프로브 설계표 (2일차, 인프라 4단계)
| | API | 워커 |
|---|---|---|
| liveness | | |
| readiness | | |
| 종료 유예 | | |

### 평가: 기준점(2일차)과 최종(3일차)
| 지표 | 기준점 | 최종 | 바뀐 이유 |
|---|---|---|---|
| RAG Recall@3 | | | |
| 판정 정확도 | | | |
| 지어낸 근거 비율 | | | |
| 응답 속도 | | | |
| 알림당 비용 | | | |

### 틀린 사례 분석 (2일차)
| 사례 | 어느 단계에서 틀렸나 (도구 / RAG / 판정) | 근거 |
|---|---|---|

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
