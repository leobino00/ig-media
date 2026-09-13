# -*- coding: utf-8 -*-
"""QQQ 주간 관측 — 산출물 생성.

`data/qqq_weekly.csv` 를 읽어 `출력/qqq-weekly-latest.{md,json}` 과 기준일 스냅샷을 낸다.
사실만 낸다. 판정하지 않는다 — 매수·매도·비중·전망을 쓰지 않는다.
네트워크를 쓰지 않는다. 저장소 밖의 어떤 파일도 읽거나 쓰지 않는다.

    python3 scripts/qqq_weekly/observe.py
    python3 scripts/qqq_weekly/observe.py --csv PATH --out DIR
"""

import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import calc
import load

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CSV = os.path.join(HERE, "data", "qqq_weekly.csv")
DEFAULT_OUT = os.path.join(HERE, "출력")

SYMBOL = "QQQ"
SMA_WEEKS = (10, 30, 40)
RETURN_WEEKS = (4, 13, 26, 52)
VOL_WEEKS = (13, 52)

BOUNDARY = (
    "이 파일은 **관측**이다. 판정하지 않는다. "
    "어드바이저 5단계 프로토콜·판정기록부·월간 판정과 무관하며, 그 입력으로 쓰이지 않는다."
)


def fmt(x, nd=2, suffix=""):
    return "결측" if x is None else ("%.*f%s" % (nd, x, suffix))


def flag(b):
    return "결측" if b is None else ("O" if b else "X")


# ------------------------------------------------------------------ 관측 산출

def observe(dates, closes, report):
    rets = calc.weekly_returns(closes)
    dd = calc.drawdown_series(closes)
    mdd, mdd_pi, mdd_ti = calc.max_drawdown(closes)

    missing = []
    missing_detail = {}

    def need(name, value, why):
        if value is None:
            missing.append(name)
            missing_detail[name] = why
        return value

    trend = {}
    for n in SMA_WEEKS:
        s = calc.sma(closes, n)
        trend["sma_%dw" % n] = s
        trend["above_sma_%dw" % n] = calc.above(closes[-1], s)
        need("sma_%dw" % n, s, "관측 %d주 < %d주" % (len(closes), n))

    returns = {}
    for n in RETURN_WEEKS:
        r = calc.trailing_return(closes, n)
        returns["ret_%dw_pct" % n] = r
        need("ret_%dw_pct" % n, r, "관측 %d주 < %d+1주" % (len(closes), n))

    vol = {}
    for n in VOL_WEEKS:
        v = calc.annualized_vol(rets, n)
        vol["vol_%dw_annualized_pct" % n] = v
        need("vol_%dw_annualized_pct" % n, v, "주간 등락률 %d개 < %d개" % (len(rets), n))

    hi52, lo52 = calc.rolling_high_low(closes, 52)
    ath = max(closes)
    ath_i = closes.index(ath)

    latest = {
        "date": dates[-1].isoformat(),
        "close": closes[-1],
        "week_return_pct": rets[-1] if rets else None,
        "prev_date": dates[-2].isoformat() if len(dates) > 1 else None,
    }

    drawdown = {
        "from_all_time_high_pct": dd[-1],
        "all_time_high": ath,
        "all_time_high_date": dates[ath_i].isoformat(),
        "weeks_since_all_time_high": len(closes) - 1 - ath_i,
        "high_52w": hi52,
        "low_52w": lo52,
        "pct_from_high_52w": calc.pct_change(closes[-1], hi52),
        "pct_from_low_52w": calc.pct_change(closes[-1], lo52),
        "max_drawdown_pct": mdd,
        "max_drawdown_peak_date": dates[mdd_pi].isoformat() if mdd_pi is not None else None,
        "max_drawdown_trough_date": dates[mdd_ti].isoformat() if mdd_ti is not None else None,
    }
    if hi52 is None:
        need("high_52w", None, "관측 %d주 < 52주" % len(closes))

    up = [r for r in rets if r is not None and r > 0.0]
    distribution = {
        "weeks": len(rets),
        "up_week_ratio_pct": (100.0 * len(up) / len(rets)) if rets else None,
        "mean_weekly_pct": calc.mean([r for r in rets if r is not None]),
        "stdev_weekly_pct": calc.stdev_sample([r for r in rets if r is not None]),
        "p05_weekly_pct": calc.percentile(rets, 5),
        "p50_weekly_pct": calc.percentile(rets, 50),
        "p95_weekly_pct": calc.percentile(rets, 95),
        "worst_week_pct": min([r for r in rets if r is not None], default=None),
        "best_week_pct": max([r for r in rets if r is not None], default=None),
    }

    episodes = {
        "%d" % int(t): calc.drawdown_episodes(dates, closes, t)
        for t in calc.DD_THRESHOLDS
    }

    return {
        "as_of": dates[-1].isoformat(),
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "symbol": SYMBOL,
        "boundary": "관측 전용. 판정하지 않는다. 어드바이저 프로토콜과 무관하다",
        "series": {
            "kind": "weekly_close",
            "cadence": "주간 (금요일 종가, 휴장주는 직전 거래일)",
            "dividend_adjusted": False,
            "currency": "USD",
            "source": "사용자 제공 파일 (data/qqq_weekly.출처.md)",
        },
        "input": report,
        "span": {
            "first_date": dates[0].isoformat(),
            "last_date": dates[-1].isoformat(),
            "weeks": len(closes),
            "years": calc.span_years(dates),
            "cagr_price_only_pct": calc.cagr(dates, closes),
        },
        "latest": latest,
        "trend": trend,
        "returns": returns,
        "volatility": vol,
        "drawdown": drawdown,
        "distribution": distribution,
        "history": {
            "annual": calc.annual_returns(dates, closes),
            "drawdown_episodes": episodes,
        },
        "missing": missing,
        "missing_detail": missing_detail,
        "caveats": caveats(report),
        "version": calc.CALC_VERSION,
    }


def caveats(report):
    out = [
        "**배당이 반영되지 않았다 (2026-09-13 확인).** 벤더(Alpha Vantage) 미수정 종가와 "
        "1028주 전부가 소수점까지 일치했고, 같은 날짜의 수정종가와는 평균 7.94% 차이가 났다. "
        "따라서 이 파일의 누적 등락률·CAGR은 배당 재투자분만큼 실제 총수익보다 낮다. "
        "낙폭과 변동성은 거의 영향받지 않는다.",
        "**주간 종가만 본다.** 주중 고가·저가를 모르므로 낙폭은 주간 종가 기준이고, "
        "일중·일간 기준 실제 낙폭보다 얕게 측정된다.",
        "**단일 출처이고 대조하지 않았다.** 거래소·운용사 원자료와 대조한 기록이 없다.",
        "**환율을 반영하지 않는다.** 전부 달러 기준이다.",
        "**구간이 2007-01-05에서 시작한다.** 그 이전의 낙폭(2000~2002년 등)은 이 관측에 없다. "
        "「전 구간 최대 낙폭」은 QQQ 상장 이래 최대가 아니라 이 파일 구간 안에서의 최대다.",
    ]
    if report.get("gaps"):
        out.append("**결측 주 의심 %d건.** 보간하지 않았다 — `input.gaps` 참조." % len(report["gaps"]))
    return out


# ------------------------------------------------------------------ md 렌더

def render_md(o):
    L = []
    A = L.append
    sp, lt, dd, tr, rt, vo, di = (
        o["span"], o["latest"], o["drawdown"], o["trend"],
        o["returns"], o["volatility"], o["distribution"],
    )

    A("# QQQ 주간 관측 — %s" % o["as_of"])
    A("")
    A("생성 %s · 계산정의 v%s · 입력 %d주 (%s ~ %s)"
      % (o["generated_at"], o["version"], sp["weeks"], sp["first_date"], sp["last_date"]))
    A("")
    A("## 경계")
    A("")
    A(BOUNDARY)
    A("")
    A("## 관측")
    A("")
    A("### 기준주")
    A("")
    A("| 항목 | 값 |")
    A("|---|---|")
    A("| 기준일 | %s |" % lt["date"])
    A("| 종가 | %s |" % fmt(lt["close"]))
    A("| 주간 등락률 | %s |" % fmt(lt["week_return_pct"], 2, "%"))
    A("")
    A("### 이동평균 대비 위치")
    A("")
    A("| 구간 | 이동평균 | 종가가 위(strict) |")
    A("|---|---|---|")
    for n in SMA_WEEKS:
        A("| %d주 | %s | %s |" % (n, fmt(tr["sma_%dw" % n]), flag(tr["above_sma_%dw" % n])))
    A("")
    A("### 누적 등락률")
    A("")
    A("| 구간 | 등락률 |")
    A("|---|---|")
    for n in RETURN_WEEKS:
        A("| %d주 | %s |" % (n, fmt(rt["ret_%dw_pct" % n], 2, "%")))
    A("| 전 구간 연평균(배당 미반영) | %s |" % fmt(sp["cagr_price_only_pct"], 2, "%"))
    A("")
    A("### 변동성 (주간 등락률 표본표준편차 × √52)")
    A("")
    A("| 구간 | 연율화 |")
    A("|---|---|")
    for n in VOL_WEEKS:
        A("| %d주 | %s |" % (n, fmt(vo["vol_%dw_annualized_pct" % n], 2, "%")))
    A("")
    A("### 낙폭")
    A("")
    A("| 항목 | 값 |")
    A("|---|---|")
    A("| 사상 최고 종가 대비 | %s |" % fmt(dd["from_all_time_high_pct"], 2, "%"))
    A("| 사상 최고 종가 | %s (%s, %d주 전) |"
      % (fmt(dd["all_time_high"]), dd["all_time_high_date"], dd["weeks_since_all_time_high"]))
    A("| 52주 최고 대비 | %s |" % fmt(dd["pct_from_high_52w"], 2, "%"))
    A("| 52주 최저 대비 | %s |" % fmt(dd["pct_from_low_52w"], 2, "%"))
    A("| 전 구간 최대 낙폭 | %s (%s → %s) |"
      % (fmt(dd["max_drawdown_pct"], 2, "%"), dd["max_drawdown_peak_date"], dd["max_drawdown_trough_date"]))
    A("")
    A("### 주간 등락률 분포 (전 구간 %d주)" % di["weeks"])
    A("")
    A("| 항목 | 값 |")
    A("|---|---|")
    A("| 상승 주 비율 (strict >0) | %s |" % fmt(di["up_week_ratio_pct"], 1, "%"))
    A("| 평균 | %s |" % fmt(di["mean_weekly_pct"], 3, "%"))
    A("| 표본표준편차 | %s |" % fmt(di["stdev_weekly_pct"], 3, "%"))
    A("| 5 / 50 / 95 백분위 | %s / %s / %s |"
      % (fmt(di["p05_weekly_pct"], 2, "%"), fmt(di["p50_weekly_pct"], 2, "%"), fmt(di["p95_weekly_pct"], 2, "%")))
    A("| 최저 / 최고 주 | %s / %s |"
      % (fmt(di["worst_week_pct"], 2, "%"), fmt(di["best_week_pct"], 2, "%")))
    A("")
    A("### 연도별 등락률")
    A("")
    A("| 연도 | 마지막 관측 | 종가 | 등락률 |")
    A("|---|---|---|---|")
    for r in o["history"]["annual"]:
        note = (" (%s)" % r["partial_reason"]) if r["partial"] else ""
        A("| %d%s | %s | %s | %s |"
          % (r["year"], note, r["last_date"], fmt(r["last_close"]), fmt(r["return_pct"], 2, "%")))
    A("")
    for t in calc.DD_THRESHOLDS:
        eps = o["history"]["drawdown_episodes"]["%d" % int(t)]
        A("### 주간 종가 낙폭 %d%% 이하 구간 — %d건" % (int(t), len(eps)))
        A("")
        if not eps:
            A("해당 구간 없음.")
            A("")
            continue
        A("| 고점 | 저점 | 낙폭 | 하락 주 | 회복 | 회복까지 주 |")
        A("|---|---|---|---|---|---|")
        for e in eps:
            rec = e["recovery_date"] if e["recovered"] else "미회복"
            wtr = str(e["weeks_trough_to_recovery"]) if e["recovered"] else "—"
            A("| %s (%s) | %s (%s) | %s | %d | %s | %s |"
              % (e["peak_date"], fmt(e["peak_close"]), e["trough_date"], fmt(e["trough_close"]),
                 fmt(e["drawdown_pct"], 2, "%"), e["weeks_peak_to_trough"], rec, wtr))
        A("")

    A("## 입력 점검")
    A("")
    A("| 항목 | 값 |")
    A("|---|---|")
    A("| 행 수 | %d |" % o["input"]["row_count"])
    A("| 요일 분포 | %s |" % ", ".join("%s %d" % (k, v) for k, v in o["input"]["weekday_counts"].items()))
    A("| 결측 주 의심 | %d건 |" % len(o["input"]["gaps"]))
    A("| 배당 반영 여부 | 미반영 (2026-09-13 대조 확인) |")
    A("")
    A("## 결측")
    A("")
    if not o["missing"]:
        A("없음.")
    else:
        for k in o["missing"]:
            A("- `%s` — %s" % (k, o["missing_detail"][k]))
    A("")
    A("## 한계")
    A("")
    for c in o["caveats"]:
        A("- %s" % c)
    A("")
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ 진입점

def main(argv=None):
    ap = argparse.ArgumentParser(description="QQQ 주간 관측 (판정하지 않는다)")
    ap.add_argument("--csv", default=DEFAULT_CSV)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--no-snapshot", action="store_true", help="기준일 스냅샷을 쓰지 않는다")
    a = ap.parse_args(argv)

    try:
        dates, closes, report = load.load(a.csv)
    except load.LoadError as e:
        sys.stderr.write("입력 오류: %s\n" % e)
        return 2

    o = observe(dates, closes, report)
    os.makedirs(a.out, exist_ok=True)

    md_path = os.path.join(a.out, "qqq-weekly-latest.md")
    js_path = os.path.join(a.out, "qqq-weekly-latest.json")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(render_md(o))
    with open(js_path, "w", encoding="utf-8") as fh:
        json.dump(o, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    written = [md_path, js_path]

    if not a.no_snapshot:
        snap = os.path.join(a.out, "qqq-weekly-%s.json" % o["as_of"])
        with open(snap, "w", encoding="utf-8") as fh:
            json.dump(o, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
        written.append(snap)

    for p in written:
        sys.stdout.write("썼다: %s\n" % p)
    if o["missing"]:
        sys.stdout.write("결측 %d건: %s\n" % (len(o["missing"]), ", ".join(o["missing"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
