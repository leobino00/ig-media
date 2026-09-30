"""QQQ 바이앤홀드 대비 전략 백테스트.

규칙: t일 종가로 신호 → t+1일 수익률부터 적용 (look-ahead 없음).
레버리지 L배 일간 리셋 합성: r_L = L*r - (L-1)*(rf+spread) - fee.
QQQ 배당은 0.6%/년 일할로 가산 (모든 QQQ 노출에 동일 적용).
"""
import numpy as np, pandas as pd, os, sys

D = os.path.join(os.path.dirname(__file__), "data")
TBILL = {1999: 4.64, 2000: 5.82, 2001: 3.39, 2002: 1.60, 2003: 1.01, 2004: 1.37, 2005: 3.15,
         2006: 4.73, 2007: 4.36, 2008: 1.37, 2009: 0.15, 2010: 0.14, 2011: 0.05, 2012: 0.09,
         2013: 0.06, 2014: 0.03, 2015: 0.05, 2016: 0.32, 2017: 0.93, 2018: 1.94, 2019: 2.06,
         2020: 0.37, 2021: 0.04, 2022: 2.02, 2023: 5.07, 2024: 4.97, 2025: 4.20, 2026: 3.80}
DIV = 0.006
SPREAD = 0.005      # 레버리지 ETF 내재 차입 스프레드
FEE_L = 0.0095      # TQQQ/QLD 보수
COST = 0.001        # 매매 1회 편도 비용 (스프레드+수수료)


def load(sym):
    df = pd.read_csv(os.path.join(D, f"{sym}.csv"), parse_dates=["date"]).set_index("date")["close"]
    return df[~df.index.duplicated()].sort_index()


def base():
    q = load("QQQ")
    r = q.pct_change().fillna(0.0)
    rf = pd.Series([TBILL[d.year] / 100 for d in r.index], index=r.index) / 252
    rq = r + DIV / 252
    out = pd.DataFrame({"px": q, "r": rq, "rf": rf})
    for s in ("TLT", "GLD"):
        try:
            out[s] = load(s).pct_change().reindex(out.index)
        except FileNotFoundError:
            pass
    return out


def lev(df, L):
    if L == 1:
        return df.r
    return L * df.r - (L - 1) * (df.rf + SPREAD / 252) - FEE_L / 252


def run(df, w, sleeves):
    """w: DataFrame 비중(종가 기준 목표). sleeves: {col: 일수익률 Series}. 신호는 하루 밀어 적용."""
    w = w.fillna(0.0)
    wexe = w.shift(1).fillna(0.0)
    ret = sum(wexe[c] * sleeves[c] for c in w.columns)
    ret = ret + (1 - wexe.sum(axis=1)) * df.rf          # 남는 비중은 현금(T-bill)
    turn = (wexe - wexe.shift(1).fillna(0.0)).abs().sum(axis=1)
    ret = ret - turn * COST
    return ret, turn


def stats(ret, rf, turn=None, name=""):
    eq = (1 + ret).cumprod()
    yrs = len(ret) / 252
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    dd = eq / eq.cummax() - 1
    vol = ret.std() * np.sqrt(252)
    ex = ret - rf
    sharpe = ex.mean() / ex.std() * np.sqrt(252)
    neg = ex[ex < 0]
    sortino = ex.mean() * 252 / (np.sqrt((neg ** 2).sum() / len(ex)) * np.sqrt(252))
    # 최장 수중 기간
    under = (dd < 0).astype(int)
    grp = (under.diff() != 0).cumsum()
    longest = under.groupby(grp).sum().max() / 252
    s = dict(name=name, CAGR=cagr, Vol=vol, MDD=dd.min(), Sharpe=sharpe, Sortino=sortino,
             Calmar=cagr / -dd.min(), UW_yrs=longest, Mult=eq.iloc[-1])
    if turn is not None:
        s["Trades/yr"] = (turn > 1e-9).sum() / yrs
    return s


def sim(df, targets, sleeves, tax=0.0, cost=COST):
    """드리프트 허용 시뮬레이터.
    targets: DataFrame(index=df.index, columns=sleeve명). 행 전체가 NaN이면 그날 매매 없음(드리프트).
             값이 있는 행 = t일 종가 판단 → t+1일 시가(=t일 종가 근사)에 그 비중으로 리밸런싱.
    나머지는 현금(T-bill). tax>0이면 평균단가로 실현이익 추적, 연말 순실현이익×tax 납부,
    마지막 날 전량 청산 과세(바이앤홀드와 동등 비교용).
    """
    cols = list(targets.columns)
    R = np.column_stack([sleeves[c].reindex(df.index).fillna(0.0).values for c in cols])
    rf = df.rf.values
    T = targets.values
    n, k = R.shape
    val = np.zeros(k); basis = np.zeros(k); cash = 1.0
    out = np.empty(n); turn = np.zeros(n); realized = 0.0
    years = df.index.year.values
    pending = None
    for t in range(n):
        # 1) 전일 결정 체결 (t일 수익률 전에)
        if pending is not None:
            tot = val.sum() + cash
            tgt = pending * tot
            delta = tgt - val
            for j in range(k):
                if delta[j] < 0 and val[j] > 0:          # 매도분 실현손익
                    frac = -delta[j] / val[j]
                    realized += frac * (val[j] - basis[j])
                    basis[j] *= (1 - frac)
                elif delta[j] > 0:
                    basis[j] += delta[j]
            c = np.abs(delta).sum() * cost
            val = tgt.copy(); cash = tot - tgt.sum() - c
            turn[t] = np.abs(delta).sum() / tot
            pending = None
        # 2) 수익률 반영
        val = val * (1 + R[t]); cash = cash * (1 + rf[t])
        # 3) 연말 과세
        if tax and (t == n - 1 or years[t + 1] != years[t]):
            if realized > 0:
                cash -= realized * tax
            realized = 0.0
        out[t] = val.sum() + cash
        # 4) 오늘 종가 판단
        if not np.all(np.isnan(T[t])):
            pending = np.nan_to_num(T[t])
    if tax:   # 종료 시 전량 청산
        out[-1] -= max(0.0, (val - basis).sum()) * tax
    eq = pd.Series(out, index=df.index)
    ret = eq.pct_change().fillna(eq.iloc[0] - 1)
    return ret, pd.Series(turn, index=df.index)
