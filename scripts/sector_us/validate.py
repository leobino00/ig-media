#!/usr/bin/env python3
"""§9 검증 — 결과가 나빠도 그대로 적는다.

금지(제안서 §9): 잘 나온 창만 골라 보고하기, 임계치를 결과 보고 조정하기.
그래서 임계치(−10%·하위 20%·4주)는 코드에 고정하고, 연도별 결과를 전부 적는다.

산출물: scripts/sector_us/검증결과.md · 검증결과.json (fetch.py가 한계 문구에 인용한다)

사용법:
  python scripts/sector_us/validate.py scripts/sector_us                      # 가격 검증 3건
  python scripts/sector_us/validate.py scripts/sector_us --with-breadth       # 폭 검증까지 (종목 100개 수집)
  python scripts/sector_us/validate.py OUT --cache-dir /tmp/c --no-network    # 캐시로 재현
"""
import argparse, json, os, statistics, sys, datetime as dt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calc, yahoo
from fetch import UNIVERSE, BENCH, KST

FWD = 4            # 주 — 선행 구간 (고정)
DD_EVENT = -10.0   # % — QQQ 4주 하락 사건 기준 (고정)
LOW_Q = 20         # % — 폭 하위 분위 (고정)
REPRO_TOL_PCT = 0.005   # % — 재현성 허용 상대차. rs_ratio는 4자리로 저장·2자리로 표시하므로
                        #      이보다 작은 차이는 산출물의 어느 자리에도 나타나지 않는다


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.fmean(xs), 3) if xs else None


def by_year(pairs):
    """[(날짜, 값)] → {연도: 평균}."""
    g = {}
    for d, v in pairs:
        if v is not None:
            g.setdefault(d[:4], []).append(v)
    return {y: round(statistics.fmean(v), 3) for y, v in sorted(g.items())}


def load_prices(rng, cache_dir, network):
    """반환: (QQQ 주봉, {티커: R(t) 시계열}, 실패, 메타). 메타는 재현성 진단에 쓴다."""
    b = yahoo.chart(BENCH, rng=rng, cache_dir=cache_dir, network=network)
    bw = calc.to_weekly(b["rows"])
    out, errs = {}, {}
    meta = {BENCH: {"used": BENCH, "price_field": b["price_field"], "rows": len(b["rows"]),
                    "last": b["rows"][-1]}}
    for name, ticker, group, alts in UNIVERSE:
        for cand in [ticker] + alts:
            try:
                c = yahoo.chart(cand, rng=rng, cache_dir=cache_dir, network=network)
                out[ticker] = calc.ratio_series(calc.to_weekly(c["rows"]), bw)
                meta[ticker] = {"used": cand, "price_field": c["price_field"],
                                "rows": len(c["rows"]), "last": c["rows"][-1]}
                break
            except Exception as e:
                errs[ticker] = str(e)[:100]
    return bw, out, errs, meta


def v1_quadrant_forward(bw, ratios):
    """분면의 선행력 — 각 주 leading 섹터의 4주 후 QQQ 대비 초과수익 vs 전체 섹터 평균.
    초과수익은 비율 변화 그대로다: R(t+4)/R(t) − 1 (%)."""
    per_quad, all_obs, lead_obs = {}, [], []
    n = 0
    for tk, rs_in in ratios.items():
        rs_list = calc.rs_series(rs_in)
        if len(rs_list) <= FWD:
            continue
        quads = calc.quadrant_history(rs_list)
        rmap = dict(rs_in)
        dates = [d for d, _ in rs_list]
        for i, (d, q, _) in enumerate(quads):
            if i + FWD >= len(dates):
                break
            if q is None:                 # 모멘텀을 만들 수 없는 앞 4주 — 분류 불가, 비교에서 뺀다
                continue
            d2 = dates[i + FWD]
            if d not in rmap or d2 not in rmap or not rmap[d]:
                continue
            ex = (rmap[d2] / rmap[d] - 1) * 100
            n += 1
            all_obs.append((d, ex))
            per_quad.setdefault(q, []).append(ex)
            if q == "leading":
                lead_obs.append((d, ex))
    lead_y, all_y = by_year(lead_obs), by_year(all_obs)
    years = sorted(set(lead_y) & set(all_y))
    diffs = {y: round(lead_y[y] - all_y[y], 3) for y in years}
    pos = sum(1 for y in years if diffs[y] > 0)
    return {
        "n_obs": n, "horizon_weeks": FWD,
        "mean_excess_by_quadrant_pct": {k: _mean(v) for k, v in sorted(per_quad.items())},
        "n_by_quadrant": {k: len(v) for k, v in sorted(per_quad.items())},
        "leading_mean_pct": _mean([v for _, v in lead_obs]),
        "all_mean_pct": _mean([v for _, v in all_obs]),
        "leading_minus_all_pp": round((_mean([v for _, v in lead_obs]) or 0) - (_mean([v for _, v in all_obs]) or 0), 3),
        "by_year_diff_pp": diffs, "years": len(years), "years_positive": pos,
    }


def v3_drawdown_warning(bw, ratios):
    """하락 예고 여부 — QQQ 4주 −10% 이상 하락 직전 주의 leading 수·분산도가 평상시와 다른가."""
    rs_by = {tk: calc.rs_series(r) for tk, r in ratios.items()}
    weeks = {}
    for tk, rs_list in rs_by.items():
        quads = calc.quadrant_history(rs_list)
        for (d, v), (_, q, _) in zip(rs_list, quads):
            weeks.setdefault(d, {})[tk] = (v, q)
    bench = dict(bw)
    dates = sorted(weeks)
    bdates = [d for d, _ in bw]
    idx = {d: i for i, d in enumerate(bdates)}
    ev_lead, ev_disp, no_lead, no_disp, n_ev = [], [], [], [], 0
    for d in dates:
        i = idx.get(d)
        if i is None or i + FWD >= len(bdates):
            continue
        fwd = (bench[bdates[i + FWD]] / bench[d] - 1) * 100
        lead = sum(1 for v, q in weeks[d].values() if q == "leading")
        disp = calc.dispersion([v for v, _ in weeks[d].values()])
        if fwd <= DD_EVENT:
            n_ev += 1
            ev_lead.append(lead); ev_disp.append(disp)
        else:
            no_lead.append(lead); no_disp.append(disp)
    return {
        "event_rule": f"QQQ {FWD}주 수익률 <= {DD_EVENT}%",
        "n_event_weeks": n_ev, "n_other_weeks": len(no_lead),
        "leading_count_before_event": _mean(ev_lead), "leading_count_other": _mean(no_lead),
        "leading_diff": None if not ev_lead or not no_lead else round(_mean(ev_lead) - _mean(no_lead), 3),
        "dispersion_before_event": _mean(ev_disp), "dispersion_other": _mean(no_disp),
        "dispersion_diff": None if not ev_disp or not no_disp else round(_mean(ev_disp) - _mean(no_disp), 4),
    }


def breadth_weekly_history(bw, cache_dir, network, rng):
    """구성종목 주별 200일선 위 비율. 모집단은 현재 구성종목 — 생존편향이 있다 (보고에 명기)."""
    cons = yahoo.ndx_constituents(cache_dir=cache_dir, network=network)
    px, errs = yahoo.charts(cons["tickers"], rng=rng, cache_dir=cache_dir, network=network)
    above_by_date = {}
    for rows in px.values():
        vals = [v for _, v in rows]
        dates = [d for d, _ in rows]
        run = 0.0
        for i, v in enumerate(vals):
            run += v
            if i >= 200:
                run -= vals[i - 200]
            if i >= 199:
                sma = run / 200
                a, t = above_by_date.setdefault(dates[i], [0, 0])
                above_by_date[dates[i]] = [a + (1 if v > sma else 0), t + 1]
    hist = []
    for d, _ in bw:
        if d in above_by_date:
            a, t = above_by_date[d]
            if t >= 0.8 * len(cons["tickers"]):
                hist.append((d, round(a / t * 100, 2)))
    return hist, {"source": cons["source"], "grade": cons["grade"], "n": cons["n"],
                  "price_errors": len(errs), "weeks": len(hist), "range": rng}


def v2_breadth_forward(bw, hist):
    """폭의 선행력 — pct_above_sma200 하위 20% 구간 이후 4주 QQQ 수익 vs 나머지."""
    if len(hist) < 30:
        return {"error": f"주 표본 {len(hist)}개 — 비교 불가"}
    bench = dict(bw)
    bdates = [d for d, _ in bw]
    idx = {d: i for i, d in enumerate(bdates)}
    vals = sorted(v for _, v in hist)
    cut = vals[max(0, int(len(vals) * LOW_Q / 100) - 1)]
    low, rest = [], []
    for d, v in hist:
        i = idx.get(d)
        if i is None or i + FWD >= len(bdates):
            continue
        fwd = (bench[bdates[i + FWD]] / bench[d] - 1) * 100
        (low if v <= cut else rest).append((d, fwd))
    ly, ry = by_year(low), by_year(rest)
    years = sorted(set(ly) & set(ry))
    diffs = {y: round(ly[y] - ry[y], 3) for y in years}
    pooled = None if not low or not rest else round(_mean([v for _, v in low]) - _mean([v for _, v in rest]), 3)
    return {
        "cutoff_pct_above_sma200": cut, "n_low": len(low), "n_rest": len(rest),
        "years_with_low_weeks": sorted(ly), "all_years": sorted(set(ly) | set(ry)),
        "pooled_and_yearly_sign_conflict": bool(
            pooled is not None and diffs and (pooled < 0) == (min(diffs.values()) > 0)),
        "qqq_fwd4w_low_pct": _mean([v for _, v in low]), "qqq_fwd4w_rest_pct": _mean([v for _, v in rest]),
        "low_minus_rest_pp": None if not low or not rest else round(_mean([v for _, v in low]) - _mean([v for _, v in rest]), 3),
        "by_year_diff_pp": diffs, "years": len(years),
        "years_positive": sum(1 for y in years if diffs[y] > 0),
    }


def v4_stability(bw, ratios, input_dir, cache_dir, network, rng, meta1):
    """데이터 안정성 — ① 같은 기준일에 두 번 받아 재계산한 값이 같은가 ② 저장된 스냅샷 대비 과거 값 변화.

    다르면 「다르다」로 끝내지 않고 **무엇이 얼마나 달랐는지** 적는다. 어느 티커·어느 주·두 값,
    대체 티커나 가격 필드가 바뀌었는지까지 남긴다 — 다음 실행에서 원인을 찾을 수 있어야 한다.
    """
    out = {}
    a = {tk: [(d, round(v, 6)) for d, v in calc.rs_series(r)][-13:] for tk, r in ratios.items()}
    bw2, ratios2, _, meta2 = load_prices(rng, cache_dir, network)
    b = {tk: [(d, round(v, 6)) for d, v in calc.rs_series(r)][-13:] for tk, r in ratios2.items()}
    diffs = []
    for tk in sorted(set(a) | set(b)):
        x, y = dict(a.get(tk, [])), dict(b.get(tk, []))
        for d in sorted(set(x) | set(y)):
            if x.get(d) != y.get(d):
                diffs.append({"ticker": tk, "week": d, "first": x.get(d), "second": y.get(d),
                              "rel_pct": None if not x.get(d) or not y.get(d)
                              else round(abs(y[d] - x[d]) / abs(x[d]) * 100, 6)})
    src = {tk: {"first": meta1.get(tk), "second": meta2.get(tk)} for tk in sorted(set(meta1) | set(meta2))
           if meta1.get(tk, {}).get("used") != meta2.get(tk, {}).get("used")
           or meta1.get(tk, {}).get("price_field") != meta2.get(tk, {}).get("price_field")
           or meta1.get(tk, {}).get("rows") != meta2.get(tk, {}).get("rows")
           or meta1.get(tk, {}).get("last") != meta2.get(tk, {}).get("last")}
    mx = max([d["rel_pct"] for d in diffs if d["rel_pct"] is not None], default=0.0)
    out["recompute_identical"] = not diffs
    out["recompute_within_tolerance"] = (not diffs) or (mx <= REPRO_TOL_PCT and not src)
    out["recompute_tolerance_pct"] = REPRO_TOL_PCT
    out["recompute_n_diff_points"] = len(diffs)
    out["recompute_max_rel_pct"] = mx
    out["recompute_diffs_sample"] = diffs[:5]
    out["source_changed_between_runs"] = src or None
    snaps = sorted(f for f in os.listdir(input_dir) if f.startswith("sector-us-2") and f.endswith(".json")) \
        if os.path.isdir(input_dir) else []
    if not snaps:
        out["snapshot_compare"] = "비교 대상 없음 — 주간 스냅샷이 쌓이면 다음 실행에서 비교한다"
        return out
    with open(os.path.join(input_dir, snaps[-1]), encoding="utf-8") as f:
        old = json.load(f)
    worst, n = 0.0, 0
    for s in old.get("sectors", []):
        h = s.get("history_13w") or {}
        now = dict(a.get(s["ticker"], []))
        for d, v in zip(h.get("week", []), h.get("rs_ratio", [])):
            if d in now and v:
                n += 1                      # 저장된 값은 4자리 반올림 — 같은 자리에서 비교한다
                worst = max(worst, abs(round(now[d], 4) - v) / abs(v) * 100)
    out["snapshot_compare"] = {"file": snaps[-1], "compared_points": n,
                              "max_abs_rel_change_pct": round(worst, 4)}
    return out


def caveat_lines(r):
    v1, v2, v3, v4 = r["v1_quadrant"], r.get("v2_breadth"), r["v3_drawdown"], r["v4_stability"]
    q = (f"{v1['years']}년 중 {v1['years_positive']}년 양수, 전체 평균 "
         f"{v1['leading_minus_all_pp']:+}%p (leading {v1['leading_mean_pct']}% vs 전체 {v1['all_mean_pct']}%, "
         f"n={v1['n_obs']}, {FWD}주 선행)")
    if not v2 or "error" in (v2 or {}):
        b = f"검증 미실시 — {(v2 or {}).get('error', '구성종목 시계열 미확보')}"
    else:
        b = (f"하위 {LOW_Q}% 주 이후 QQQ {FWD}주 {v2['qqq_fwd4w_low_pct']}% vs 나머지 {v2['qqq_fwd4w_rest_pct']}% "
             f"(전체 차 {v2['low_minus_rest_pp']:+}%p · 하위 구간이 있던 {v2['years']}개 연도 중 "
             f"{v2['years_positive']}년 양수)")
        if v2.get("pooled_and_yearly_sign_conflict"):
            b += " — 전체와 연도별 부호가 반대다(하위 구간이 약세 연도에 몰렸다). 한쪽만 인용하지 않는다"
    if v3["n_event_weeks"] == 0:
        d = f"표본 기간에 QQQ {FWD}주 {DD_EVENT}% 이하 하락 주가 없었다 — 비교 불가"
    else:
        d = (f"하락 직전 leading 수 {v3['leading_count_before_event']}개 vs 평상시 {v3['leading_count_other']}개"
             f" (차 {v3['leading_diff']:+}개), 분산도 차 {v3['dispersion_diff']:+}"
             f" (사건 {v3['n_event_weeks']}주)")
    if v4.get("recompute_identical"):
        s = "같은 기준일 두 번 수집·재계산 완전 동일"
    elif v4.get("recompute_within_tolerance"):
        s = (f"같은 기준일 두 번 수집 — 표시 자리수 안에서 동일(최근 13주 rs_ratio "
             f"{v4.get('recompute_n_diff_points')}점이 최대 {v4.get('recompute_max_rel_pct')}% 달랐고, "
             f"허용 {v4.get('recompute_tolerance_pct')}% 이하다. 출처·가격필드·행수는 동일)")
    else:
        ex = (v4.get("recompute_diffs_sample") or [{}])[0]
        s = (f"같은 기준일 두 번 수집했을 때 최근 13주 rs_ratio {v4.get('recompute_n_diff_points')}점이 달랐다"
             f"(최대 {v4.get('recompute_max_rel_pct')}%, 예: {ex.get('ticker')} {ex.get('week')} "
             f"{ex.get('first')}→{ex.get('second')})"
             + (f" · 출처가 바뀐 티커 {list(v4['source_changed_between_runs'])}"
                if v4.get("source_changed_between_runs") else " · 출처·가격필드·행수는 동일"))
    sc = v4.get("snapshot_compare")
    s += f" · 스냅샷 대비 과거 rs_ratio 최대 변화 {sc['max_abs_rel_change_pct']}% ({sc['compared_points']}점)" \
        if isinstance(sc, dict) else f" · {sc}"
    return {"quadrant": q, "breadth": b, "drawdown": d, "stability": s}


def _snap_line(sc):
    if not isinstance(sc, dict):
        return sc
    return (f"{sc['file']}의 과거 rs_ratio {sc['compared_points']}점과 비교 — "
            f"최대 상대 변화 {sc['max_abs_rel_change_pct']}%")


def to_markdown(r):
    c = r["caveat_lines"]
    L = ["# us-sector-strength 검증 결과 (§9)", "",
         f"| 실행 | {r['run_at']} · 계산정의 v{calc.CALC_VERSION} · 표본 {r['range']} |", "|---|---|",
         f"| 기준 주 | {r['first_week']} ~ {r['last_week']} ({r['n_weeks']}주) |",
         f"| 고정 임계치 | 선행 {FWD}주 · 하락 사건 {DD_EVENT}% · 폭 하위 {LOW_Q}% |",
         f"| 수집 실패 | {r['fetch_errors'] or '없음'} |", "",
         "결과가 나빠도 그대로 적는다. 창을 골라 싣지 않는다 — 연도별 수치를 전부 둔다.", "",
         "## 1. 분면의 선행력", "",
         "| 분면 | 4주 후 QQQ 대비 초과수익 평균 | 관측 수 |", "|---|---|---|"]
    v1 = r["v1_quadrant"]
    for q, m in v1["mean_excess_by_quadrant_pct"].items():
        L.append(f"| {q} | {m}% | {v1['n_by_quadrant'][q]} |")
    L += ["", f"- leading − 전체 평균 = **{v1['leading_minus_all_pp']:+}%p**",
          f"- 연도별 차이(%p): " + " · ".join(f"{y} {d:+}" for y, d in v1["by_year_diff_pp"].items()),
          f"- 양수 연도 {v1['years_positive']}/{v1['years']}", "",
          "## 2. 폭의 선행력", ""]
    v2 = r.get("v2_breadth")
    if not v2 or "error" in v2:
        L.append(f"- 미실시: {(v2 or {}).get('error', '구성종목 시계열 미확보')} "
                 f"(`--with-breadth`로 실행하면 채워진다)")
    else:
        L += [f"- 하위 {LOW_Q}% 기준값 = 200일선 위 {v2['cutoff_pct_above_sma200']}%",
              f"- 이후 QQQ 4주 수익: 하위 구간 {v2['qqq_fwd4w_low_pct']}% (n={v2['n_low']}) vs 나머지 "
              f"{v2['qqq_fwd4w_rest_pct']}% (n={v2['n_rest']}) → 차 **{v2['low_minus_rest_pp']:+}%p**",
              f"- 연도별 차이(%p): " + " · ".join(f"{y} {d:+}" for y, d in v2["by_year_diff_pp"].items())
              + f" (하위 구간이 나타난 연도만. 표본 전체 연도는 {', '.join(v2.get('all_years', []))})",
              f"- 양수 연도 {v2['years_positive']}/{v2['years']}"
              + (" · **전체 차이와 연도별 부호가 반대다** — 하위 구간이 약세 연도에 몰린 결과이고, "
                 "한쪽만 인용하면 안 된다" if v2.get("pooled_and_yearly_sign_conflict") else ""),
              f"- 모집단: {r['breadth_meta']['source']} ({r['breadth_meta']['grade']}) 현재 구성종목 "
              f"{r['breadth_meta']['n']}종목 · 주 표본 {r['breadth_meta']['weeks']}개 — **생존편향이 있다**"]
    v3 = r["v3_drawdown"]
    L += ["", "## 3. 하락 예고 여부", "",
          f"- 사건 정의: {v3['event_rule']} · 사건 {v3['n_event_weeks']}주 / 그 외 {v3['n_other_weeks']}주",
          f"- 직전 주 leading 섹터 수: 사건 {v3['leading_count_before_event']} vs 그 외 {v3['leading_count_other']} "
          f"(차 {v3['leading_diff']})",
          f"- 직전 주 분산도: 사건 {v3['dispersion_before_event']} vs 그 외 {v3['dispersion_other']} "
          f"(차 {v3['dispersion_diff']})",
          f"- 사건 {v3['n_event_weeks']}주는 작은 표본이다. 차이의 부호를 근거로 예고력을 주장하지 않는다.", "",
          "## 4. 데이터 안정성", "",
          f"- 같은 기준일 두 번 수집·재계산: "
          + ("완전 동일" if r["v4_stability"].get("recompute_identical")
             else f"표시 자리수 안에서 동일 (허용 {REPRO_TOL_PCT}%)" if r["v4_stability"].get("recompute_within_tolerance")
             else "불일치")
          + ("" if r["v4_stability"].get("recompute_identical") else
             f" — 다른 점 {r['v4_stability'].get('recompute_n_diff_points')}개 · 최대 상대차 "
             f"{r['v4_stability'].get('recompute_max_rel_pct')}% · 예 {r['v4_stability'].get('recompute_diffs_sample')}"
             f" · 출처 변화 {r['v4_stability'].get('source_changed_between_runs') or '없음'}"),
          f"- 스냅샷 대비: {_snap_line(r['v4_stability'].get('snapshot_compare'))}",
          "- Yahoo 수정종가는 배당·분할 시 과거 값이 소급 변경된다. 그래서 주간 스냅샷을 덮어쓰지 않는다.", "",
          "## md 꼬리에 들어가는 문구", ""]
    for k in ("quadrant", "breadth", "drawdown", "stability"):
        L.append(f"- **{k}**: {c[k]}")
    return "\n".join(L) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description="§9 검증")
    p.add_argument("out_dir", nargs="?", default=os.path.dirname(os.path.abspath(__file__)))
    p.add_argument("--range", default="10y", help="가격 표본 구간 (Yahoo range)")
    p.add_argument("--breadth-range", default="6y")
    p.add_argument("--with-breadth", action="store_true", help="구성종목 100종목을 받아 폭 검증까지 한다")
    p.add_argument("--input-dir", default="claude/advisor/월간판정/입력", help="스냅샷 비교용")
    p.add_argument("--cache-dir", default=None)
    p.add_argument("--no-network", action="store_true")
    a = p.parse_args(argv)
    network = not a.no_network

    bw, ratios, errs, meta1 = load_prices(a.range, a.cache_dir, network)
    weeks = sorted({d for r in ratios.values() for d, _ in r})
    r = {"run_at": dt.datetime.now(KST).replace(microsecond=0).isoformat(),
         "calc_version": calc.CALC_VERSION, "range": a.range,
         "first_week": weeks[0] if weeks else None, "last_week": weeks[-1] if weeks else None,
         "n_weeks": len(weeks), "fetch_errors": errs,
         "v1_quadrant": v1_quadrant_forward(bw, ratios),
         "v3_drawdown": v3_drawdown_warning(bw, ratios)}
    if a.with_breadth:
        try:
            hist, meta = breadth_weekly_history(bw, a.cache_dir, network, a.breadth_range)
            r["breadth_meta"] = meta
            r["v2_breadth"] = v2_breadth_forward(bw, hist)
        except Exception as e:
            r["breadth_meta"] = None
            r["v2_breadth"] = {"error": str(e)[:200]}
    else:
        r["breadth_meta"] = None
        r["v2_breadth"] = {"error": "--with-breadth 없이 실행 — 구성종목 시계열 미수집"}
    r["v4_stability"] = v4_stability(bw, ratios, a.input_dir, a.cache_dir, network, a.range, meta1)
    r["caveat_lines"] = caveat_lines(r)

    os.makedirs(a.out_dir, exist_ok=True)
    with open(os.path.join(a.out_dir, "검증결과.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=1)
    md = to_markdown(r)
    with open(os.path.join(a.out_dir, "검증결과.md"), "w", encoding="utf-8") as f:
        f.write(md)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
