#!/usr/bin/env python3
"""us-sector-strength — 미국 섹터의 QQQ 대비 상대강도·분면·폭을 주간으로 관측한다.

판단하지 않는다. 사실과 플래그만 낸다 (제안서 §3 · R5). 판정은 어드바이저가 한다.
산출물: <out_dir>/sector-us-latest.md · sector-us-latest.json · sector-us-YYYY-MM-DD.json

사용법:
  python scripts/sector_us/fetch.py "claude/advisor/월간판정/입력"
  python scripts/sector_us/fetch.py OUT --cache-dir /tmp/c --no-network   # 캐시만으로 재현
  python scripts/sector_us/fetch.py OUT --no-breadth                      # 폭 지표 생략
"""
import argparse, json, os, sys, datetime as dt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calc, yahoo
from lint_no_judgment import scan as lint_scan

PROGRAM = "us-sector-strength"
PROGRAM_VERSION = "0.1"
BENCH = "QQQ"
SECTOR_RANGE = "5y"        # 26주 워밍업 + 분산도 2년 백분위용 (제안서 R8의 2y는 최소값)
BREADTH_RANGE = "2y"       # 200일선 + 52주 고저 판정에 필요한 최소 구간 + 4주 전 시점

# R2 — 유니버스 14. 이 이상 늘리지 않는다 (출력이 길어지면 루틴이 읽는 비용이 는다).
UNIVERSE = [
    ("반도체",     "SMH",  "nasdaq_sub", ["SOXX"]),
    ("소프트웨어", "IGV",  "nasdaq_sub", []),
    ("바이오",     "XBI",  "nasdaq_sub", []),
    ("기술",       "XLK",  "gics", []),
    ("헬스케어",   "XLV",  "gics", []),
    ("금융",       "XLF",  "gics", []),
    ("임의소비재", "XLY",  "gics", []),
    ("커뮤니케이션", "XLC", "gics", []),
    ("산업재",     "XLI",  "gics", []),
    ("필수소비재", "XLP",  "gics", []),
    ("에너지",     "XLE",  "gics", []),
    ("유틸리티",   "XLU",  "gics", []),
    ("리츠",       "XLRE", "gics", []),
    ("소재",       "XLB",  "gics", []),
]

# R4 — Yahoo assetProfile.sector(자체 분류) → 위 유니버스 티커. GICS와 완전히 같지 않다.
# 반도체·소프트웨어·바이오는 Yahoo에서 각각 Technology·Technology·Healthcare로 오므로
# 하위섹터 3종으로는 매핑되지 않는다. 이 한계를 json의 note에 남긴다.
YAHOO_SECTOR_TO_TICKER = {
    "Technology": "XLK", "Healthcare": "XLV", "Financial Services": "XLF",
    "Financial": "XLF", "Consumer Cyclical": "XLY", "Communication Services": "XLC",
    "Industrials": "XLI", "Consumer Defensive": "XLP", "Energy": "XLE",
    "Utilities": "XLU", "Real Estate": "XLRE", "Basic Materials": "XLB",
}

KST = dt.timezone(dt.timedelta(hours=9))
VALIDATION_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "검증결과.json")


def load_validation():
    """§9 검증 결과를 한계 문구에 인용한다. 없으면 '미실시'라고 적는다 — 채워 넣지 않는다."""
    try:
        with open(VALIDATION_JSON, encoding="utf-8") as f:
            v = json.load(f)
        return {"as_of": v.get("run_at"), "lines": v.get("caveat_lines") or {}}
    except Exception:
        return {"as_of": None, "lines": {}}


def fetch_sectors(bench, cache_dir, network):
    """14섹터 일봉 → 주봉 → §5 지표. 실패한 섹터는 None으로 남긴다."""
    bench_weekly = calc.to_weekly(bench["rows"])
    sectors, rs_by_ticker, errors = [], {}, {}
    for name, ticker, group, alts in UNIVERSE:
        used, rows, err = None, None, None
        for cand in [ticker] + alts:
            try:
                rows = yahoo.chart(cand, rng=SECTOR_RANGE, cache_dir=cache_dir, network=network)["rows"]
                used = cand
                break
            except Exception as e:
                err = str(e)[:120]
        rec = {"name": name, "ticker": ticker, "group": group}
        if rows is None:
            errors[ticker] = err
            rec.update({"ticker_used": None, "rs_ratio": None, "rs_chg_4w": None,
                        "rs_momentum": None, "quadrant": None, "weeks_in_quadrant": None,
                        "quadrant_changed": None, "rs_dd_from_26w_high": None, "rs_dd_15": None,
                        "rs_up_from_26w_low": None, "rs_up_30": None, "history_13w": None,
                        "missing_reason": err})
            sectors.append(rec)
            continue
        ratios = calc.ratio_series(calc.to_weekly(rows), bench_weekly)
        rs_list = calc.rs_series(ratios)
        m = calc.sector_metrics(ratios, rs_list)
        if m is None:
            errors[ticker] = f"{used}: 주봉 {len(ratios)}주 — 26주 워밍업 미달"
            rec.update({"ticker_used": used, "rs_ratio": None, "quadrant": None,
                        "missing_reason": errors[ticker]})
            sectors.append(rec)
            continue
        rs_by_ticker[ticker] = rs_list
        rec["ticker_used"] = used
        rec.update(m)
        sectors.append(rec)
    return bench_weekly, sectors, rs_by_ticker, errors


def breadth_block(cache_dir, network, as_of=None):
    """R3 — 나스닥100 구성종목 폭. 구성종목 목록이나 커버리지가 모자라면 결측."""
    try:
        cons = yahoo.ndx_constituents(cache_dir=cache_dir, network=network)
    except Exception as e:
        return None, {"constituents": str(e)[:200]}
    px, errs = yahoo.charts(cons["tickers"], rng=BREADTH_RANGE, cache_dir=cache_dir, network=network)
    stale = 0
    if as_of:                       # 마지막 거래일이 기준일과 다른 종목은 쓰지 않는다 (기준일 혼선 방지)
        for s in [s for s, rows in px.items() if rows[-1][0] != as_of]:
            errs[s] = f"마지막 거래일 {px[s][-1][0]} ≠ 기준일 {as_of}"
            del px[s]
            stale += 1
    pct, n_pct = calc.pct_above_sma200(px)
    pct_4w, _ = calc.pct_above_sma200(px, offset=20)
    nh, nl, n_hl = calc.new_highs_lows(px)
    n_req = len(cons["tickers"])
    coverage = round(n_pct / n_req * 100, 1) if n_req else None
    block = {
        "universe": "NDX-100 constituents", "n": n_req, "n_priced": n_pct,
        "coverage_pct": coverage,
        "constituents_source": cons["source"], "constituents_grade": cons["grade"],
        "constituents_as_of": cons.get("as_of"), "constituents_url": cons.get("url"),
        "pct_above_sma200": pct, "pct_above_sma200_4w_ago": pct_4w,
        "new_highs_5d": nh if n_hl else None, "new_lows_5d": nl if n_hl else None,
        "nh_nl_ratio": calc.nh_nl_ratio(nh, nl) if n_hl else None,
        "n_52w_judged": n_hl,
        "price_fetch_errors": len(errs),
        "price_fetch_failed": sorted(errs)[:10],
        "excluded_stale_last_bar": stale,
        "constituents_attempt_errors": cons.get("attempt_errors") or None,
    }
    missing = {}
    if coverage is not None and coverage < 80:
        block["pct_above_sma200"] = block["pct_above_sma200_4w_ago"] = None
        block["nh_nl_ratio"] = block["new_highs_5d"] = block["new_lows_5d"] = None
        missing["breadth"] = f"구성종목 가격 커버리지 {coverage}% (<80%) — 폭 지표 결측 처리"
    if cons["grade"] == "C":
        missing["breadth_source_grade_C"] = (
            f"구성종목 목록을 {cons['source']}에서 받았다 — 등급 C(출처 등급표상 결측 취급). 값은 참고만")
    return block, missing


def holdings_block(out_dir, sectors, args):
    """R4 · §8-1 — holdings.json이 있으면 티커에 섹터를 붙여 해당 섹터 행을 복사한다.
    평단·손익은 계산하지 않는다 (T4는 어드바이저가 한다)."""
    path = args.holdings or os.path.join(out_dir, "holdings.json")
    if not os.path.exists(path):
        return [], {"source": None, "note": "holdings.json 없음 — 빈 배열"}
    try:
        with open(path, encoding="utf-8") as f:
            h = json.load(f)
    except Exception as e:
        return [], {"source": path, "error": f"읽기 실패: {e}"}
    by_ticker = {s["ticker"]: s for s in sectors}
    out = []
    for sat in h.get("satellites", []) or []:
        tk = (sat.get("ticker") or "").upper()
        ysec = yahoo.sector_of(tk, cache_dir=args.cache_dir, network=not args.no_network) if tk else None
        etf = YAHOO_SECTOR_TO_TICKER.get(ysec)
        row = by_ticker.get(etf) if etf else None
        out.append({
            "ticker": tk, "since": sat.get("since"),
            "yahoo_sector": ysec, "sector_grade": "B" if ysec else None,
            "sector_etf": etf,
            "sector_row": None if row is None else {
                k: row.get(k) for k in ("name", "ticker", "rs_ratio", "rs_momentum", "quadrant",
                                        "weeks_in_quadrant", "quadrant_changed",
                                        "rs_dd_from_26w_high", "rs_dd_15",
                                        "rs_up_from_26w_low", "rs_up_30")},
        })
    return out, {"source": path, "as_of": h.get("as_of"), "account": h.get("account")}


def degraded(reason):
    """분모(QQQ)를 받지 못하면 아무 값도 만들 수 없다. 직전 파일을 그대로 두지 않고
    전부 결측인 파일을 새로 쓴다 — 루틴이 지난주 값을 이번 주 값으로 읽는 일을 막는다."""
    return {
        "program": PROGRAM, "program_version": PROGRAM_VERSION, "version": calc.CALC_VERSION,
        "as_of": None, "generated_at": dt.datetime.now(KST).replace(microsecond=0).isoformat(),
        "benchmark": BENCH, "calc": {}, "sources": [{"name": "yahoo_chart", "grade": "B",
                                                    "url": yahoo.CHART, "price_field": None}],
        "missing": [BENCH] + [t for _, t, _, _ in UNIVERSE] + ["breadth"],
        "missing_detail": {BENCH: reason},
        "sectors": [{"name": n, "ticker": t, "group": g, "rs_ratio": None, "quadrant": None,
                     "missing_reason": f"분모 {BENCH} 결측"} for n, t, g, _ in UNIVERSE],
        "breadth": None, "regime": {"dispersion": None, "dispersion_pctile_2y": None,
                                    "dispersion_history_weeks": 0, "dispersion_universe_n": 0},
        "events": {"quadrant_changes": [], "rs_dd_15": [], "rs_up_30": []},
        "holdings": [], "holdings_meta": {"source": None, "note": "분모 결측으로 태깅하지 않았다"},
        "validation": {"file": "scripts/sector_us/검증결과.md", "run_at": None, "summary": None},
        "caveats": ["benchmark_missing"],
        "notes": [f"분모 {BENCH}를 받지 못해 이번 주 관측은 전부 결측이다: {reason}"],
    }


def build(args):
    out_dir = args.out_dir
    network = not args.no_network
    try:
        bench = yahoo.chart(BENCH, rng=SECTOR_RANGE, cache_dir=args.cache_dir, network=network)
    except Exception as e:
        return degraded(str(e)[:200])
    bench_weekly, sectors, rs_by_ticker, errors = fetch_sectors(bench, args.cache_dir, network)
    as_of = bench_weekly[-1][0] if bench_weekly else None
    asof_date = dt.date.fromisoformat(as_of) if as_of else None

    # 국면 — 이번 주 분산도와 2년 백분위 (모집단: 값이 있는 섹터 전부)
    disp = calc.dispersion([s.get("rs_ratio") for s in sectors])
    hist = calc.dispersion_history(rs_by_ticker)
    disp_hist = [v for d, v in hist[-104:] if v is not None and d < (as_of or "")]
    regime = {"dispersion": disp, "dispersion_pctile_2y": calc.percentile(disp, disp_hist),
              "dispersion_history_weeks": len(disp_hist),
              "dispersion_universe_n": len([s for s in sectors if s.get("rs_ratio") is not None])}

    missing = {}
    for tk, e in errors.items():
        missing[tk] = e
    breadth, b_missing = (None, {"breadth": "--no-breadth로 생략"}) if args.no_breadth \
        else breadth_block(args.cache_dir, network, as_of=as_of)
    missing.update(b_missing)
    holdings, h_meta = holdings_block(out_dir, sectors, args)

    events = {
        "quadrant_changes": [s["ticker"] for s in sectors if s.get("quadrant_changed") is True],
        "rs_dd_15": [s["ticker"] for s in sectors if s.get("rs_dd_15") is True],
        "rs_up_30": [s["ticker"] for s in sectors if s.get("rs_up_30") is True],
    }

    sources = [{"name": "yahoo_chart", "grade": "B", "url": yahoo.CHART,
                "price_field": bench["price_field"], "range": SECTOR_RANGE}]
    if breadth:
        sources.append({"name": breadth["constituents_source"], "grade": breadth["constituents_grade"],
                        "url": breadth.get("constituents_url"), "as_of": breadth.get("constituents_as_of")})
    if any(h.get("yahoo_sector") for h in holdings):
        sources.append({"name": "yahoo_quote_summary_assetProfile", "grade": "B", "url": yahoo.QUOTE_SUMMARY})

    val = load_validation()
    notes = [
        "분모는 QQQ 수정종가다. SPY가 아니다 (제안서 R1).",
        f"가격 필드는 {bench['price_field']} — 배당 재투자 반영. Yahoo가 과거 수정종가를 소급 변경하면 과거 값이 바뀔 수 있다.",
        "보유 위성 섹터 태깅은 Yahoo 자체 섹터 분류를 GICS 11종 ETF에 대응시킨 것이고, "
        "반도체·소프트웨어·바이오 하위섹터로는 매핑되지 않는다.",
        "이 파일은 관측 입력이다. 판정 규칙이 아니고 월간 10지표에 들어가지 않는다 (제안서 §3).",
    ]
    if breadth and breadth.get("constituents_attempt_errors"):
        notes.append("구성종목 목록 출처 폴백: " + " / ".join(breadth["constituents_attempt_errors"])
                     + f" → {breadth['constituents_source']}({breadth['constituents_grade']}) 사용.")
    if breadth and breadth.get("price_fetch_failed"):
        notes.append("구성종목 가격 실패: " + ", ".join(breadth["price_fetch_failed"])
                     + f" (총 {breadth['price_fetch_errors']}종목 — 폭 지표 모집단에서 빠졌다).")
    if asof_date and asof_date.weekday() != 4:
        notes.append(f"기준일 {as_of}은 금요일이 아니다 (요일={asof_date.weekday()}). "
                     "마지막 거래일 종가 기준이며 주가 덜 끝났을 수 있다.")

    doc = {
        "program": PROGRAM, "program_version": PROGRAM_VERSION, "version": calc.CALC_VERSION,
        "as_of": as_of,
        "generated_at": dt.datetime.now(KST).replace(microsecond=0).isoformat(),
        "benchmark": BENCH,
        "calc": {"rs_window_weeks": calc.RS_WINDOW, "momentum_lag_weeks": calc.MOM_LAG,
                 "dd_fire_pct": calc.DD_FIRE, "up_fire_pct": calc.UP_FIRE,
                 "dispersion": "표본표준편차(n−1)", "weekly_rule": "ISO 주 마지막 거래일 종가"},
        "sources": sources,
        "missing": sorted(missing.keys()),
        "missing_detail": missing,
        "sectors": sectors,
        "breadth": breadth,
        "regime": regime,
        "events": events,
        "holdings": holdings,
        "holdings_meta": h_meta,
        "validation": {"file": "scripts/sector_us/검증결과.md", "run_at": val["as_of"],
                       "summary": val["lines"] or None},
        "caveats": ["no_benchmark_drawdown_prediction", "quadrant_forward_power_see_validation",
                    "no_flow_data_by_design", "breadth_universe_is_current_constituents"],
        "notes": notes,
    }
    return doc


def _f(v, digits=2, sign=False, pct=False):
    if v is None:
        return "결측"
    s = f"{v:+.{digits}f}" if sign else f"{v:.{digits}f}"
    return s.replace("-", "−") + ("%" if pct else "")


def to_markdown(doc):
    """사람용 요약. 80행 이내 (제안서 R11). 판단 어휘를 쓰지 않는다."""
    v = doc["validation"]["summary"] or {}
    src = " · ".join(f"{s['name']} ({s['grade']})" for s in doc["sources"])
    miss = ", ".join(doc["missing"]) if doc["missing"] else "없음"
    L = [f"# 미국 섹터 상대강도 (QQQ 대비) — 주간 관측", "",
         "| | |", "|---|---|",
         f"| 기준일 | {doc['as_of'] or '결측 — 분모를 받지 못했다'} |",
         f"| 생성 | {doc['generated_at']} · {doc['program']} v{doc['program_version']} (계산정의 v{doc['version']}) |",
         f"| 분모 | QQQ {doc['sources'][0]['price_field'] or '(결측)'} |",
         f"| 출처 | {src} |",
         f"| 결측 | {miss} |", "",
         "## 관측 — 사실만", "",
         "| 섹터 | 티커 | RS비율 | 4주Δ | 모멘텀% | 분면 | 연속(주) | DD26w% | 플래그 |",
         "|---|---|---|---|---|---|---|---|---|"]
    for s in doc["sectors"]:
        flags = []
        if s.get("quadrant_changed"):
            flags.append("분면전환")
        if s.get("rs_dd_15"):
            flags.append("rs_dd_15")
        if s.get("rs_up_30"):
            flags.append("rs_up_30")
        used = s.get("ticker_used") or s["ticker"]
        tk = used if used == s["ticker"] else f"{used}(대체)"
        L.append(f"| {s['name']} | {tk} | {_f(s.get('rs_ratio'))} | {_f(s.get('rs_chg_4w'), sign=True)} "
                 f"| {_f(s.get('rs_momentum'), 2, sign=True)} | {s.get('quadrant') or '결측'} "
                 f"| {s.get('weeks_in_quadrant') if s.get('weeks_in_quadrant') is not None else '결측'} "
                 f"| {_f(s.get('rs_dd_from_26w_high'), 1, sign=True)} | {' · '.join(flags)} |")
    b = doc["breadth"]
    L += ["", f"| 폭 (나스닥100 구성종목{' ' + str(b['n']) + '종목' if b else ' — 결측'}) | 값 | 비교 |", "|---|---|---|"]
    if b:
        L.append(f"| 200일선 위 비율 | {_f(b['pct_above_sma200'], 1, pct=True)} | 4주 전 {_f(b['pct_above_sma200_4w_ago'], 1, pct=True)} |")
        nh, nl = b.get("new_highs_5d"), b.get("new_lows_5d")
        ratio = "신저가 0 → 비율 결측" if (nl == 0 and nh is not None) else _f(b.get("nh_nl_ratio"))
        L.append(f"| 52주 신고가/신저가 (5일) | {nh if nh is not None else '결측'} / {nl if nl is not None else '결측'} | 비율 {ratio} |")
        L.append(f"| 출처·커버리지 | {b['constituents_source']} ({b['constituents_grade']}) | 가격 {b['n_priced']}/{b['n']}종목 |")
    else:
        L.append(f"| 200일선 위 비율 · 52주 신고저 | 결측 | {doc['missing_detail'].get('constituents', doc['missing_detail'].get('breadth', ''))[:60]} |")
    r = doc["regime"]
    L += ["", "| 국면 | 값 | 2년 백분위 |", "|---|---|---|",
          f"| 섹터 분산도 (n={r['dispersion_universe_n']}) | {_f(r['dispersion'], 4)} "
          f"| {str(r['dispersion_pctile_2y']) + '%' if r['dispersion_pctile_2y'] is not None else '결측'} "
          f"(과거 {r['dispersion_history_weeks']}주) |", ""]
    e = doc["events"]
    L.append(f"이벤트: 분면 전환 {len(e['quadrant_changes'])}"
             + (f" ({', '.join(e['quadrant_changes'])})" if e["quadrant_changes"] else "")
             + f" · rs_dd_15 {len(e['rs_dd_15'])}"
             + (f" ({', '.join(e['rs_dd_15'])})" if e["rs_dd_15"] else "")
             + f" · rs_up_30 {len(e['rs_up_30'])}"
             + (f" ({', '.join(e['rs_up_30'])})" if e["rs_up_30"] else ""))
    L += ["", "## 보유 위성 (holdings.json 기준)", ""]
    if not doc["holdings"]:
        L.append(f"없음 — {doc['holdings_meta'].get('note') or doc['holdings_meta'].get('error') or '위성 0건'}")
    else:
        L += ["| 티커 | 섹터(Yahoo) | 대응 ETF | 분면 | 연속(주) | DD26w% | 플래그 |", "|---|---|---|---|---|---|---|"]
        for h in doc["holdings"]:
            row = h.get("sector_row") or {}
            fl = " · ".join([k for k in ("rs_dd_15", "rs_up_30") if row.get(k)])
            L.append(f"| {h['ticker']} | {h.get('yahoo_sector') or '결측'} | {h.get('sector_etf') or '결측'} "
                     f"| {row.get('quadrant') or '결측'} | {row.get('weeks_in_quadrant', '결측')} "
                     f"| {_f(row.get('rs_dd_from_26w_high'), 1, sign=True)} | {fl} |")
    L += ["", "## 한계 (고정 · §9 검증 결과)", "",
          f"- QQQ 대비 상대강도는 QQQ 자체의 하락을 예고하지 않는다 — {v.get('drawdown', '검증 미실시(러너 첫 실행 대기)')}",
          f"- 분면의 4주 선행 초과수익 예측력: {v.get('quadrant', '검증 미실시(러너 첫 실행 대기)')}",
          f"- 폭 지표의 선행력: {v.get('breadth', '검증 미실시(러너 첫 실행 대기)')}",
          f"- 재현성: {v.get('stability', '검증 미실시(러너 첫 실행 대기)')}",
          "- 자금흐름 지표는 없다 (의도적 — 미국엔 외국인·기관 순매수 데이터가 없고 ETF flow·13F는 지연·불완전).",
          "- 폭 지표의 모집단은 **현재** 나스닥100 구성종목이다. 과거 시점의 편출입을 반영하지 않는다.",
          "- 이 표는 관측이다. 판정·추천이 아니다."]
    return "\n".join(L) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description="미국 섹터 상대강도 주간 관측")
    p.add_argument("out_dir", nargs="?", default="claude/advisor/월간판정/입력")
    p.add_argument("--cache-dir", default=None, help="원본 응답 캐시 (재현·오프라인 시험용)")
    p.add_argument("--no-network", action="store_true", help="캐시만 쓴다")
    p.add_argument("--no-breadth", action="store_true", help="구성종목 폭 지표를 생략한다")
    p.add_argument("--holdings", default=None, help="holdings.json 경로 (기본: out_dir/holdings.json)")
    p.add_argument("--stdout", action="store_true", help="파일을 쓰지 않고 md만 출력한다")
    args = p.parse_args(argv)

    doc = build(args)
    md = to_markdown(doc)
    hits = lint_scan(md)
    doc["lint_judgment_words"] = hits
    if hits:
        print(f"[경고] 판단 어휘 검사 실패: {hits}", file=sys.stderr)

    if args.stdout:
        print(md)
        return 0
    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "sector-us-latest.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    with open(os.path.join(args.out_dir, "sector-us-latest.md"), "w", encoding="utf-8") as f:
        f.write(md)
    snap = os.path.join(args.out_dir, f"sector-us-{doc['as_of'] or dt.date.today().isoformat()}.json")
    if not os.path.exists(snap):                      # 주간 스냅샷은 덮어쓰지 않는다 (R10)
        with open(snap, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
    print(md)
    print(f"[결측] {doc['missing'] or '없음'}", file=sys.stderr)
    return 0                                           # 부분 결측도 커밋한다 — 결측 표기가 목적


if __name__ == "__main__":
    sys.exit(main())
