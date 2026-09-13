# -*- coding: utf-8 -*-
"""단위 시험 — 네트워크 불필요.

백테스트에서 가장 조용히 틀리는 것은 **타이밍**이다. 그래서 타이밍을 제일 많이 시험한다.

    python3 scripts/qqq_regime/self_test.py
"""

import contextlib
import datetime as dt
import io as _io
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import backtest as BT
import prices
import signals as S

_P, _F = [], []


def check(name, cond, detail=""):
    (_P if cond else _F).append((name, detail))


def near(a, b, tol=1e-9):
    return a is not None and abs(a - b) <= tol


def wk(n, start="2020-01-03"):
    d0 = dt.date.fromisoformat(start)
    return [d0 + dt.timedelta(days=7 * i) for i in range(n)]


class FlatRate(object):
    def __init__(self, annual_pct):
        self.a = annual_pct

    def annual_pct(self, on):
        return self.a

    def weekly_return(self, on):
        return (self.a / 100.0) / 52.0


# ------------------------------------------------------------------ 신호

def test_signals():
    ds = wk(6)
    cs = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0]
    out = S.sma_band(ds, cs, 3, 0.0)
    check("이동평균과 같으면 UP이 아니다", out[ds[-1]] == S.NEUTRAL)
    check("표본 부족 주는 신호가 없다", ds[0] not in out and ds[1] not in out)

    cs2 = [100.0, 100.0, 100.0, 102.0]
    o2 = S.sma_band(wk(4), cs2, 3, 0.0)
    check("이동평균 위면 UP", o2[wk(4)[-1]] == S.UP)

    # band 경계: 종가가 정확히 sma*(1+b) 면 UP 이 아니다
    cs3 = [100.0, 100.0, 100.0, 102.0]
    o3 = S.sma_band(wk(4), cs3, 3, 2.0)
    check("band 경계에서 UP 아님(strict)", o3[wk(4)[-1]] == S.NEUTRAL,
          "sma=100, band 2%% → 102 는 UP 이 아니다")

    o4 = S.momentum(wk(3), [100.0, 100.0, 100.0], 2, 0.0)
    check("모멘텀 0%는 UP이 아니다", o4[wk(3)[-1]] == S.NEUTRAL)
    o5 = S.momentum(wk(3), [100.0, 100.0, 90.0], 2, 0.0)
    check("모멘텀 음수면 DOWN", o5[wk(3)[-1]] == S.DOWN)

    names = [n for n, _ in S.build_grid()]
    check("그리드에 중복 이름이 없다", len(names) == len(set(names)))
    check("그리드 크기 35", len(names) == 35, str(len(names)))


# ------------------------------------------------------------------ 타이밍

def test_timing():
    ds = wk(4)
    # A 는 2주차에만 +100%, 나머지 0%
    rets = {"A": {ds[1]: 0.0, ds[2]: 1.0, ds[3]: 0.0},
            "B": {ds[1]: 0.0, ds[2]: 0.0, ds[3]: 0.0}}
    mp = {S.UP: "A", S.DOWN: "B", S.NEUTRAL: None}
    rate = FlatRate(0.0)

    # ds[1] 종가에 UP 을 켜면 ds[2] 수익률을 받는다
    sig_ok = {ds[0]: S.DOWN, ds[1]: S.UP, ds[2]: S.DOWN, ds[3]: S.DOWN}
    r = BT.run(ds, sig_ok, rets, mp, rate, switch_cost_bps=0.0)
    check("신호는 다음 주 수익률에 적용된다", near(r.curve[-1][1], 2.0),
          "ds[1]의 UP 이 ds[2]의 +100%%를 받아야 한다: %r" % r.curve[-1][1])

    # ds[2] 에 UP 을 켜면 이미 지난 수익률은 못 받는다 (미래참조 차단 확인)
    sig_late = {ds[0]: S.DOWN, ds[1]: S.DOWN, ds[2]: S.UP, ds[3]: S.DOWN}
    r2 = BT.run(ds, sig_late, rets, mp, rate, switch_cost_bps=0.0)
    check("같은 주 종가 신호로 그 주 수익률을 받지 않는다", near(r2.curve[-1][1], 1.0),
          "받았다면 미래참조다: %r" % r2.curve[-1][1])

    # 비용은 전환한 주에만
    r3 = BT.run(ds, sig_ok, rets, mp, rate, switch_cost_bps=100.0)  # 1%
    check("전환 횟수", r3.switches == 2, str(r3.switches))
    check("비용이 전환마다 곱셈으로 붙는다", near(r3.curve[-1][1], 2.0 * 0.99 * 0.99, 1e-12))

    r4 = BT.run(ds, {d: S.UP for d in ds}, rets, mp, rate, switch_cost_bps=100.0)
    check("전환이 없으면 비용도 없다", r4.switches == 0 and near(r4.curve[-1][1], 2.0))


def test_controls():
    ds = wk(5)
    rets = {"A": {ds[i]: 0.10 for i in range(1, 5)}}
    mp = {S.UP: "A", S.DOWN: None, S.NEUTRAL: None}
    r = BT.run(ds, {d: S.UP for d in ds}, rets, mp, FlatRate(0.0), switch_cost_bps=0.0)
    bh = BT.buy_and_hold(ds, rets, "A")
    check("항상 UP = 바이앤홀드", near(r.curve[-1][1], bh.curve[-1][1], 1e-12))

    rc = FlatRate(5.2)
    r2 = BT.run(ds, {d: S.NEUTRAL for d in ds}, rets, mp, rc, switch_cost_bps=0.0)
    check("현금은 금리로 복리된다", near(r2.curve[-1][1], (1 + 0.052 / 52) ** 4, 1e-12))


def test_metrics():
    ds = wk(4)
    curve = [(ds[0], 1.0), (ds[1], 1.2), (ds[2], 0.6), (ds[3], 1.5)]
    check("최대낙폭", near(BT.max_drawdown_pct(curve), -50.0, 1e-9))
    check("낙폭 없으면 0", near(BT.max_drawdown_pct([(ds[0], 1.0), (ds[1], 2.0)]), 0.0))
    check("표본 1개 표준편차 결측", BT.stdev([1.0]) is None)

    c2 = [(dt.date(2020, 6, 5), 1.0), (dt.date(2020, 12, 31), 1.1),
          (dt.date(2021, 12, 31), 2.2), (dt.date(2022, 3, 4), 1.1)]
    a = BT.annual_returns(c2)
    check("연도 수", len(a) == 3)
    check("첫 해 부분 표시", a[0]["partial"] is not None and "시작" in a[0]["partial"])
    check("중간 해는 온전", a[1]["partial"] is None and near(a[1]["return_pct"], 100.0, 1e-9))
    check("마지막 해 부분 표시", a[2]["partial"] is not None and "까지" in a[2]["partial"])
    check("연도 경계는 직전 연말 종가 기준", near(a[2]["return_pct"], -50.0, 1e-9))


def test_rate_curve(tmp):
    p = os.path.join(tmp, "ffr.csv")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("date,ffr_pct\n2020-01-01,1.50\n2020-06-01,0.25\n2021-01-01,0.10\n")
    rc = prices.RateCurve(p)
    check("기준일 이하 최신값", near(rc.annual_pct(dt.date(2020, 5, 31)), 1.50))
    check("경계일 포함", near(rc.annual_pct(dt.date(2020, 6, 1)), 0.25))
    check("미래 값을 당겨쓰지 않는다", near(rc.annual_pct(dt.date(2020, 12, 31)), 0.25))
    check("시작 이전은 결측", rc.annual_pct(dt.date(2019, 1, 1)) is None)


def _w(tmp, name, txt):
    p = os.path.join(tmp, name)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(txt)
    return p


def test_loader(tmp):
    p = os.path.join(tmp, "s.csv")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("date,adj_close\n2020-01-03,100\n2020-01-10,110\n")
    s = prices.load_series(p)
    check("수익률 변환", near(prices.to_returns(s)[dt.date(2020, 1, 10)], 0.10, 1e-12))
    check("역순 입력은 정렬해 받는다", prices.load_series(_w(tmp, "r.csv",
          "date,adj_close\n2020-01-10,110\n2020-01-03,100\n"))[0][0] == dt.date(2020, 1, 3))
    for name, txt in [("날짜 중복 거부", "date,adj_close\n2020-01-03,100\n2020-01-03,101\n"),
                      ("0 이하 거부", "date,adj_close\n2020-01-03,0\n2020-01-10,110\n")]:
        q = os.path.join(tmp, "b.csv")
        with open(q, "w", encoding="utf-8") as fh:
            fh.write(txt)
        try:
            prices.load_series(q); check(name, False, "예외가 나야 한다")
        except ValueError:
            check(name, True)


def test_real_data():
    """저장소 실 데이터로 대조군이 벤치마크와 정확히 일치하는지 본다."""
    here = os.path.dirname(os.path.abspath(__file__))
    d = os.path.join(here, "data")
    if not os.path.exists(os.path.join(d, "tqqq_weekly_adj.csv")):
        check("실 데이터 대조군", True, "데이터 없음 — 건너뜀")
        return
    q = prices.load_series(os.path.join(d, "qqq_weekly_adj.csv"))
    t = prices.load_series(os.path.join(d, "tqqq_weekly_adj.csv"))
    s = prices.load_series(os.path.join(d, "sqqq_weekly_adj.csv"))
    rc = prices.RateCurve(os.path.join(d, "ffr_weekly.csv"))
    rets = {"QQQ": prices.to_returns(q), "TQQQ": prices.to_returns(t), "SQQQ": prices.to_returns(s)}
    qd = [x for x, _ in q]
    ds = [x for x in qd if x >= dt.date(2010, 2, 19)]
    mp = {S.UP: "TQQQ", S.DOWN: "SQQQ", S.NEUTRAL: None}
    r = BT.run(ds, {x: S.UP for x in qd}, rets, mp, rc, switch_cost_bps=10.0)
    bh = BT.buy_and_hold(ds, rets, "TQQQ")
    check("실 데이터: 항상 UP = TQQQ 바이앤홀드", near(r.cagr_pct, bh.cagr_pct, 1e-9),
          "%r vs %r" % (r.cagr_pct, bh.cagr_pct))
    check("세 종목 주간 라벨이 정확히 정렬된다", len(ds) == len(set(ds) & set(rets["TQQQ"])) + 1,
          "%d vs %d" % (len(ds), len(set(ds) & set(rets["TQQQ"]))))


def main():
    tmp = tempfile.mkdtemp(prefix="qqq_regime_test_")
    quiet = _io.StringIO()
    try:
        with contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
            test_signals()
            test_timing()
            test_controls()
            test_metrics()
            test_rate_curve(tmp)
            test_loader(tmp)
            test_real_data()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for n, d in _F:
        sys.stderr.write("실패: %s%s\n" % (n, (" — " + d) if d else ""))
    sys.stdout.write("시험 %d건 중 %d건 통과\n" % (len(_P) + len(_F), len(_P)))
    return 1 if _F else 0


if __name__ == "__main__":
    raise SystemExit(main())
