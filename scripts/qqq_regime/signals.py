# -*- coding: utf-8 -*-
"""레짐 판별 규칙 — QQQ 주간 수정종가만 본다.

세 상태를 낸다: UP(상승 추세) · DOWN(하락 추세) · NEUTRAL(중립·횡보).

**미래를 보지 않는다.** 기준주 t 의 상태는 t 까지의 종가만으로 계산한다.
백테스트는 그 상태를 t+1 주에 보유한다 (backtest.py 가 강제한다).

중립 구간(band)이 있는 이유: 상·하만 있으면 이동평균 근처에서 매주 뒤집히고,
거래비용이 결과를 지배한다. 사용자가 요구한 「횡보 시 현금」이 이 band 다.
"""

UP, DOWN, NEUTRAL = "UP", "DOWN", "NEUTRAL"
STATES = (UP, DOWN, NEUTRAL)


def _sma(vals, end, n):
    return sum(vals[end - n + 1:end + 1]) / n if end + 1 >= n else None


def sma_band(dates, closes, n, band_pct):
    """종가가 n주 이동평균보다 band% 위면 UP, band% 아래면 DOWN, 그 사이는 NEUTRAL."""
    b = band_pct / 100.0
    out = {}
    for i, d in enumerate(dates):
        m = _sma(closes, i, n)
        if m is None:
            continue
        c = closes[i]
        out[d] = UP if c > m * (1 + b) else (DOWN if c < m * (1 - b) else NEUTRAL)
    return out


def dual_sma(dates, closes, fast, slow, band_pct):
    """단기 이동평균이 장기 이동평균보다 band% 위면 UP, 아래면 DOWN, 사이는 NEUTRAL."""
    b = band_pct / 100.0
    out = {}
    for i, d in enumerate(dates):
        f, s = _sma(closes, i, fast), _sma(closes, i, slow)
        if f is None or s is None:
            continue
        out[d] = UP if f > s * (1 + b) else (DOWN if f < s * (1 - b) else NEUTRAL)
    return out


def momentum(dates, closes, n, thresh_pct):
    """n주 누적 등락률이 +thresh 초과면 UP, −thresh 미만이면 DOWN, 사이는 NEUTRAL."""
    t = thresh_pct / 100.0
    out = {}
    for i, d in enumerate(dates):
        if i < n:
            continue
        r = closes[i] / closes[i - n] - 1.0
        out[d] = UP if r > t else (DOWN if r < -t else NEUTRAL)
    return out


def always(dates, closes, state):
    """대조군 — 항상 같은 상태. 신호의 기여분을 재는 기준선이다."""
    return {d: state for d in dates}


def _grid(sma_n, sma_b, dual_fs, dual_b, mom_n, mom_t):
    grid = []
    for n in sma_n:
        for b in sma_b:
            grid.append(("sma%d_b%.0f" % (n, b), lambda ds, cs, n=n, b=b: sma_band(ds, cs, n, b)))
    for f, s in dual_fs:
        for b in dual_b:
            grid.append(("dual%d-%d_b%.0f" % (f, s, b), lambda ds, cs, f=f, s=s, b=b: dual_sma(ds, cs, f, s, b)))
    for n in mom_n:
        for t in mom_t:
            grid.append(("mom%d_t%.0f" % (n, t), lambda ds, cs, n=n, t=t: momentum(ds, cs, n, t)))
    return grid


def build_grid():
    """3상태 실험이 쓰는 규칙 35개. **일부만 골라 싣지 않는다** — 전수를 보고한다."""
    return _grid((10, 20, 30, 40, 52), (0.0, 2.0, 4.0),
                 ((5, 20), (10, 30), (10, 40), (20, 50)), (0.0, 2.0),
                 (4, 13, 26, 52), (0.0, 3.0, 6.0))


def build_grid_wide():
    """2상태(TQQQ/현금) 실험용 확장 그리드 60개.

    숏 다리를 뺐으므로 탐색 폭을 넓혔다. 대신 「60개 중 최고」의 선택편향도 같이 커지므로,
    보고는 반드시 중앙값·표본외와 함께 한다 (experiment_2state.py 가 강제한다).
    """
    return _grid((8, 10, 13, 20, 26, 30, 35, 40, 45, 52), (0.0, 2.0, 4.0),
                 ((3, 10), (5, 20), (10, 30), (10, 40), (13, 40), (20, 50)), (0.0, 2.0),
                 (4, 8, 13, 26, 39, 52), (0.0, 3.0, 6.0))


# 주간 규칙 ↔ 일간 규칙 1:1 대응. 1주 = 5거래일로 환산한다.
# 같은 「달력 길이」를 같은 비용·같은 구간에서 비교하기 위한 짝이다.
WEEK_TO_DAY = {3: 15, 4: 20, 5: 25, 8: 40, 10: 50, 13: 65, 20: 100, 26: 130,
               30: 150, 35: 175, 39: 195, 40: 200, 45: 225, 50: 250, 52: 260}


def build_grid_daily():
    """2상태 일간 실험용 60개. `build_grid_wide()` 와 길이가 1:1로 짝지어진다."""
    W = WEEK_TO_DAY
    return _grid(tuple(W[n] for n in (8, 10, 13, 20, 26, 30, 35, 40, 45, 52)), (0.0, 2.0, 4.0),
                 tuple((W[f], W[s]) for f, s in ((3, 10), (5, 20), (10, 30), (10, 40), (13, 40), (20, 50))),
                 (0.0, 2.0),
                 tuple(W[n] for n in (4, 8, 13, 26, 39, 52)), (0.0, 3.0, 6.0))


def pair_weekly_daily():
    """[(주간 규칙명, 일간 규칙명)] — 길이가 같은 짝."""
    W = WEEK_TO_DAY
    out = []
    for n in (8, 10, 13, 20, 26, 30, 35, 40, 45, 52):
        for b in (0.0, 2.0, 4.0):
            out.append(("sma%d_b%.0f" % (n, b), "sma%d_b%.0f" % (W[n], b)))
    for f, s in ((3, 10), (5, 20), (10, 30), (10, 40), (13, 40), (20, 50)):
        for b in (0.0, 2.0):
            out.append(("dual%d-%d_b%.0f" % (f, s, b), "dual%d-%d_b%.0f" % (W[f], W[s], b)))
    for n in (4, 8, 13, 26, 39, 52):
        for t in (0.0, 3.0, 6.0):
            out.append(("mom%d_t%.0f" % (n, t), "mom%d_t%.0f" % (W[n], t)))
    return out


# ---------------------------------------------------------------- 변동성 게이트

def realized_vol(dates, closes, n, periods_per_year=52):
    """최근 n개 수익률의 표본표준편차(n-1)를 연율화한 %. 기준주까지만 쓴다.

    표본이 모자란 구간은 아예 넣지 않는다 (0으로 채우지 않는다).
    """
    import math
    out = {}
    rets = [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]
    for i in range(n, len(closes)):
        w = rets[i - n:i]
        m = sum(w) / n
        sd = math.sqrt(sum((x - m) ** 2 for x in w) / (n - 1))
        out[dates[i]] = sd * math.sqrt(periods_per_year) * 100.0
    return out


def vol_gate_abs(vol_by_date, threshold_pct):
    """연율 변동성이 임계치 **미만**이면 통과(True). 같으면 통과가 아니다 — 약한 쪽으로 센다.

    임계치는 적합하지 않고 이론에서 온다. 일간리셋 L배 상품의 변동성 끌림은 대략
    (L^2-L)/2 * sigma^2 이고 L=3 이면 3*sigma^2 다. 3배 위험프리미엄(연 15~18%)을
    끌림이 넘어서는 지점이 sigma ~= 22% 라서, 20~35% 구간을 훑는다.
    """
    return {d: (v < threshold_pct) for d, v in vol_by_date.items()}


def vol_gate_pct(vol_by_date, dates, pct, lookback):
    """변동성이 **직전 lookback 기간 분포의 pct 백분위 미만**이면 통과.

    절대 임계치와 달리 수준이 시대에 따라 변하는 것을 흡수한다.
    기준주 자신을 포함한 과거만 쓴다 — 미래를 보지 않는다.
    """
    ds = [d for d in dates if d in vol_by_date]
    out = {}
    for i, d in enumerate(ds):
        if i + 1 < lookback:
            continue
        w = sorted(vol_by_date[x] for x in ds[i + 1 - lookback:i + 1])
        k = int(len(w) * pct / 100.0)
        k = min(max(k, 0), len(w) - 1)
        out[d] = vol_by_date[d] < w[k]
    return out


def gate_states(states, gate):
    """추세 UP 이면서 게이트를 통과한 주만 UP. 나머지는 NEUTRAL(현금).

    게이트 값이 없는 주(워밍업 부족)는 **통과시키지 않는다** — 모르면 들어가지 않는다.
    """
    return {d: (UP if (st == UP and gate.get(d) is True) else NEUTRAL) for d, st in states.items()}


def vol_target_weight(vol_by_date, target_pct, max_weight=1.0):
    """변동성 타게팅 비중 = min(max_weight, target / 실현변동성). 0~max_weight."""
    out = {}
    for d, v in vol_by_date.items():
        out[d] = 0.0 if v <= 0 else min(max_weight, target_pct / v)
    return out


def build_vol_configs():
    """검토할 변동성 게이트 전수. 절대 임계 4 + 백분위 6 = 10개."""
    cfg = []
    for n in (13, 26):
        for th in (20.0, 25.0, 30.0, 35.0):
            cfg.append(("vol%dw<%.0f" % (n, th), n, ("abs", th, None)))
        for pct in (50.0, 70.0, 80.0):
            cfg.append(("vol%dw_p%.0f" % (n, pct), n, ("pct", pct, 104)))
    return cfg
