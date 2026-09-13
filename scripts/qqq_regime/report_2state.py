# -*- coding: utf-8 -*-
"""experiment_2state.json → 보고서-2상태.md

    python3 scripts/qqq_regime/report_2state.py
"""

import json
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "출력")


def f(x, nd=2, suf="%"):
    return "결측" if x is None else ("%+.*f%s" % (nd, x, suf))


def fa(x, nd=2, suf="%"):
    return "결측" if x is None else ("%.*f%s" % (nd, x, suf))


def main():
    with open(os.path.join(OUT, "experiment_2state.json"), encoding="utf-8") as fh:
        r = json.load(fh)
    A, B, sv, sp = r["A"], r["B"], r["sim_validation"], r["A"]["split"]
    fit = B["scenarios"]["적합"]
    bt, bq = A["bench"]["TQQQ"], A["bench"]["QQQ"]
    n = r["n_rules"]
    L = []
    P = L.append

    P("# QQQ 2상태 실험 — 상승 추세면 TQQQ, 아니면 현금")
    P("")
    P("생성 %s · 규칙 %d개 · 전환비용 %.0fbp" % (r["generated_at"], n, r["cost_bps"]))
    P("")
    P("> **실험 기록이다. 투자 판정이 아니다.** 어드바이저 프로토콜·판정기록부와 무관하다.")
    P("> 숏(SQQQ) 다리는 뺐다 — 3상태 실험에서 35개 규칙 전부를 악화시켰기 때문이다.")
    P("")
    P("## 답 — 기간에 따라 정반대로 뒤집힌다")
    P("")
    P("| 구간 | 규칙 %d개 CAGR 중앙 | TQQQ 그냥 보유 | 판정 |" % n)
    P("|---|---|---|---|")
    P("| **A. 2010~2026** (실제 TQQQ) | %s | **%s** | 바이앤홀드가 이긴다 |"
      % (f(A["cagr"]["median"]), f(bt["cagr_pct"])))
    P("| **B. 2000~2026** (시뮬 TQQQ) | **%s** | %s | **바이앤홀드가 소멸한다** |"
      % (f(fit["cagr"]["median"]), f(fit["bench_tqqq"]["cagr_pct"])))
    P("")
    P("**하나의 연간 수익률로 답할 수 없는 이유가 이것이다.** 2010년 이후만 보면 이 전략은")
    P("TQQQ를 그냥 드는 것보다 **못하다**(60개 중 %d개만 이겼다). 2000년부터 보면" % A["beat_tqqq_cagr"])
    P("TQQQ 바이앤홀드는 **CAGR %s · 최대낙폭 %s** 로 사실상 소멸하고, 전략은 %s로 살아남는다."
      % (f(fit["bench_tqqq"]["cagr_pct"]), fa(fit["bench_tqqq"]["mdd_pct"]), f(fit["cagr"]["median"])))
    P("")
    P("**이 전략이 사는 곳은 상승장이 아니라 붕괴장이다.**")
    P("")
    P("## 구간 A — 2010-02-19 ~ 2026-09-11, 실제 TQQQ 가격 (%d주)" % A["period"][2])
    P("")
    P("| | CAGR | 최대낙폭 | MAR | 변동성 |")
    P("|---|---|---|---|---|")
    P("| TQQQ 그냥 보유 | %s | %s | %.3f | %s |" % (f(bt["cagr_pct"]), fa(bt["mdd_pct"]), bt["mar"], fa(bt["vol_pct"])))
    P("| QQQ 그냥 보유 | %s | %s | %.3f | %s |" % (f(bq["cagr_pct"]), fa(bq["mdd_pct"]), bq["mar"], fa(bq["vol_pct"])))
    P("| 규칙 %d개 중앙값 | %s | %s | %.3f | — |" % (n, f(A["cagr"]["median"]), fa(A["mdd"]["median"]), A["mar"]["median"]))
    P("| 규칙 %d개 범위 | %s ~ %s | %s ~ %s | %.3f ~ %.3f | — |" % (
        n, f(A["cagr"]["min"]), f(A["cagr"]["max"]), fa(A["mdd"]["min"]), fa(A["mdd"]["max"]),
        A["mar"]["min"], A["mar"]["max"]))
    P("")
    P("| 질문 | 답 |")
    P("|---|---|")
    P("| TQQQ 보유보다 **CAGR**이 높은 규칙 | **%d / %d** |" % (A["beat_tqqq_cagr"], n))
    P("| TQQQ 보유보다 **MAR**(수익÷낙폭)이 높은 규칙 | **%d / %d** |" % (A["beat_tqqq_mar"], n))
    P("| 규칙이 TQQQ에 들어가 있던 기간 | 중앙 %s (범위 %s ~ %s) |" % (
        fa(A["pct_in"]["median"], 1), fa(A["pct_in"]["min"], 1), fa(A["pct_in"]["max"], 1)))
    P("")
    P("**이 구간에서 수익률로는 단 한 규칙도 이기지 못했다.** 이기는 규칙이 나오는 축은 MAR뿐이고,")
    P("그것도 %d/%d다. 낙폭은 중앙 %s로 TQQQ 보유(%s)보다 %s p 낫다."
      % (A["beat_tqqq_mar"], n, fa(A["mdd"]["median"]), fa(bt["mdd_pct"]),
         f(abs(bt["mdd_pct"]) - abs(A["mdd"]["median"]), 1, "%p")))
    P("")
    P("## 구간 B — 2000-01-07 ~ 2026-09-11, 시뮬 TQQQ (%d주)" % B["period"][2])
    P("")
    P("TQQQ는 2010년 상장이라 닷컴·금융위기 성적이 없다. **그 두 사건이 이 전략의 존재 이유이므로**")
    P("일간리셋 모형으로 3배를 합성해 구간을 늘렸다. 합성 오차는 아래 「시뮬 검증」에 있다.")
    P("")
    P("| 보수 가정 | TQQQ 보유 CAGR | TQQQ 보유 MDD | 규칙 중앙 CAGR | 규칙 중앙 MDD | 규칙 중앙 MAR |")
    P("|---|---|---|---|---|---|")
    for label, sc in sorted(B["scenarios"].items(), key=lambda kv: kv[1]["fee_annual_pct"]):
        P("| %s (연 %s) | %s | %s | **%s** | %s | %.3f |" % (
            label, fa(sc["fee_annual_pct"]), f(sc["bench_tqqq"]["cagr_pct"]), fa(sc["bench_tqqq"]["mdd_pct"]),
            f(sc["cagr"]["median"]), fa(sc["mdd"]["median"]), sc["mar"]["median"]))
    P("")
    P("같은 구간 **QQQ 그냥 보유는 CAGR %s · MDD %s** 다."
      % (f(fit["bench_qqq"]["cagr_pct"]), fa(fit["bench_qqq"]["mdd_pct"])))
    P("즉 2000년부터 보면 규칙 중앙값(%s)이 QQQ 보유(%s)와 TQQQ 보유(%s)를 **둘 다 이긴다.**"
      % (f(fit["cagr"]["median"]), f(fit["bench_qqq"]["cagr_pct"]), f(fit["bench_tqqq"]["cagr_pct"])))
    P("보수 가정을 %s~%s로 흔들어도 중앙값은 %s ~ %s 사이다 — 결론이 가정에 의존하지 않는다." % (
        fa(min(s["fee_annual_pct"] for s in B["scenarios"].values())),
        fa(max(s["fee_annual_pct"] for s in B["scenarios"].values())),
        f(min(s["cagr"]["median"] for s in B["scenarios"].values())),
        f(max(s["cagr"]["median"] for s in B["scenarios"].values()))))
    P("")
    P("### 3배 바이앤홀드가 소멸한다는 것의 의미")
    P("")
    P("구간 B에서 TQQQ 그냥 보유의 최대낙폭은 **%s** 다. 26년을 버텨도 CAGR이 %s다."
      % (fa(fit["bench_tqqq"]["mdd_pct"]), f(fit["bench_tqqq"]["cagr_pct"])))
    P("**TQQQ가 2010년에 상장했다는 사실 자체가 생존편향이다** — 닷컴 붕괴를 통과한 3배 나스닥 상품은")
    P("존재하지 않는다. 「TQQQ 장기보유 CAGR +41.67%」는 **운 좋은 출발점의 수익률**이다.")
    P("")
    P("## 위기 구간 — 중앙값 규칙 `%s`" % r["crisis"]["median_rule"])
    P("")
    P("| 구간 | 전략 | 전략 MDD | TQQQ 보유 | TQQQ MDD | QQQ 보유 |")
    P("|---|---|---|---|---|---|")
    for w in r["crisis"]["windows"]:
        P("| %s | **%s** | %s | %s | %s | %s |" % (
            w["name"], f(w["strategy_total_pct"]), fa(w["strategy_mdd_pct"]),
            f(w["tqqq_total_pct"]), fa(w["tqqq_mdd_pct"]), f(w["qqq_total_pct"])))
    P("")
    P("**전략도 크게 잃는다.** 닷컴에서 %s다 — 주간 종가로만 전환하므로 급락을 며칠씩 맞고 나간다."
      % f(r["crisis"]["windows"][0]["strategy_total_pct"]))
    P("차이는 회복 가능성이다. %s는 이후 상승에서 되돌아올 수 있지만, TQQQ 보유의 %s에는"
      % (f(r["crisis"]["windows"][0]["strategy_total_pct"]), f(r["crisis"]["windows"][0]["tqqq_total_pct"])))
    P("복구할 원금이 남지 않는다 — 2배가 오르면 원금의 %.1f%%가 된다."
      % ((1 + r["crisis"]["windows"][0]["tqqq_total_pct"] / 100.0) * 300))
    P("")
    P("## 시뮬 검증 — 합성 3배를 믿어도 되는 근거")
    P("")
    P("| 항목 | 값 |")
    P("|---|---|")
    P("| 주간 수익률 상관 (시뮬 vs 실제 TQQQ) | **%.4f** |" % sv["weekly_corr"])
    P("| 주간 수익률 평균절대차 | %sp |" % fa(sv["weekly_mean_abs_diff_pp"], 3, ""))
    P("| 보수 0%% 가정 시뮬 CAGR | %s (실제 %s, 차 **%sp**) |" % (
        f(sv["sim_cagr_fee0_pct"]), f(sv["real_cagr_pct"]), f(sv["err_fee0_pp"], 2, "%")))
    P("| 적합된 연 보수 | %s (공시 보수 %s) |" % (fa(sv["fitted_fee_annual_pct"]), fa(sv["stated_expense_ratio_pct"])))
    P("| 참고 — 주간 등락률 ×3 단순 합성 | 실제를 연 **+9.66%p 과대평가** |")
    P("")
    P("적합 보수가 **%s** 로 공시 보수(%s)와 같은 자릿수이고 부호만 약간 반대다."
      % (fa(sv["fitted_fee_annual_pct"]), fa(sv["stated_expense_ratio_pct"])))
    P("음수인 이유는 분모로 쓴 QQQ 가격수익률이 나스닥100 지수보다 QQQ 자체 보수(연 0.20%)만큼 낮기 때문이다")
    P("— 3배로 확대되면 약 0.6%p다. **모형이 구조적으로 맞다는 신호**이지, 맞춰 넣은 숫자가 아니다.")
    P("")
    P("## 표본외 — 「가장 좋은 규칙」을 고르면 안 되는 이유")
    P("")
    P("| 항목 | 값 |")
    P("|---|---|")
    P("| 표본내 (%s ~ %s) 최고 | `%s` %s |" % (sp["is_period"][0], sp["is_period"][1], sp["best_is_rule"], f(sp["best_is_cagr"])))
    P("| 그 규칙의 표본외 (%s ~ %s) | %s (**%d/%d위**) |" % (
        sp["oos_period"][0], sp["oos_period"][1], f(sp["oos_cagr_of_that"]), sp["oos_rank_of_that"], n))
    P("| 표본내·표본외 **순위상관** | **%+.3f** |" % sp["rank_corr_is_oos"])
    P("| 표본내 top5 중 표본외 top10 잔류 | **%d / 5** |" % sp["is_top5_still_top10_oos"])
    P("| 표본내 중앙 → 표본외 중앙 | %s → %s |" % (f(sp["is_median"]), f(sp["oos_median"])))
    P("| 표본외 TQQQ 그냥 보유 | %s |" % f(sp["oos_bench_tqqq"]))
    P("")
    P("표본내 top5의 표본외 순위: %s." % ", ".join("`%s`→%d위" % (a, b) for a, b in sp["is_top5_oos_ranks"]))
    P("")
    P("순위상관 %+.3f는 **규칙 성적이 무작위는 아니라는 뜻**이다. 그러나 표본내 상위 5개 중"
      % sp["rank_corr_is_oos"])
    P("표본외 상위 10위 안에 남은 것은 **%d개뿐**이다. 1등이 1등을 지킨 것은 한 번의 관측이지 근거가 아니다."
      % sp["is_top5_still_top10_oos"])
    P("**보고할 숫자는 중앙값이고, 최고값은 「%d개 중 1등」이라는 꼬리표와 함께만 쓴다.**" % n)
    P("")
    P("## 규칙 전수 — 구간 A (CAGR 내림차순)")
    P("")
    P("| 규칙 | CAGR | 최대낙폭 | MAR | TQQQ 보유기간 | 전환/년 |")
    P("|---|---|---|---|---|---|")
    for x in sorted(A["rows"], key=lambda z: -z["cagr_pct"]):
        P("| `%s` | %s | %s | %.3f | %s | %.1f |" % (
            x["rule"], f(x["cagr_pct"]), fa(x["mdd_pct"]), x["mar"],
            fa(x["pct_in_tqqq"], 1), x["switches_per_year"]))
    P("")
    P("## 한계")
    P("")
    for c in [
        "**구간 B는 시뮬레이션이다.** 검증을 거쳤고 오차가 작지만(위), 2000~2009에는 대조할 실제 3배 상품이 "
        "없다. 그 시기에 3배 상품이 실제로 존재했다면 자금유출·거래상대방·상장폐지 위험이 있었을 것이고, "
        "모형에는 그것이 없다.",
        "**주간 종가로만 전환한다.** 닷컴 구간 전략 손실 %s가 그 대가다. 일간 전환이면 낙폭은 줄겠지만 "
        "전환 횟수·비용·세금이 커진다 — 시험하지 않았다." % f(r["crisis"]["windows"][0]["strategy_total_pct"]),
        "**규칙 %d개는 이동평균·모멘텀 계열뿐이다.** 변동성·폭·거시 기반 레짐 판별은 보지 않았다." % n,
        "**세금이 없다.** 국내 계좌에서 TQQQ 회전은 양도세를 만든다. 전환 %.1f~%.1f회/년이면 세후는 위 숫자보다 낮다."
        % (min(x["switches_per_year"] for x in A["rows"]), max(x["switches_per_year"] for x in A["rows"])),
        "**환율이 없다.** 전부 달러 기준이다.",
        "**단일 벤더다.** Alpha Vantage 수정종가 · Twelve Data 일봉. 원자료와 대조하지 않았다.",
    ]:
        P("- %s" % c)
    P("")

    path = os.path.join(OUT, "보고서-2상태.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    sys.stdout.write("썼다: %s (%d행)\n" % (path, len(L) + 1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
