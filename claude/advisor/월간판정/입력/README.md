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

**자동화되지 않는 것:** B1 ISM(검색), FedWatch(검색·상충 시 C), 한은 기준금리(검색), V1 나스닥100 선행 PER(결측·S&P 대체), A2(벤더 종목별 집계).

## 켜는 법 (사용자, 1회)

1. `main`에 이 워크플로가 있어야 예약 실행이 된다 — **예약(schedule)은 기본 브랜치에서만 돈다.** 이 브랜치를 main에 병합하거나, 병합 전엔 GitHub → Actions → `macro-fetch` → **Run workflow**로 수동 실행.
2. `FRED_API_KEY`는 선택. 없으면 `fredgraph.csv`로 받는다. 있으면 Settings → Secrets → Actions에 등록.
3. 첫 실행 후 `fred-latest.md`가 생기면 파이프라인 확인 끝.

## 읽는 법 (어드바이저)

- 월간 판정: 기준일(첫 영업일) 이후 가장 가까운 `fred-YYYY-MM-DD.json`을 쓴다. 기준일 이후 값이 섞이지 않게 `raw_recent`에서 기준일 이하로 자른다.
- 트리거 점검: `fred-latest.json`의 `C3_T3` · `C4_T2` 플래그를 그대로 옮긴다. 판정은 어드바이저가 한다 — 스크립트는 값과 방향만 준다.
- 값이 `null`이면 결측. 추정하지 않는다.
