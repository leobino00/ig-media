# -*- coding: utf-8 -*-
"""experiment_asym.json → 보고서-비대칭진입이탈.md"""

import json
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "출력")
KINDS = ("대칭", "이탈빠름(진입느림)", "진입빠름(이탈느림)")


def f(x, nd=2, suf="%"):
    return "결측" if x is None else ("%+.*f%s" % (nd, x, suf))


def fa(x, nd=2, suf="%"):
    return "결측" if x is None else ("%.*f%s" % (nd, x, suf))


def main():
    with open(os.path.join(OUT, "experiment_asym.json"), encoding="utf-8") as fh:
        r = json.load(fh)
    A, B, M, V, D = r["A"], r["B"], r["mirror"], r["v2020"], r["dominance"]
    F = r["frontier"]
    n = r["n_rules"]
    L = []
    P = L.append

    P("# 비대칭 진입/이탈 — 나가는 속도와 들어오는 속도를 따로 정하면")
    P("")
    P("생성 %s · 설정 %d개 (대칭 %d · 이탈빠름 %d · 진입빠름 %d) · 게이트 `%s` · 전환비용 %.0fbp"
      % (r["generated_at"], n, r["kinds"]["대칭"], r["kinds"]["이탈빠름(진입느림)"],
         r["kinds"]["진입빠름(이탈느림)"], r["gate"], r["cost_bps"]))
    P("")
    P("> **실험 기록이다. 투자 판정이 아니다.** 어드바이저 프로토콜·판정기록부와 무관하다.")
    P("")
    P("## 먼저 바로잡을 것")
    P("")
    P("이 실험을 제안할 때 「나갈 땐 빠르게, 들어올 땐 천천히 → 2020 V자에서 잃은 절반을 되찾는다」고 적었다.")
    P("**틀렸다.** 진입을 늦추면 V자 회복은 더 놓친다. V를 되찾는 것은 *빠른 재진입*이고,")
    P("닷컴을 막는 것은 *느린 재진입*이다. 둘은 같은 다이얼의 반대쪽 끝이다.")
    P("그래서 이 실험은 **어느 한쪽이 낫다는 가설이 아니라, 프런티어가 있는지를 보는 실험**이고,")
    P("격자를 두 방향에 **대칭으로** 깔았다 (진입빠름 %d · 이탈빠름 %d)."
      % (r["kinds"]["진입빠름(이탈느림)"], r["kinds"]["이탈빠름(진입느림)"]))
    P("")
    P("## 답 — 프런티어가 맞다. 공짜 개선은 없다")
    P("")
    P("| 검사 | 결과 |")
    P("|---|---|")
    P("| 대칭 최선(`%s`)을 **닷컴과 2020 회복 둘 다에서** 이긴 설정 | **%d / %d** |"
      % (D["baseline_rule"], D["n_dominating"], n))
    P("")
    P("기준선은 닷컴 %s · 2020회복 %s · CAGR %s · MDD %s 다. **%d개 설정 중 하나도 두 구간을 동시에 개선하지 못했다.**"
      % (f(D["baseline"]["게이트|닷컴"]), f(D["baseline"]["게이트|2020회복"]),
         f(D["baseline"]["게이트|CAGR"]), fa(D["baseline"]["게이트|MDD"]), n))
    P("비대칭은 성능을 **옮길 뿐 늘리지 않는다.**")
    P("")
    P("## 부류별 성적")
    P("")
    for key, lab in (("B", "구간 B (2000~2026, 붕괴 포함)"), ("A", "구간 A (2010~2026)")):
        R = r[key]
        P("### %s — TQQQ 보유 %s / MDD %s" % (
            lab, f(R["bench"]["TQQQ"]["cagr_pct"]), fa(R["bench"]["TQQQ"]["mdd_pct"])))
        P("")
        P("| 부류 | CAGR 중앙 | MDD 중앙 | MAR 중앙 |")
        P("|---|---|---|---|")
        for pre in ("기본", "게이트"):
            for k in KINDS:
                tag = "%s|%s" % (pre, k)
                v = R["by_kind"][tag]
                P("| %s · %s | %s | %s | %.3f |" % (pre, k, f(v["cagr"]["median"]),
                                                    fa(v["mdd"]["median"]), v["mar"]["median"]))
        P("")
    P("게이트를 켠 상태에서 **진입빠름이 CAGR·MAR 모두 가장 높다.** 「손실은 빨리 끊어라」는 통념과 반대다.")
    P("다만 그대로 믿으면 안 되는 이유가 둘 있다 — 아래 두 절이 그것이다.")
    P("")
    P("## 교란 1 — 「진입이 빠르다」는 「노출이 많다」와 같은 말이다")
    P("")
    P("진입/이탈 파라미터를 **맞바꾼 거울짝** %d쌍을 비교했다. 거르는 양이 정확히 같고 방향만 반대다." % M["n"])
    P("")
    P("| 지표 | 진입빠름이 우세한 쌍 | 중앙 차이 |")
    P("|---|---|---|")
    P("| CAGR | **%d / %d** | %sp |" % (M["fast_in_better_cagr"], M["n"], f(M["median_d_cagr"])))
    P("| 최대낙폭 | %d / %d | %sp |" % (M["fast_in_better_mdd"], M["n"], f(M["median_d_mdd"])))
    P("| MAR | %d / %d | — |" % (M["fast_in_better_mar"], M["n"]))
    P("| 닷컴 구간 | **%d / %d** | %sp |" % (M["fast_in_better_dotcom"], M["n"], f(M["median_d_dotcom"])))
    P("| **TQQQ 보유기간** | — | **%sp** |" % f(M["median_d_pct_in"], 1, "%"))
    P("")
    P("거울짝으로도 노출 차이가 **%sp** 남는다. 그럴 수밖에 없다 —"
      % f(M["median_d_pct_in"], 1, "%"))
    P("**「빨리 들어가고 늦게 나온다」는 정의상 시장에 더 오래 있는 것**이기 때문이다.")
    P("즉 진입빠름의 CAGR 우위는 별개의 효과가 아니라 **노출을 늘린 결과**로 읽어야 한다.")
    P("")
    P("그리고 결정적으로, **낙폭은 %d/%d 로 반반이다** (중앙 차이 %sp, 사실상 0)."
      % (M["fast_in_better_mdd"], M["n"], f(M["median_d_mdd"])))
    P("**「빨리 나가면 낙폭을 줄인다」가 이 표본에서는 성립하지 않았다.**")
    P("이탈빠름이 확실히 이기는 곳은 닷컴 한 구간뿐이다 (%d/%d 에서 우세)."
      % (M["n"] - M["fast_in_better_dotcom"], M["n"]))
    P("")
    P("## 교란 2 — 2020 회복은 게이트가 이미 결정해 버린다")
    P("")
    P("| 조건 | 서로 다른 값 | 최빈값 비중 | 범위 |")
    P("|---|---|---|---|")
    P("| 게이트 **적용** | %d개 | **%.0f%%** | %s ~ %s |" % (
        V["gated_distinct"], 100 * V["gated_mode_share"], f(V["gated_range"][0]), f(V["gated_range"][1])))
    P("| 게이트 없음 | — | — | %s ~ %s |" % (f(V["base_range"][0]), f(V["base_range"][1])))
    P("")
    P("게이트를 켜면 %d개 설정 중 **%.0f%%가 2020 회복에서 똑같은 값**을 낸다." % (n, 100 * V["gated_mode_share"]))
    P("변동성이 높은 동안 게이트가 진입 자체를 막으므로, 진입을 아무리 빠르게 해도 들어갈 수가 없다.")
    P("**비대칭으로 2020 손실을 되찾겠다는 원래 발상은 이 지점에서 구조적으로 막힌다.**")
    P("")
    P("게이트를 끄면 비대칭이 살아난다 — 2020 회복 중앙값: %s."
      % " / ".join("%s %s" % (k, f(v)) for k, v in V["base_median_by_kind"].items()))
    P("진입을 늦추면 그 구간에서 %sp를 잃는다."
      % f(V["base_median_by_kind"]["이탈빠름(진입느림)"] - V["base_median_by_kind"]["대칭"]))
    P("")
    P("## 프런티어 — 닷컴 방어와 2020 회복은 맞바꾸는 관계다")
    P("")
    P("| 부류 | 닷컴 중앙 | 2020회복 중앙 | CAGR 중앙 | MDD 중앙 |")
    P("|---|---|---|---|---|")
    for k in KINDS:
        sub = [x for x in F if x["kind"] == k]
        P("| %s | %s | %s | %s | %s |" % (
            k, f(st.median([x["게이트|닷컴"] for x in sub])),
            f(st.median([x["게이트|2020회복"] for x in sub])),
            f(st.median([x["게이트|CAGR"] for x in sub])),
            fa(st.median([x["게이트|MDD"] for x in sub]))))
    P("")
    P("닷컴에서는 이탈빠름·대칭이 낫고 진입빠름이 나쁘다. 2020 회복은 게이트가 눌러 놓아 차이가 없다.")
    P("**두 구간을 동시에 개선하는 설정은 %d개 중 0개다.**" % n)
    P("")
    P("## 표본외")
    P("")
    P("| 부류 | 표본내 (%s~%s) | 표본외 (%s~%s) | 차 |" % (
        r["split"]["is_period"][0], r["split"]["is_period"][1],
        r["split"]["oos_period"][0], r["split"]["oos_period"][1]))
    P("|---|---|---|---|")
    for pre in ("기본", "게이트"):
        for k in KINDS:
            v = r["split"]["by_kind"]["%s|%s" % (pre, k)]
            P("| %s · %s | %s | %s | %sp |" % (pre, k, f(v["is_median"]), f(v["oos_median"]),
                                               f(v["oos_median"] - v["is_median"])))
    P("")
    P("모든 부류가 표본외에서 올랐다 — 2019~2026이 강세장이었기 때문이지 규칙의 힘이 아니다.")
    P("순위(진입빠름 > 대칭 > 이탈빠름)는 표본내·외에서 유지됐는데, **그것도 같은 이야기다** —")
    P("두 구간 모두 상승장이었고, 노출이 많은 쪽이 이겼다.")
    P("")
    P("## 결론")
    P("")
    P("1. **비대칭은 공짜 개선이 아니다.** %d개 설정 중 닷컴과 2020을 동시에 개선한 것이 0개다." % n)
    P("2. **「빨리 나가면 낙폭이 준다」는 이 표본에서 성립하지 않았다.** 거울짝 낙폭 비교가 %d/%d 로 반반이다."
      % (M["fast_in_better_mdd"], M["n"]))
    P("3. **진입 속도는 사실상 노출 다이얼이다.** 상승장 표본에서는 빠른 진입이 이기는데, 그것은")
    P("   전략의 우위가 아니라 시장에 더 오래 있었다는 뜻이다.")
    P("4. **게이트를 켜면 2020 구간에서 비대칭이 무력해진다** (%.0f%%가 동일값)." % (100 * V["gated_mode_share"]))
    P("")
    P("실무적으로는 **대칭을 기본값으로 두는 편이 정직하다.** 비대칭을 쓸 이유는")
    P("「어느 국면이 올지 안다」는 전제인데, 이 실험은 그 전제를 지지하지 않는다.")
    P("")
    P("## 한계")
    P("")
    for c in [
        "**두 극단 구간이 각각 한 번씩뿐이다.** 닷컴 1회·2020 1회로 프런티어의 모양을 확정할 수 없다.",
        "**구간 B는 시뮬레이션이다.** 다만 노출 비율과 전환 횟수는 모형과 무관하게 QQQ에서 관측된다.",
        "**확인지연은 주 단위다.** 일간 확인지연은 앞선 실험에서 일간 전환이 기각됐으므로 보지 않았다.",
        "**이동평균 길이를 20·40주 둘로 고정했다.** 다른 길이에서 프런티어 모양이 다를 수 있다.",
        "**세금·환율이 없다.** 국내 계좌 기준 세후·원화 수익률은 위 숫자보다 낮다.",
    ]:
        P("- %s" % c)
    P("")
    P("## 네 가설의 결말")
    P("")
    P("| 시도 | 결과 |")
    P("|---|---|")
    P("| SQQQ 숏 다리 | **기각.** 35개 규칙 전부 악화 |")
    P("| 일간 전환 | **기각.** 톱질로 두 구간 모두 악화 |")
    P("| 변동성 게이트 | **부분 채택.** 낙폭 58/60 개선, 수익률은 국면 의존 |")
    P("| 비대칭 진입/이탈 | **기각.** 프런티어를 옮길 뿐 넓히지 못한다 (%d/%d) |" % (D["n_dominating"], n))
    P("")

    path = os.path.join(OUT, "보고서-비대칭진입이탈.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    sys.stdout.write("썼다: %s (%d행)\n" % (path, len(L) + 1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
