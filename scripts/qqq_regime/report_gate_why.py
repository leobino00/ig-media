# -*- coding: utf-8 -*-
"""analysis_gate.json → 보고서-게이트원인분석.md"""

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
    with open(os.path.join(OUT, "analysis_gate.json"), encoding="utf-8") as fh:
        r = json.load(fh)
    H0, SOLO, RD = r["H0_shift"], r["H0_shift_solo"], r["redundancy"]
    H2, H34, EC = r["H2_persistence"], r["H3_H4_by_quintile"], r["exposure_control"]
    L = []
    P = L.append

    P("# 변동성 게이트는 왜 살아남았는가 — 원인 분해")
    P("")
    P("생성 %s · 게이트 `%s` · 추세 `%s`" % (r["generated_at"], r["gate"], r["trend"]))
    P("")
    P("> **실험 기록이다. 투자 판정이 아니다.** 어드바이저 프로토콜·판정기록부와 무관하다.")
    P("")
    P("## 결론 먼저")
    P("")
    P("**게이트의 이득은 「위험한 구간을 알아맞힌 것」이 아니라 「노출을 줄인 것」으로 거의 전부 설명된다.**")
    P("")
    P("근거 세 줄:")
    P("")
    P("1. 노출을 맞춘 순환이동 검정에서 **수익도 낙폭도 유의하지 않다** (p = %.2f ~ %.2f)."
      % (min(H0[k]["matched"]["pval_mdd"] for k in H0 if H0[k].get("matched")),
         max(H0[k]["matched"]["pval_cagr"] for k in H0 if H0[k].get("matched"))))
    P("2. 게이트가 막은 주의 **%s는 추세 신호가 이미 막고 있었다.** 게이트가 추가로 막는 것은 전체의 %s뿐이다."
      % (fa(RD["blocked_and_trend_down_pct"], 1), fa(RD["gate_adds_pct"], 1)))
    P("3. 그런데 **게이트 단독**(추세 없이)으로는 구간 A에서 낙폭 정보가 유의하다 (p = %.3f)."
      % SOLO["A 실제"]["pval_mdd"])
    P("")
    P("즉 **게이트가 아는 것은 진짜지만, 그 대부분을 추세가 이미 알고 있었다.**")
    P("")
    P("## 귀무가설 검정 — 순환이동")
    P("")
    P("게이트 시계열을 k주 돌린다. 노출 비율과 연속구간 길이 분포가 **정확히 보존**되고,")
    P("「어느 주를 막는가」의 시간 정렬만 깨진다. 실제 게이트가 surrogate 분포의 어디에 있는지를 본다.")
    P("")
    P("### 추세 위에 얹은 게이트")
    P("")
    P("| 구간 | | 실제 | surrogate 중앙 | p |")
    P("|---|---|---|---|---|")
    for k, v in H0.items():
        P("| **%s** | CAGR | %s | %s | %.3f |" % (k, f(v["real_cagr"]), f(v["surr_cagr_median"]), v["pval_cagr"]))
        P("| | 최대낙폭 | %s | %s | **%.3f** |" % (fa(v["real_mdd"]), fa(v["surr_mdd_median"]), v["pval_mdd"]))
        P("| | 노출 | %s | %s | — |" % (fa(v["real_pct_in"], 1), fa(v["surr_pct_in_median"], 1)))
    P("")
    P("낙폭 p값이 %.3f·%.3f 로 유의해 보인다. **그러나 노출이 맞지 않는다** —"
      % (H0["A 실제"]["pval_mdd"], H0["B 시뮬"]["pval_mdd"]))
    P("순환이동은 게이트 자체의 노출은 보존하지만 **추세 UP 과의 겹침**은 보존하지 않아,")
    P("실제 쪽 노출이 surrogate 중앙보다 %sp 높다. 그래서 노출을 맞춘 부분집합으로 다시 잰다."
      % f(H0["A 실제"]["real_pct_in"] - H0["A 실제"]["surr_pct_in_median"], 1, "%"))
    P("")
    P("### 노출을 맞추면")
    P("")
    P("| 구간 | surrogate 수 | 허용 오차 | CAGR p | 최대낙폭 p |")
    P("|---|---|---|---|---|")
    for k, v in H0.items():
        m = v.get("matched")
        if m:
            P("| %s | %d개 | ±%sp | **%.3f** | **%.3f** |" % (
                k, m["n"], fa(m["tolerance_pp"], 0), m["pval_cagr"], m["pval_mdd"]))
    P("")
    P("**둘 다 유의하지 않다.** 같은 비율로 아무 주나 (덩어리째) 막아도 결과가 비슷하다는 뜻이다.")
    P("")
    P("방향만은 두 구간에서 일관된다 — 실제 게이트는 exposure-matched surrogate 대비")
    P("수익을 약 %sp 내주고 낙폭을 약 %sp 얻는다. 유의하지는 않지만 부호가 흔들리지 않는다."
      % (f(H0["B 시뮬"]["matched"]["cagr_median"] - H0["B 시뮬"]["real_cagr"], 1),
         f(abs(H0["B 시뮬"]["matched"]["mdd_median"]) - abs(H0["B 시뮬"]["real_mdd"]), 1)))
    P("")
    P("## 왜 유의하지 않은가 — 추세와 중복이다")
    P("")
    P("| 항목 | 값 |")
    P("|---|---|")
    P("| 관측 주 | %d |" % RD["weeks"])
    P("| 추세 UP 비율 | %s |" % fa(RD["trend_up_pct"], 1))
    P("| 게이트 차단 비율 | %s |" % fa(RD["gate_blocked_pct"], 1))
    P("| **게이트가 막은 주 중 추세가 이미 DOWN 이던 비율** | **%s** |" % fa(RD["blocked_and_trend_down_pct"], 1))
    P("| 게이트가 추가로 막은 주 (전체 대비) | %s |" % fa(RD["gate_adds_pct"], 1))
    P("| 추세 UP 과 게이트 통과의 상관 (phi) | %.3f |" % RD["phi"])
    P("")
    P("**게이트 일의 절반은 이미 되어 있던 일이다.**")
    P("그래서 추세 위에 얹으면 남은 여지가 작고, 검정력이 그만큼 떨어진다.")
    P("")
    P("### 게이트 단독이면 정보가 보인다")
    P("")
    P("| 구간 | | 실제 | surrogate 중앙 | p | TQQQ 보유 |")
    P("|---|---|---|---|---|---|")
    for k, v in SOLO.items():
        P("| **%s** | CAGR | %s | %s | %.3f | %s |" % (
            k, f(v["real_cagr"]), f(v["surr_cagr_median"]), v["pval_cagr"], f(v["bench_tqqq_cagr"])))
        P("| | 최대낙폭 | %s | %s | **%.3f** | %s |" % (
            fa(v["real_mdd"]), fa(v["surr_mdd_median"]), v["pval_mdd"], fa(v["bench_tqqq_mdd"])))
    P("")
    P("구간 A에서 게이트 단독의 낙폭이 **p = %.3f** 로 유의하다 (노출 %s vs surrogate %s — 거의 맞는다)."
      % (SOLO["A 실제"]["pval_mdd"], fa(SOLO["A 실제"]["real_pct_in"], 1),
         fa(SOLO["A 실제"]["surr_pct_in_median"], 1)))
    P("**게이트에 낙폭 정보가 있다는 증거는 여기 있다.** 추세 위에서는 그것이 중복돼 사라진다.")
    P("")
    P("## 기계는 실재한다 — H1 변동성 끌림")
    P("")
    P("주간 로그수익 기준 끌림 = `ln(1+r_3배) − 3·ln(1+r_QQQ)`. 이론값은 `−3σ²` (연율).")
    P("")
    for blk in r["H1_drag"]:
        P("### %s (%s ~ %s)" % (blk["label"], blk["period"][0], blk["period"][1]))
        P("")
        P("| 변동성 5분위 | n | 평균 변동성 | 측정 끌림/년 | 이론 −3σ² | 잔차 |")
        P("|---|---|---|---|---|---|")
        for x in blk["rows"]:
            P("| %d | %d | %s | **%s** | %s | %sp |" % (
                x["quintile"], x["n"], fa(x["mean_vol_pct"], 1), f(x["measured_drag_pct"]),
                f(x["theory_drag_pct"]), f(x["residual_pp"])))
        P("")
    a = r["H1_drag"][0]["rows"]
    P("**최상위 5분위의 구조적 비용이 최하위의 %.1f배다** (%s vs %s, 실제 TQQQ)."
      % (a[4]["measured_drag_pct"] / a[0]["measured_drag_pct"],
         f(a[4]["measured_drag_pct"]), f(a[0]["measured_drag_pct"])))
    P("이론 `−3σ²` 가 기울기를 맞추고, 잔차 %s ~ %sp 는 보수·차입비용과"
      % (f(min(x["residual_pp"] for x in a), 1), f(max(x["residual_pp"] for x in a), 1)))
    P("분모로 쓴 QQQ 가격수익률이 지수보다 낮은 몫(×3)으로 설명된다.")
    P("**이것은 예측이 아니라 비용이다.** 게이트는 맞히는 것이 아니라 비싼 구간을 피하는 장치다.")
    P("")
    P("## 쓸 수 있는 이유 — H2 변동성은 지속된다")
    P("")
    P("| 시차 | 자기상관 |")
    P("|---|---|")
    for k, v in sorted(H2["autocorr"].items(), key=lambda kv: int(kv[0])):
        P("| %s주 | %.3f |" % (k, v))
    P("")
    P("%d주 뒤에도 최상위 5분위에 남아 있을 확률이 **%s** 다 (무정보면 20%%)."
      % (H2["lag_weeks"], fa(H2["stay_top_pct"], 1)))
    P("지속성이 없으면 과거 변동성으로 미래를 막는 일 자체가 성립하지 않는다. **H1을 쓸 수 있게 해 주는 전제다.**")
    P("")
    P("## 부수 효과 — H3·H4")
    P("")
    P("| 변동성 5분위 | n | 향후 QQQ(연율) | 향후 TQQQ(연율) | 추세 UP 비율 | UP 적중률 |")
    P("|---|---|---|---|---|---|")
    for x in H34:
        P("| %d | %d | %s | %s | %s | %s |" % (
            x["quintile"], x["n"], f(x["fwd_qqq_pct"]), f(x["fwd_tqqq_pct"]),
            fa(x["trend_up_share_pct"], 1), fa(x["trend_up_hit_pct"], 1)))
    P("")
    P("- **H3**: 최상위 5분위의 향후 QQQ가 %s, TQQQ가 %s다. 고변동 구간은 기대수익 자체가 낮다."
      % (f(H34[4]["fwd_qqq_pct"]), f(H34[4]["fwd_tqqq_pct"])))
    P("- **H4**: 추세 UP 신호의 적중률이 최상위 5분위에서 %s로 떨어진다 (다른 구간 %s~%s)."
      % (fa(H34[4]["trend_up_hit_pct"], 1),
         fa(min(x["trend_up_hit_pct"] for x in H34[:4]), 1),
         fa(max(x["trend_up_hit_pct"] for x in H34[:4]), 1)))
    P("- **그런데 바로 그 구간의 추세 UP 비율이 이미 %s뿐이다.** 중복성의 출처가 이 칸이다."
      % fa(H34[4]["trend_up_share_pct"], 1))
    P("")
    P("## 노출만 줄이면 안 되는가 — 상수 비중 대조")
    P("")
    P("추세 UP 구간에 게이트와 **같은 평균 노출**의 상수 비중을 둔다.")
    P("")
    P("| 구간 | 게이트 CAGR / MDD | 상수비중 CAGR / MDD | 평균 비중 |")
    P("|---|---|---|---|")
    for k, v in EC.items():
        P("| %s | %s / %s | %s / %s | %.2f |" % (
            k, f(v["gate_cagr"]), fa(v["gate_mdd"]), f(v["const_cagr"]), fa(v["const_mdd"]),
            v["const_mean_weight"]))
    P("")
    P("구간 B에서 게이트가 상수 비중보다 낙폭 %sp 낫다."
      % f(abs(EC["B 시뮬"]["const_mdd"]) - abs(EC["B 시뮬"]["gate_mdd"]), 1))
    P("**연속적으로 줄이는 것보다 덩어리째 빼는 편이 낙폭에 유리하다** — 그런데 순환이동 검정이 보여주듯")
    P("그 이득의 대부분은 「덩어리째 빼는 구조」에서 오지 「어느 덩어리를 빼는가」에서 오지 않는다.")
    P("")
    P("## 네 실험을 한 문장으로")
    P("")
    P("| 시도 | 결과 | 지금 보면 |")
    P("|---|---|---|")
    P("| SQQQ 숏 다리 | 기각 | **노출을 늘렸다** — 틀린 주마다 연 −52% 속도로 잃는다 |")
    P("| 일간 전환 | 기각 | **회전만 늘렸다** — 노출 구조는 그대로 |")
    P("| 변동성 게이트 | 부분 채택 | **노출을 덩어리째 줄였다** |")
    P("| 비대칭 진입/이탈 | 기각 | **노출 다이얼이었다** — 거울짝에서 낙폭 66/132 |")
    P("")
    P("**3배 상품에서는 도움이 되는 거의 모든 것이 노출 관리이고, 예측인 것은 거의 없다.**")
    P("네 번 중 셋이 기각된 것도, 하나가 살아남은 것도 같은 이유다.")
    P("")
    P("## 한계")
    P("")
    for c in [
        "**순환이동 검정의 surrogate는 서로 독립이 아니다.** 인접한 k는 거의 같은 시계열이므로 "
        "유효 표본 수는 1284보다 훨씬 적다. p값을 액면 그대로 읽으면 안 된다.",
        "**구간 A와 B는 겹친다** (A ⊂ B). 두 p값을 합쳐 강한 주장을 만들 수 없다.",
        "**게이트 하나(vol13w_p80)와 추세 하나(sma40_b0)만 분해했다.** 다른 조합에서 중복성의 크기가 다를 수 있다.",
        "**구간 B의 TQQQ는 시뮬레이션이다.** 다만 중복성·지속성·적중률은 QQQ에서 직접 관측된다.",
        "**끌림 분해는 σ의 5분위 평균을 쓴다.** 분위 안의 분산 때문에 E[σ²] > (E[σ])² 이므로 "
        "이론값이 과소평가되고, 최상위 분위에서 잔차가 커지는 것은 그 탓이 크다.",
    ]:
        P("- %s" % c)
    P("")

    path = os.path.join(OUT, "보고서-게이트원인분석.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    sys.stdout.write("썼다: %s (%d행)\n" % (path, len(L) + 1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
