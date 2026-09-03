# 월간 판정 입력 — 자동 수집 파이프라인

이 세션 환경에서는 FRED(`fred.stlouisfed.org`, `api.stlouisfed.org`)가 프록시에 차단돼 있다 (2026-09-03 실측: CONNECT 403).
그래서 **수집은 GitHub Actions가 하고, 어드바이저는 저장소에서 읽는다.**

```
GitHub Actions (금요일 밤 · 매월 1일)          어드바이저 세션
  scripts/fetch_fred.py ──► 입력/fred-latest.json ──► git pull ──► 월간 판정 · 트리거 점검
                            입력/fred-latest.md
                            입력/fred-YYYY-MM-DD.json (스냅샷)
```

| 채워지는 지표 | 시리즈 | 이전 상태 |
|---|---|---|
| B2 청구 4주 평균 (+3개월 방향) | IC4WSA | 사용자 수동 |
| C3 HY OAS + **T3 발동 여부** | BAMLH0A0HYM2 | 3개월 전 값 결측 |
| C4 VIX 월평균 + **T2·T6** | VIXCLS | 사용자 수동 |
| **B5 순유동성** (WALCL − TGA − RRP, 3개월 변화) | WALCL · WTREGEN · RRPONTSYD | 결측 |
| **B34 실질금리** (10년 TIPS) | DFII10 | 결측 |
| B34 명목 · 연방기금 | DGS10 · DFF | 벤더 |
| A3 (최선노력) | FactSet 페이지 파싱 | 결측 — 실패 시 null |

**1차 출처 자동 수집 (`fetch_web.py` → `web-latest.json`):** B1 ISM 제조·서비스(ismworld.org는 reCAPTCHA 봇 벽 → **PR Newswire 배포문 제목**에서 읽음, 2026-09-03 검증), D2 한은 기준금리(bok.or.kr 표, 검증), A3 FactSet 서프라이즈(기사 본문 파싱, 문구 패턴 보강 중). 실패 시 null → 검색 2출처 규칙 (PROTOCOL 부칙 3).

**시장 지표:** 지수는 FRED `NASDAQ100`(트리거 스킬의 NDX와 일치), 달러는 FRED `DTWEXBGS`, C2 비율은 Yahoo Finance(QQQE/QQQ). stooq는 봇 차단이라 폴백만.

**검증 이력:** 2026-09-03 수동 실행 3회 — ① 푸시 경합 실패 → rebase 재시도 추가 ② FRED 전부 성공, 웹 파서 실패 → 폴백·정규식 보강 ③ ISM·한은·C2 성공, FactSet만 미해결.

**자동화되지 않는 것:** FedWatch(JS 렌더링 — 검색, 상충 시 C), V1 나스닥100 선행 PER(유료 — S&P 대체), A2(벤더 종목별 집계).

## 켜는 법 (사용자, 1회)

1. `main`에 이 워크플로가 있어야 예약 실행이 된다 — **예약(schedule)은 기본 브랜치에서만 돈다.** 이 브랜치를 main에 병합하거나, 병합 전엔 GitHub → Actions → `macro-fetch` → **Run workflow**로 수동 실행.
2. `FRED_API_KEY`는 선택. 없으면 `fredgraph.csv`로 받는다. 있으면 Settings → Secrets → Actions에 등록.
3. 첫 실행 후 `fred-latest.md`가 생기면 파이프라인 확인 끝.

## 읽는 법 (어드바이저)

- 월간 판정: 기준일(첫 영업일) 이후 가장 가까운 `fred-YYYY-MM-DD.json`을 쓴다. 기준일 이후 값이 섞이지 않게 `raw_recent`에서 기준일 이하로 자른다.
- 트리거 점검: `fred-latest.json`의 `C3_T3` · `C4_T2` 플래그를 그대로 옮긴다. 판정은 어드바이저가 한다 — 스크립트는 값과 방향만 준다.
- 값이 `null`이면 결측. 추정하지 않는다.

## 판정 자동 실행 (Routine, 2026-09-03 사용자 지시)

| 루틴 | ID | 일정 (UTC → KST) | 하는 일 |
|---|---|---|---|
| 주간 트리거 점검 | `trig_01SSz2iFHLwDLvhmikpfiiXH` | 토 01:00 → **토 10:00** | `fred-latest.json` `market`·`derived` 플래그로 T1~T6 + 원화 낙폭 → `트리거점검/YYYY-MM-DD.md` + 기록부 행 |
| 월간 판정 | `trig_014bWWwyxUNvWUPb2vnVr17i` | 매월 2일 01:30 → **2일 10:30** | 첫 영업일 기준 10지표 → `월간판정/YYYY-MM.md`, 지난달 채점, 현황 갱신 |

- 수집(GitHub Actions)이 먼저 돌고(금 22:30 UTC · 2일 00:30 UTC) 판정 세션이 그 뒤에 깨어난다.
- 루틴 세션에는 데이터 벤더 도구가 없을 수 있다. 그래서 `fetch_fred.py`가 **시장 지표(stooq QQQ·QQQE·UUP, 원달러 5년 밴드, 원화 낙폭)** 까지 계산해 둔다. 벤더가 있으면 보완, 없으면 파일만으로 진행.
- **사용량 판단(사용자 결정 2026-09-03):** 사용량을 보고 유지·수정 결정. 일시정지·해제는 어드바이저에게 「루틴 꺼줘/켜줘」로.
