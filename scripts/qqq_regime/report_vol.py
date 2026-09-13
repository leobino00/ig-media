# -*- coding: utf-8 -*-
"""experiment_vol.json → 보고서-변동성게이트.md"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "출력")


def f(x, nd=2, suf="%"):
    return "결측" if x is None else ("%+.*f%s" % (nd, x, suf))


def fa(x, nd=2, suf="%"):
    return "결측" if x is None else ("%.*f%s" % (nd, x, suf))


def main():
    with open(os.path.join(OUT, "experiment_vol.json"), encoding="utf-8") as fh:
        r = json.load(fh)
    A, B, bg, n = r["A"], r["B"], r["best_gate"], r["n_trend_rules"]
    gk = "추세+게이트 (%s)" % bg
    ORDER = ["QQQ 보유", "TQQQ 보유", "추세만 (sma40_b0)", gk, "타게팅 vt13w_t20", "타게팅+추세"]
    L = []
    P = L.append

    P("# 변동성 게이트 — 조용할 때만 3배에 들어간다")
    P("")
    P("생성 %s · 추세 규칙 %d개 × 게이트 %d개 · 전환비용 %.0fbp"
      % (r["generated_at"], n, r["n_gates"], r["cost_bps"]))
    P("")
    P("> **실험 기록이다. 투자 판정이 아니다.** 어드바이저 프로토콜·판정기록부와 무관하다.")
    P("")
    P("## 가설과 근거")
    P("")
    P("앞선 두 실험에서 기각된 것 — **SQQQ 숏 다리**(35개 규칙 전부 악화), **일간 전환**(톱질로 두 구간 모두 악화).")
    P("남은 가설: 가격만 보는 추세 신호가 톱질에 약하다면 **변동성을 게이트로 쓰면 어떤가.**")
    P("")
    P("임계치는 적합하지 않고 **이론에서 온다.** 일간리셋 L배 상품의 변동성 끌림은 대략 (L²−L)/2·σ² 이고,")
    P("L=3 이면 3σ² 다. 3배 위험프리미엄(연 15~18%)을 끌림이 넘어서는 지점이 **σ ≈ 22%** 이므로")
    P("절대 임계는 20~35%를 훑었고, 시대별 수준 변화를 흡수하는 백분위 게이트도 함께 봤다.")
    P("(참고: QQQ 13주 실현변동성은 중앙 %s · 75백분위 %s · 최대 %s.)"
      % (fa(r["vol_summary"]["median_13w"], 1), fa(r["vol_summary"]["p75_13w"], 1),
         fa(r["vol_summary"]["max_13w"], 1)))
    P("")
    P("## 답 — 처음으로 효과가 있다. 다만 공짜가 아니다")
    P("")
    P("추세 규칙 %d개 각각에 게이트를 켜고 끈 **짝 비교**다. 바뀐 것은 게이트뿐이다." % n)
    P("")
    P("| 구간 | 지표 | 게이트 없음 | 게이트 `%s` | 개선된 규칙 |" % bg)
    P("|---|---|---|---|---|")
    for key, lab in (("A", "A. 2010~2026 (실제)"), ("B", "B. 2000~2026 (시뮬)")):
        R = r[key]
        g = R["gated"][bg]
        P("| **%s** | CAGR 중앙 | %s | %s | %d / %d |" % (
            lab, f(R["base"]["cagr"]["median"]), f(g["cagr"]["median"]), g["improved_cagr"], n))
        P("| | 최대낙폭 중앙 | %s | **%s** | **%d / %d** |" % (
            fa(R["base"]["mdd"]["median"]), fa(g["mdd"]["median"]), g["improved_mdd"], n))
        P("| | MAR 중앙 | %.3f | **%.3f** | %d / %d |" % (
            R["base"]["mar"]["median"], g["mar"]["median"], g["improved_mar"], n))
    P("")
    P("**낙폭 개선이 압도적이다** — 구간 B에서 %d/%d 규칙, 구간 A에서 %d/%d 규칙이 나아졌다."
      % (B["gated"][bg]["improved_mdd"], n, A["gated"][bg]["improved_mdd"], n))
    P("수익률은 구간에 따라 갈린다: 붕괴가 들어간 B에서는 %s 올랐고, 상승만 있던 A에서는 %s 내렸다."
      % (f(B["gated"][bg]["median_d_cagr"], 2, "%p"), f(A["gated"][bg]["median_d_cagr"], 2, "%p")))
    P("")
    P("## 게이트 전수 — 고른 것이 아니라 전부 싣는다")
    P("")
    for key, lab in (("A", "구간 A (2010~2026)"), ("B", "구간 B (2000~2026)")):
        P("### %s" % lab)
        P("")
        P("| 게이트 | CAGR 중앙 | MDD 중앙 | MAR 중앙 | CAGR 개선 | MDD 개선 | MAR 개선 |")
        P("|---|---|---|---|---|---|---|")
        for gname, g in sorted(r[key]["gated"].items(), key=lambda kv: -kv[1]["mar"]["median"]):
            P("| `%s` | %s | %s | %.3f | %d/%d | %d/%d | %d/%d |" % (
                gname, f(g["cagr"]["median"]), fa(g["mdd"]["median"]), g["mar"]["median"],
                g["improved_cagr"], n, g["improved_mdd"], n, g["improved_mar"], n))
        P("")
    P("**두 구간의 상위 2개가 같다** — `vol13w_p80` 과 `vol13w<30`. 13주가 26주보다 일관되게 낫다.")
    P("서로 다른 기간에서 순위가 일치하는 것은 이 실험에서 드문 일이다 (규칙 선택은 그렇지 않았다).")
    P("다만 **`%s` 를 대표로 고른 기준이 구간 B의 MAR 중앙값이므로, 그 숫자에는 선택이 들어가 있다.**" % bg)
    P("")
    P("## 후보 대조")
    P("")
    for key, lab in (("B", "구간 B (2000~2026) — 붕괴 포함"), ("A", "구간 A (2010~2026)")):
        P("### %s" % lab)
        P("")
        P("| 전략 | CAGR | 최대낙폭 | MAR | 평균 노출 |")
        P("|---|---|---|---|---|")
        for k in ORDER:
            x = r["candidates"][key][k]
            mw = ("%.0f%%" % (100 * x["mean_weight"])) if x.get("mean_weight") is not None else "—"
            P("| %s | %s | %s | %.3f | %s |" % (k, f(x["cagr_pct"]), fa(x["mdd_pct"]), x["mar"] or 0, mw))
        P("")
    cb = r["candidates"]["B"]
    P("구간 B에서 **추세+게이트가 수익률은 거의 그대로 두고(%s → %s) 낙폭을 %s → %s 로 줄인다.**"
      % (f(cb["추세만 (sma40_b0)"]["cagr_pct"]), f(cb[gk]["cagr_pct"]),
         fa(cb["추세만 (sma40_b0)"]["mdd_pct"]), fa(cb[gk]["mdd_pct"])))
    P("MAR은 %.3f → %.3f 다. **변동성 타게팅 단독은 안 된다** — 낙폭 %s 로 추세 없이는 하락장을 못 벗어난다."
      % (cb["추세만 (sma40_b0)"]["mar"], cb[gk]["mar"], fa(cb["타게팅 vt13w_t20"]["mdd_pct"])))
    P("")
    P("## 왜 되는가 — 위기 구간의 노출 비율")
    P("")
    for w in r["crisis"]["windows"]:
        P("### %s (%d주, 13주 실현변동성 중앙 %s)" % (w["name"], w["weeks"], fa(w["median_vol_13w"], 1)))
        P("")
        P("| 전략 | 수익률 | 최대낙폭 | 노출 |")
        P("|---|---|---|---|")
        for k in ORDER + ["전액 현금"]:
            ex = w[k].get("exposure_pct")
            P("| %s | **%s** | %s | %s |" % (k, f(w[k]["total_pct"]), fa(w[k]["mdd_pct"]),
                                             ("%.1f%%" % ex) if ex is not None else "—"))
        P("")
    dot = r["crisis"]["windows"][0]
    rec = [x for x in r["crisis"]["windows"] if "회복" in x["name"]][0]
    P("**닷컴이 이 게이트의 존재 이유다.** 그 139주의 13주 실현변동성 중앙값이 %s로, 전체 기간 중앙값 %s의 2배가 넘는다."
      % (fa(dot["median_vol_13w"], 1), fa(r["vol_summary"]["median_13w"], 1)))
    P("추세 신호만 쓰면 139주 중 %s만 들어갔는데도 %s를 잃었다 — 곰 반등에 몇 번 속았고, 3배가 그것을 치명상으로 만들었다."
      % (fa(dot["추세만 (sma40_b0)"]["exposure_pct"], 1), f(dot["추세만 (sma40_b0)"]["total_pct"])))
    P("게이트를 켜면 노출이 %s로 줄고 손실은 %s다. (전액 현금이었다면 %s — 당시 금리가 5~6%%였다.)"
      % (fa(dot[gk]["exposure_pct"], 1), f(dot[gk]["total_pct"]), f(dot["전액 현금"]["total_pct"])))
    P("")
    P("**값은 2020년 회복에서 치른다.** %s: 추세만 %s vs 추세+게이트 %s."
      % (rec["name"], f(rec["추세만 (sma40_b0)"]["total_pct"]), f(rec[gk]["total_pct"])))
    P("변동성이 가라앉기를 기다리는 동안 V자 반등의 절반을 놓친다. **게이트가 사는 대가가 이것이다.**")
    P("")
    P("## 표본외 — 그래서 공짜가 아니다")
    P("")
    P("| 전략 | 표본내 (2010~2018) | 표본외 (2019~2026) | 표본외 MDD |")
    P("|---|---|---|---|")
    for k in ORDER[1:]:
        i = r["candidates"]["split"]["is"].get(k)
        o = r["candidates"]["split"]["oos"].get(k)
        if i and o:
            P("| %s | %s | %s | %s |" % (k, f(i["cagr_pct"]), f(o["cagr_pct"]), fa(o["mdd_pct"])))
    P("")
    sp = r["split"]
    P("규칙 %d개 중앙값 기준으로는 표본내 %s → %s (%sp), 표본외 %s → %s (**%sp**)." % (
        n, f(sp["is"]["base_median"]), f(sp["is"]["gated_median"]),
        f(sp["is"]["gated_median"] - sp["is"]["base_median"]),
        f(sp["oos"]["base_median"]), f(sp["oos"]["gated_median"]),
        f(sp["oos"]["gated_median"] - sp["oos"]["base_median"])))
    P("")
    P("**표본외에서 게이트는 수익률을 크게 깎았다.** 그 기간에 2020년 V자 회복이 있었기 때문이고,")
    P("같은 기간 낙폭은 %s → %s 로 나아졌다. 이것은 게이트가 틀렸다는 뜻이 아니라"
      % (fa(r["candidates"]["split"]["oos"]["추세만 (sma40_b0)"]["mdd_pct"]),
         fa(r["candidates"]["split"]["oos"][gk]["mdd_pct"])))
    P("**게이트가 사고파는 것이 수익이 아니라 낙폭이라는 뜻**이다. 어느 쪽이 이득인지는 앞으로 오는 국면이 정한다.")
    P("")
    P("## 거래비용은 원인이 아니다")
    P("")
    P("| 전환비용 | A 기본 | A 게이트 | A 차 | B 기본 | B 게이트 | B 차 |")
    P("|---|---|---|---|---|---|---|")
    for c in sorted(r["cost"], key=lambda x: float(x[:-2])):
        v = r["cost"][c]
        P("| %s | %s | %s | %sp | %s | %s | %sp |" % (
            c, f(v["A"]["base_median"]), f(v["A"]["gated_median"]),
            f(v["A"]["gated_median"] - v["A"]["base_median"]),
            f(v["B"]["base_median"]), f(v["B"]["gated_median"]),
            f(v["B"]["gated_median"] - v["B"]["base_median"])))
    P("")
    P("모든 비용 수준에서 부호가 같다. 게이트는 회전을 늘리지 않는다 — 오히려 진입을 막는 쪽이다.")
    P("")
    P("## 한계")
    P("")
    for c in [
        "**대표 게이트 선택에 사후판단이 있다.** `%s` 는 구간 B의 MAR 중앙값으로 골랐다. "
        "다만 상위 2개가 두 구간에서 같았다는 사실은 그 선택과 독립이다." % bg,
        "**구간 B는 시뮬레이션이다.** 닷컴 결과가 이 실험의 가장 강한 근거인데, 그 구간에 실제 3배 상품이 없었다. "
        "다만 노출 비율(0.7%)과 실현변동성(42.9%)은 모형과 무관하게 QQQ에서 직접 관측된다.",
        "**σ≈22% 라는 이론 임계는 근사다.** 위험프리미엄 추정과 정규성 가정이 들어가 있고, 실제 최적점은 다를 수 있다.",
        "**표본외 1구간뿐이다.** 2019~2026 한 번의 결과로 게이트의 우열을 정할 수 없다.",
        "**세금·환율이 없다.** 국내 계좌 기준 세후·원화 수익률은 위 숫자보다 낮다.",
        "**단일 벤더다.** Alpha Vantage 수정종가 · Twelve Data 일봉. 원자료와 대조하지 않았다.",
    ]:
        P("- %s" % c)
    P("")
    P("## 세 실험을 합치면")
    P("")
    P("| 시도 | 결과 |")
    P("|---|---|")
    P("| SQQQ 숏 다리 | **기각.** 35개 규칙 전부 악화 |")
    P("| 일간 전환 | **기각.** 톱질로 두 구간 모두 악화 |")
    P("| 변동성 게이트 | **부분 채택.** 낙폭을 일관되게 줄인다(%d/%d). 수익률은 국면에 따라 갈린다 |"
      % (B["gated"][bg]["improved_mdd"], n))
    P("")

    path = os.path.join(OUT, "보고서-변동성게이트.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    sys.stdout.write("썼다: %s (%d행)\n" % (path, len(L) + 1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
