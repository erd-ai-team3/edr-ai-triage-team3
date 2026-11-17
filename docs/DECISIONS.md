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
| max_characters | new_after_n_chars | 청크 수 | Recall@3 (키워드) | Recall@3 (벡터) | Recall@3 (hybrid) |
|---:|---:|---:|---:|---:|---:|
| **600 (선택)** | 600 | **21** | **0.905** | **0.810** | **0.905** |
| 800 | 600 | 19 | 0.905 | 0.810 | 0.810 |
| 1000 | 600 | 19 | 0.905 | 0.810 | 0.810 |
| 1200 | 600 | 19 | 0.905 | 0.810 | 0.810 |

실험 조건: `fast`, `new_after_n_chars=600`. 각 설정을 차례로 적재한 뒤 `python -m soc.eval.rag_eval --mode all`로 21문항을 평가했다. 청크 수는 600자 21개, 800·1000·1200자 각각 19개였다. hybrid Recall@3는 600자가 0.905, 나머지 세 설정은 0.810이었다. 따라서 현재 설정과 인덱스는 600자 기준으로 맞췄다.

### Recall@3 (600자 선택 기준선, 1일차 재측정)
| 검색 방식 | Recall@3 | 특히 k13·k14 (한국어 질문 → 영어 문서) |
|---|---|---|
| 키워드만 | **0.905** | k13 성공, k14 실패 |
| 벡터만 | 0.810 | k13·k14 실패 |
| 둘을 합침 (RRF) | **0.905** | k13 성공, k14 실패 |

평가: `python -m soc.eval.rag_eval --mode all` (21문항, k=3). 600자에서는 키워드와 hybrid가 0.905로 같았고, k13은 두 방식에서 성공했다. 벡터 검색은 0.810이며 k13·k14 모두 실패했다. k14는 세 방식 모두 실패했다.

## 👥 함께

### 가드레일 실패 처리 (2일차)
<!-- 다시 조사 vs '의심'으로 낮추기. 무엇을 골랐고 왜 -->

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
