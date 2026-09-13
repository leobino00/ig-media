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

import analysis_gate as AG
import backtest as BT
import leverage as LV
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
        return self.period_return(on, 52)

    def period_return(self, on, periods_per_year):
        return (self.a / 100.0) / float(periods_per_year)


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


def test_leverage():
    ds = wk(4)
    cs = [100.0, 110.0, 99.0, 108.9]
    r0 = FlatRate(0.0)

    s1 = LV.simulate_daily(ds, cs, 1.0, r0, 0.0)
    check("1배·보수0·금리0 = 원자산", near(s1[-1][1], cs[-1] / cs[0], 1e-12))

    s3 = LV.simulate_daily(ds, cs, 3.0, r0, 0.0)
    exp = 1.0
    for i in range(1, len(cs)):
        exp *= (1 + 3 * (cs[i] / cs[i - 1] - 1))
    check("3배는 일간 등락률에 3을 곱해 복리한다", near(s3[-1][1], exp, 1e-12))

    # 변동성 끌림: +10% 뒤 -10% 면 원자산은 -1%, 3배는 -9%
    s3b = LV.simulate_daily(wk(3), [100.0, 110.0, 99.0], 3.0, r0, 0.0)
    check("변동성 끌림이 계산에서 나온다", near(s3b[-1][1], 1.3 * 0.7, 1e-12),
          "3배 왕복은 -9%%여야 한다: %r" % s3b[-1][1])

    # 차입비용: L=3 이면 금리가 2배만큼 빠진다
    sr = LV.simulate_daily(wk(2), [100.0, 100.0], 3.0, FlatRate(25.2), 0.0)
    check("L=3 은 (1-L)=-2 배의 금리를 낸다",
          near(sr[-1][1], 1 + (1 - 3) * (0.252 / LV.TRADING_DAYS), 1e-12))
    si = LV.simulate_daily(wk(2), [100.0, 100.0], -3.0, FlatRate(25.2), 0.0)
    check("L=-3 은 (1-L)=+4 배의 금리를 받는다",
          near(si[-1][1], 1 + 4 * (0.252 / LV.TRADING_DAYS), 1e-12))

    sf = LV.simulate_daily(wk(2), [100.0, 100.0], 3.0, r0, 25.2)
    check("보수는 매일 차감된다", near(sf[-1][1], 1 - 0.252 / LV.TRADING_DAYS, 1e-12))

    # 주간 집계는 기준일 이하의 마지막 일간 값을 쓴다 (미래를 보지 않는다)
    daily = [(dt.date(2020, 1, 1), 1.0), (dt.date(2020, 1, 3), 2.0), (dt.date(2020, 1, 8), 9.0)]
    w = LV.to_weekly(daily, [dt.date(2020, 1, 3), dt.date(2020, 1, 10)])
    check("주간 집계는 미래 일간값을 당겨쓰지 않는다", near(w[0][1], 2.0) and near(w[1][1], 9.0))

    fee = LV.fit_fee(ds, cs, 3.0, r0, LV.cagr_pct(LV.simulate_daily(ds, cs, 3.0, r0, 3.5)))
    check("보수 적합이 원래 값을 되찾는다", near(fee, 3.5, 1e-3), "%r" % fee)


def test_daily_tr_and_periods():
    # 일봉 총수익 복원: 격자점에서 정확히 일치해야 한다
    dp = [(dt.date(2020, 1, 6) + dt.timedelta(days=i), 100.0) for i in range(10)]
    wf = [(dt.date(2020, 1, 8), 0.98), (dt.date(2020, 1, 13), 1.0)]
    tr = dict(prices.build_daily_total_return(dp, wf))
    check("격자 이전 날짜는 첫 factor를 쓴다", near(tr[dt.date(2020, 1, 6)], 98.0, 1e-9))
    check("격자일에 factor가 바뀐다", near(tr[dt.date(2020, 1, 8)], 98.0, 1e-9)
          and near(tr[dt.date(2020, 1, 13)], 100.0, 1e-9))
    check("격자 사이에는 계단 유지", near(tr[dt.date(2020, 1, 12)], 98.0, 1e-9))
    check("길이 보존", len(tr) == len(dp))

    # 연율화 주기
    ds = wk(5)
    rets = {"A": {ds[i]: 0.0 for i in range(1, 5)}}
    mp = {S.UP: "A", S.DOWN: None, S.NEUTRAL: None}
    rc = FlatRate(25.2)
    rw = BT.run(ds, {d: S.NEUTRAL for d in ds}, rets, mp, rc, switch_cost_bps=0.0, periods_per_year=52)
    rd = BT.run(ds, {d: S.NEUTRAL for d in ds}, rets, mp, rc, switch_cost_bps=0.0, periods_per_year=252)
    check("현금 수익률이 연율화 주기를 따른다",
          near(rw.curve[-1][1], (1 + 0.252 / 52) ** 4, 1e-12)
          and near(rd.curve[-1][1], (1 + 0.252 / 252) ** 4, 1e-12))
    check("변동성 연율화가 주기를 따른다", rw.vol_pct is not None and rd.vol_pct is not None)

    # 주간·일간 규칙 짝
    pr = S.pair_weekly_daily()
    gw, gdd = dict(S.build_grid_wide()), dict(S.build_grid_daily())
    check("짝 60쌍", len(pr) == 60)
    check("짝의 양쪽이 모두 그리드에 있다", all(a in gw and b in gdd for a, b in pr))
    check("짝은 1:1 이다", len({a for a, _ in pr}) == 60 and len({b for _, b in pr}) == 60)
    check("짝의 길이비가 5배다", ("sma40_b0", "sma200_b0") in pr)


def test_vol_and_weights():
    ds = wk(30)
    # 변동성이 0 인 시계열
    flat = [100.0] * 30
    v = S.realized_vol(ds, flat, 13)
    check("변동 없으면 변동성 0", near(v[ds[-1]], 0.0, 1e-9))
    check("워밍업 부족 주는 값이 없다", ds[5] not in v)

    g = S.vol_gate_abs({ds[-1]: 20.0}, 20.0)
    check("변동성 경계: 같으면 통과 아님(strict)", g[ds[-1]] is False)
    check("변동성 경계: 미만이면 통과", S.vol_gate_abs({ds[-1]: 19.99}, 20.0)[ds[-1]] is True)

    st_ = {ds[i]: S.UP for i in range(30)}
    gated = S.gate_states(st_, {ds[i]: (i % 2 == 0) for i in range(30)})
    check("게이트 막히면 UP이 NEUTRAL이 된다",
          gated[ds[0]] == S.UP and gated[ds[1]] == S.NEUTRAL)
    check("게이트 값이 없으면 들어가지 않는다", S.gate_states(st_, {})[ds[0]] == S.NEUTRAL)
    check("추세가 DOWN이면 게이트 통과해도 UP 아님",
          S.gate_states({ds[0]: S.DOWN}, {ds[0]: True})[ds[0]] == S.NEUTRAL)

    w = S.vol_target_weight({ds[0]: 40.0, ds[1]: 10.0}, 20.0)
    check("타게팅 비중 = 목표/실현", near(w[ds[0]], 0.5, 1e-12))
    check("타게팅 비중 상한 1", near(w[ds[1]], 1.0, 1e-12))

    # 백분위 게이트는 과거만 본다
    vv = {ds[i]: float(i) for i in range(30)}
    gp = S.vol_gate_pct(vv, ds, 50.0, 10)
    check("백분위 게이트 워밍업", ds[5] not in gp)
    check("백분위 게이트: 상승 시계열의 최신값은 항상 상위 → 막힌다", gp[ds[-1]] is False)

    # 연속 비중 엔진
    d4 = wk(4)
    rets = {"A": {d4[1]: 0.10, d4[2]: 0.10, d4[3]: 0.10}}
    r1 = BT.run_weights(d4, {d: 1.0 for d in d4}, rets, "A", FlatRate(0.0), switch_cost_bps=0.0)
    check("비중 1 = 바이앤홀드", near(r1.curve[-1][1], 1.1 ** 3, 1e-12))
    r0 = BT.run_weights(d4, {d: 0.0 for d in d4}, rets, "A", FlatRate(5.2), switch_cost_bps=0.0)
    check("비중 0 = 현금", near(r0.curve[-1][1], (1 + 0.052 / 52) ** 3, 1e-12))
    rh = BT.run_weights(d4, {d: 0.5 for d in d4}, rets, "A", FlatRate(0.0), switch_cost_bps=0.0)
    check("비중 0.5 = 절반", near(rh.curve[-1][1], 1.05 ** 3, 1e-12))
    rc_ = BT.run_weights(d4, {d4[0]: 0.0, d4[1]: 1.0, d4[2]: 1.0, d4[3]: 1.0},
                         rets, "A", FlatRate(0.0), switch_cost_bps=100.0)
    check("비용은 비중 변화량에 비례", near(rc_.turnover, 1.0, 1e-12))
    check("결측 비중은 현금으로 둔다", near(
        BT.run_weights(d4, {}, rets, "A", FlatRate(0.0), switch_cost_bps=0.0).curve[-1][1], 1.0, 1e-12))


def test_asymmetric():
    ds = wk(12)
    cs = [100.0] * 5 + [120.0, 120.0, 120.0, 90.0, 90.0, 120.0, 120.0]

    def seq(ec, xc, eb=0.0, xb=0.0):
        st_ = S.asymmetric(ds, cs, 5, eb, xb, ec, xc)
        return "".join("U" if st_[d] == S.UP else "." for d in ds if d in st_)

    check("시작 상태는 현금", seq(1, 1)[0] == ".")
    check("진입확인 1 = 즉시 진입", seq(1, 1) == ".UUU..UU", seq(1, 1))
    check("진입확인 3 = 3주 연속 필요", seq(3, 1) == "...U....", seq(3, 1))
    check("이탈확인 3 = 눌림을 버틴다", seq(1, 3) == ".UUUUUUU", seq(1, 3))
    check("이탈확인 2 = 2주째에 나간다", seq(1, 2).count("U") > seq(1, 1).count("U"))

    # 이력(hysteresis): 밴드 안이면 직전 상태를 유지한다
    ds2 = wk(8)
    # 120 으로 상단 밴드를 넘어 진입한 뒤, 이후 값들이 ±4% 밴드 **안**에 머문다
    cs2 = [100.0, 100.0, 100.0, 120.0, 108.0, 109.0, 110.0, 110.0]
    st2 = S.asymmetric(ds2, cs2, 3, 4.0, 4.0, 1, 1)
    inside = [d for d in ds2[3:] if d in st2]
    check("밴드 안에서는 직전 상태 유지(이력)", all(st2[d] == S.UP for d in inside),
          "".join("U" if st2[d] == S.UP else "." for d in ds2 if d in st2))
    # 밴드 하단을 뚫으면 나간다
    cs3 = [100.0, 100.0, 100.0, 120.0, 108.0, 109.0, 110.0, 95.0]
    st3 = S.asymmetric(ds2, cs3, 3, 4.0, 4.0, 1, 1)
    check("밴드 하단을 뚫으면 이탈", st3[ds2[-1]] == S.NEUTRAL)

    # 거울짝이 격자 안에 반드시 있다
    g = S.build_asym_grid()
    names = {n for n, _, _ in g}
    miss = []
    for n, _, p_ in g:
        mir = "a%d_e%.0f-%d_x%.0f-%d" % (p_["sma"], p_["exit_band"], p_["exit_confirm"],
                                         p_["enter_band"], p_["enter_confirm"])
        if mir not in names:
            miss.append((n, mir))
    check("모든 설정의 거울짝이 격자에 있다", not miss, str(miss[:3]))

    kinds = {}
    for _, _, p_ in g:
        k = S.asym_kind(p_)
        kinds[k] = kinds.get(k, 0) + 1
    check("격자가 두 방향에 균형", kinds["이탈빠름(진입느림)"] == kinds["진입빠름(이탈느림)"],
          str(kinds))
    check("대칭 판정", S.asym_kind({"enter_confirm": 2, "enter_band": 2.0,
                                     "exit_confirm": 2, "exit_band": 2.0}) == "대칭")
    check("확인지연이 밴드보다 우선", S.asym_kind({"enter_confirm": 3, "enter_band": 0.0,
                                                   "exit_confirm": 1, "exit_band": 4.0})
          == "이탈빠름(진입느림)")


def test_analysis_helpers():
    vals = list(range(100))
    e = AG.quintile_edges(vals, 5)
    check("5분위 경계 4개", len(e) == 4)
    check("경계가 오름차순", all(e[i] < e[i + 1] for i in range(3)))
    b = [AG.bucket(v, e) for v in vals]
    check("버킷은 0~4", min(b) == 0 and max(b) == 4)
    counts = [b.count(i) for i in range(5)]
    check("버킷 크기가 고르다", max(counts) - min(counts) <= 1, str(counts))
    check("경계값은 위쪽 버킷", AG.bucket(e[0], e) == 1)

    check("자기상관 완전상관", near(AG.autocorr([1.0, 2.0, 3.0, 4.0, 5.0], 1), 1.0, 1e-9))
    check("표본 부족 자기상관 결측", AG.autocorr([1.0, 2.0], 1) is None)

    ds = wk(5)
    g = {ds[0]: True, ds[1]: True, ds[2]: False, ds[3]: False, ds[4]: True}
    s1 = AG.circular_shift(g, ds, 1)
    check("순환이동은 노출을 보존한다",
          sum(1 for v in s1.values() if v) == sum(1 for v in g.values() if v))
    check("순환이동 0은 원본", AG.circular_shift(g, ds, 0) == g)
    check("한 바퀴 돌면 원본", AG.circular_shift(g, ds, 5) == g)
    check("실제로 자리가 바뀐다", s1 != g)
    # 연속 구간 길이 분포도 보존된다 (원형이므로)
    def runs(d):
        v = [d[x] for x in ds]
        out, cur = [], 1
        for i in range(1, len(v)):
            if v[i] == v[i - 1]:
                cur += 1
            else:
                out.append(cur); cur = 1
        out.append(cur)
        return sorted(out)
    check("연속구간 길이 분포 보존(원형 기준)", sum(runs(s1)) == sum(runs(g)))


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
            test_leverage()
            test_daily_tr_and_periods()
            test_vol_and_weights()
            test_asymmetric()
            test_analysis_helpers()
            test_real_data()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for n, d in _F:
        sys.stderr.write("실패: %s%s\n" % (n, (" — " + d) if d else ""))
    sys.stdout.write("시험 %d건 중 %d건 통과\n" % (len(_P) + len(_F), len(_P)))
    return 1 if _F else 0


if __name__ == "__main__":
    raise SystemExit(main())
