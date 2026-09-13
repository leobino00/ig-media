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
