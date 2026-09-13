# -*- coding: utf-8 -*-
"""단위 시험 — 네트워크 불필요, 저장소 데이터 불필요.

계산 정의의 경계값과 로더의 거부 조건을 못박는다.
정의를 바꾸면 여기가 먼저 깨져야 한다.

    python3 scripts/qqq_weekly/self_test.py
"""

import contextlib
import datetime as dt
import io as _io
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import calc
import load
import lint_no_judgment as lint
import observe

_PASS = []
_FAIL = []


def check(name, cond, detail=""):
    (_PASS if cond else _FAIL).append((name, detail))


def close_to(a, b, tol=1e-9):
    return a is not None and abs(a - b) <= tol


def D(*iso):
    return [dt.date.fromisoformat(x) for x in iso]


def weeks_from(start, n):
    d0 = dt.date.fromisoformat(start)
    return [d0 + dt.timedelta(days=7 * i) for i in range(n)]


# ---------------------------------------------------------------- 기초 계산

def test_basics():
    check("pct_change 기본", close_to(calc.pct_change(110, 100), 10.0))
    check("pct_change 분모 0 → 결측", calc.pct_change(110, 0) is None)
    check("pct_change 분모 음수 → 결측", calc.pct_change(110, -1) is None)
    check("pct_change 결측 입력 → 결측", calc.pct_change(None, 100) is None)

    check("stdev_sample 표본 1개 → 결측", calc.stdev_sample([1.0]) is None)
    check("stdev_sample n-1 사용", close_to(calc.stdev_sample([1.0, 3.0]), 1.4142135623730951))
    check("mean 빈 입력 → 결측", calc.mean([]) is None)

    check("percentile 중앙값", close_to(calc.percentile([1, 2, 3], 50), 2.0))
    check("percentile 선형보간", close_to(calc.percentile([0, 10], 25), 2.5))
    check("percentile 빈 입력 → 결측", calc.percentile([], 50) is None)


def test_trend():
    c = [1.0, 2.0, 3.0, 4.0]
    check("sma 계산", close_to(calc.sma(c, 4), 2.5))
    check("sma 표본 부족 → 결측", calc.sma(c, 5) is None)
    check("sma 경계(표본 == n)", close_to(calc.sma([1.0, 3.0], 2), 2.0))

    check("above 경계: 같으면 위가 아니다", calc.above(100.0, 100.0) is False)
    check("above 위", calc.above(100.1, 100.0) is True)
    check("above 결측 → 결측(False 아님)", calc.above(None, 100.0) is None)

    check("trailing_return 경계(정확히 n주치)", close_to(calc.trailing_return([100.0, 110.0], 1), 10.0))
    check("trailing_return 표본 부족 → 결측", calc.trailing_return([100.0, 110.0], 2) is None)

    hi, lo = calc.rolling_high_low([5.0, 9.0, 7.0], 3)
    check("rolling_high_low", hi == 9.0 and lo == 5.0)
    check("rolling_high_low 표본 부족 → (결측, 결측)",
          calc.rolling_high_low([5.0], 3) == (None, None))

    r = [1.0] * 13
    check("annualized_vol 변동 없음 → 0", close_to(calc.annualized_vol(r, 13), 0.0))
    check("annualized_vol 표본 부족 → 결측", calc.annualized_vol(r, 14) is None)
    check("weekly_returns 길이 = n-1", len(calc.weekly_returns([1.0, 2.0, 3.0])) == 2)


# ---------------------------------------------------------------- 낙폭

def test_drawdown():
    c = [100.0, 120.0, 60.0, 130.0]
    dd = calc.drawdown_series(c)
    check("drawdown_series 신고가에서 0", close_to(dd[1], 0.0))
    check("drawdown_series 저점", close_to(dd[2], -50.0))

    worst, pi, ti = calc.max_drawdown(c)
    check("max_drawdown 값", close_to(worst, -50.0))
    check("max_drawdown 고점·저점 위치", pi == 1 and ti == 2)
    check("max_drawdown 빈 입력", calc.max_drawdown([]) == (None, None, None))

    # 경계: 정확히 -10.00% 는 포함한다 (이진부동소수로 -9.999999999999998 이 된다)
    dates = weeks_from("2020-01-03", 3)
    eps = calc.drawdown_episodes(dates, [100.0, 90.0, 101.0], -10.0)
    check("낙폭 경계: 정확히 -10% 는 포함", len(eps) == 1,
          "부동소수 허용치 DD_EPS 없이는 누락된다")

    eps2 = calc.drawdown_episodes(dates, [100.0, 90.01, 101.0], -10.0)
    check("낙폭 경계: -9.99% 는 제외", len(eps2) == 0)

    dates4 = weeks_from("2020-01-03", 4)
    eps3 = calc.drawdown_episodes(dates4, [100.0, 80.0, 70.0, 100.0], -10.0)
    check("낙폭 구간 1건으로 합친다", len(eps3) == 1)
    e = eps3[0]
    check("낙폭 저점은 최저 종가", close_to(e["trough_close"], 70.0))
    check("낙폭 회복 경계: 고점 종가와 같으면 회복", e["recovered"] is True)
    check("낙폭 하락 주 수", e["weeks_peak_to_trough"] == 2)
    check("낙폭 회복 주 수", e["weeks_trough_to_recovery"] == 1)
    check("낙폭 총 주 수", e["weeks_total"] == 3)

    eps4 = calc.drawdown_episodes(dates, [100.0, 80.0, 90.0], -10.0)
    check("미회복 구간 표시", eps4[0]["recovered"] is False)
    check("미회복 구간의 회복값은 결측",
          eps4[0]["recovery_date"] is None and eps4[0]["weeks_total"] is None)

    eps5 = calc.drawdown_episodes(dates4, [100.0, 80.0, 100.0, 105.0], -20.0)
    check("임계치 -20% 경계: 정확히 -20% 포함", len(eps5) == 1)


# ---------------------------------------------------------------- 연·전구간

def test_annual_and_cagr():
    dates = D("2020-12-31", "2021-12-31", "2022-06-30")
    rows = calc.annual_returns(dates, [100.0, 110.0, 121.0])
    check("연도별 3개 연도", len(rows) == 3)
    check("첫 해 등락률 결측", rows[0]["return_pct"] is None)
    check("첫 해 부분 사유", rows[0]["partial_reason"] == "직전 연말 종가 없음")
    check("중간 해는 부분이 아니다", rows[1]["partial"] is False)
    check("중간 해 등락률", close_to(rows[1]["return_pct"], 10.0))
    check("마지막 해가 12월 전이면 연중 표시",
          rows[2]["partial"] is True and rows[2]["partial_reason"].startswith("연중"))

    dates2 = D("2020-12-31", "2021-12-31")
    rows2 = calc.annual_returns(dates2, [100.0, 110.0])
    check("마지막 해가 12월이면 연중 아님", rows2[1]["partial"] is False)

    d = D("2020-01-01", "2022-01-01")
    check("cagr 2년 4배 → 100%", close_to(calc.cagr(d, [100.0, 400.0]), 100.0, tol=0.2))
    check("cagr 표본 1개 → 결측", calc.cagr(D("2020-01-01"), [100.0]) is None)


# ---------------------------------------------------------------- 로더

def _write(tmp, text):
    p = os.path.join(tmp, "t.csv")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)
    return p


def test_loader(tmp):
    ok = _write(tmp, "date,close\n2020-01-03,100\n2020-01-10,110\n")
    d, c, r = load.load(ok)
    check("로더 정상 파싱", d[0] == dt.date(2020, 1, 3) and close_to(c[1], 110.0))
    check("로더 요일 집계", r["weekday_counts"].get("Fri") == 2)

    for name, text in [
        ("열 누락 거부", "day,price\n2020-01-03,100\n"),
        ("날짜 중복 거부", "date,close\n2020-01-03,100\n2020-01-03,101\n"),
        ("역순 거부", "date,close\n2020-01-10,100\n2020-01-03,101\n"),
        ("종가 0 이하 거부", "date,close\n2020-01-03,0\n2020-01-10,101\n"),
        ("날짜 형식 오류 거부", "date,close\n2020/01/03,100\n2020-01-10,101\n"),
        ("2주 미만 거부", "date,close\n2020-01-03,100\n"),
    ]:
        try:
            load.load(_write(tmp, text))
            check(name, False, "예외가 나야 한다")
        except load.LoadError:
            check(name, True)

    gap = _write(tmp, "date,close\n2020-01-03,100\n2020-02-07,110\n")
    _, _, rg = load.load(gap)
    check("결측 주 의심 기록", len(rg["gaps"]) == 1 and rg["gaps"][0]["days"] == 35)
    check("결측 주를 보간하지 않는다", rg["row_count"] == 2)

    bom = _write(tmp, "﻿date,close\n2020-01-03,100\n2020-01-10,110\n")
    check("BOM 붙은 파일 파싱", load.load(bom)[0][0] == dt.date(2020, 1, 3))


# ---------------------------------------------------------------- 어휘 검사

def test_lint(tmp):
    good = os.path.join(tmp, "good.md")
    with open(good, "w", encoding="utf-8") as fh:
        fh.write("# t\n\n## 경계\n\n판정하지 않는다. 비중을 내지 않는다.\n\n"
                 "## 관측\n\n종가 100.00, 주간 등락률 1.00%\n\n## 한계\n\n전망하지 않는다.\n")
    check("어휘 검사 통과", lint.lint(good) == 0, "경계·한계 절의 금지어는 검사 대상이 아니다")

    bad = os.path.join(tmp, "bad.md")
    with open(bad, "w", encoding="utf-8") as fh:
        fh.write("# t\n\n## 관측\n\n지금 매수 구간이다.\n\n## 한계\n\n-\n")
    check("어휘 검사 적발", lint.lint(bad) == 1)

    noseg = os.path.join(tmp, "noseg.md")
    with open(noseg, "w", encoding="utf-8") as fh:
        fh.write("# t\n\n## 다른절\n\n내용\n")
    check("관측 절 없으면 종료코드 2", lint.lint(noseg) == 2)


# ---------------------------------------------------------------- 전 경로

def test_end_to_end(tmp):
    n = 120
    dates = weeks_from("2020-01-03", n)
    closes = []
    v = 100.0
    for i in range(n):
        v *= 1.01 if i % 3 else 0.985
        closes.append(round(v, 4))
    csv_path = os.path.join(tmp, "e2e.csv")
    with open(csv_path, "w", encoding="utf-8") as fh:
        fh.write("date,close\n")
        for d, c in zip(dates, closes):
            fh.write("%s,%s\n" % (d.isoformat(), c))

    out = os.path.join(tmp, "out")
    rc = observe.main(["--csv", csv_path, "--out", out])
    check("전 경로 종료코드 0", rc == 0)

    md = os.path.join(out, "qqq-weekly-latest.md")
    js = os.path.join(out, "qqq-weekly-latest.json")
    check("md 생성", os.path.exists(md))
    check("json 생성", os.path.exists(js))
    check("스냅샷 생성", os.path.exists(os.path.join(out, "qqq-weekly-%s.json" % dates[-1].isoformat())))

    with open(js, encoding="utf-8") as fh:
        o = json.load(fh)
    top = {"as_of", "generated_at", "symbol", "boundary", "series", "input", "span",
           "latest", "trend", "returns", "volatility", "drawdown", "distribution",
           "history", "missing", "missing_detail", "caveats", "version"}
    check("json 최상위 키 고정", top.issubset(set(o)), "빠진 키: %s" % (top - set(o)))
    check("배당 반영 여부는 미반영으로 확정(2026-09-13 벤더 대조)",
          o["series"]["dividend_adjusted"] is False)
    check("계산정의 버전 기록", o["version"] == calc.CALC_VERSION)
    check("결측 없음(120주면 52주 지표가 전부 산출된다)", o["missing"] == [], str(o["missing"]))

    check("산출물이 어휘 검사를 통과", lint.lint(md) == 0)

    with open(md, encoding="utf-8") as fh:
        md1 = fh.read()
    observe.main(["--csv", csv_path, "--out", out])
    with open(md, encoding="utf-8") as fh:
        md2 = fh.read()
    drop = lambda t: "\n".join(x for x in t.splitlines() if not x.startswith("생성 "))
    check("두 번 돌려 같다(생성시각 제외)", drop(md1) == drop(md2))

    # 표본이 짧으면 결측으로 남는지
    short_csv = os.path.join(tmp, "short.csv")
    with open(short_csv, "w", encoding="utf-8") as fh:
        fh.write("date,close\n")
        for d, c in list(zip(dates, closes))[:20]:
            fh.write("%s,%s\n" % (d.isoformat(), c))
    out2 = os.path.join(tmp, "out2")
    observe.main(["--csv", short_csv, "--out", out2, "--no-snapshot"])
    with open(os.path.join(out2, "qqq-weekly-latest.json"), encoding="utf-8") as fh:
        o2 = json.load(fh)
    check("표본 부족은 결측으로 남는다", "ret_52w_pct" in o2["missing"], str(o2["missing"]))
    check("결측 사유를 적는다", o2["missing_detail"].get("ret_52w_pct") is not None)
    check("--no-snapshot 이면 스냅샷 없음",
          not os.path.exists(os.path.join(out2, "qqq-weekly-%s.json" % o2["as_of"])))

    check("입력 오류는 종료코드 2",
          observe.main(["--csv", os.path.join(tmp, "없다.csv"), "--out", out2]) == 2)


def main():
    tmp = tempfile.mkdtemp(prefix="qqq_weekly_test_")
    quiet = _io.StringIO()
    try:
        # 피시험 코드의 정상 출력은 삼킨다. 시험 결과만 보이게 한다.
        with contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
            test_basics()
            test_trend()
            test_drawdown()
            test_annual_and_cagr()
            test_loader(tmp)
            test_lint(tmp)
            test_end_to_end(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    for name, detail in _FAIL:
        sys.stderr.write("실패: %s%s\n" % (name, (" — " + detail) if detail else ""))
    sys.stdout.write("시험 %d건 중 %d건 통과\n" % (len(_PASS) + len(_FAIL), len(_PASS)))
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
