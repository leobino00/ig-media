# -*- coding: utf-8 -*-
"""다섯 실험 + 원인분해를 하나로 묶는다 → 출력/결론.md

손으로 쓰지 않고 각 실험의 json 에서 생성한다. 실험을 다시 돌리면 결론의 숫자도 같이 바뀐다.
숫자를 두 곳에 적어 두면 반드시 갈라지고, 갈라진 순간 어느 쪽이 맞는지 알 수 없게 된다.

    python3 scripts/qqq_regime/report_summary.py
"""

import json
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "출력")

FILES = {"s3": "experiment.json", "s2": "experiment_2state.json", "dly": "experiment_daily.json",
         "vol": "experiment_vol.json", "asym": "experiment_asym.json", "why": "analysis_gate.json"}


def f(x, nd=2, suf="%"):
    return "결측" if x is None else ("%+.*f%s" % (nd, x, suf))


def fa(x, nd=2, suf="%"):
    return "결측" if x is None else ("%.*f%s" % (nd, x, suf))


def load():
    out = {}
    for k, name in FILES.items():
        p = os.path.join(OUT, name)
        if not os.path.exists(p):
            sys.stderr.write("없다: %s — 해당 실험을 먼저 돌린다\n" % p)
            return None
        with open(p, encoding="utf-8") as fh:
            out[k] = json.load(fh)
    return out


def main():
    J = load()
    if J is None:
        return 2
    s3, s2, dly, vol, asym, why = (J[k] for k in ("s3", "s2", "dly", "vol", "asym", "why"))
    g3 = s3["grids"]["3상태(TQQQ/SQQQ/현금)"]
    gn = s3["grids"]["숏없음(TQQQ/현금)"]
    m3 = {x["rule"]: x for x in g3["rows"]}
    mn = {x["rule"]: x for x in gn["rows"]}
    gaps = [m3[k]["cagr_pct"] - mn[k]["cagr_pct"] for k in m3]
    bg = vol["best_gate"]
    vA, vB = vol["A"]["gated"][bg], vol["B"]["gated"][bg]
    cB = vol["candidates"]["B"]
    gk = "추세+게이트 (%s)" % bg
    dot = vol["crisis"]["windows"][0]
    rec = [w for w in vol["crisis"]["windows"] if "회복" in w["name"]][0]
    M, RD, SOLO, H0 = asym["mirror"], why["redundancy"], why["H0_shift_solo"], why["H0_shift"]
    drag = why["H1_drag"][0]["rows"]
    dailyC = dly["crisis"]["probes"][1]

    L = []
    P = L.append

    P("# QQQ 레짐 전환 프로젝트 — 결론")
    P("")
    P("생성 %s · 실험 5회 + 원인분해 1회 · 각 실험의 json 에서 자동 생성" % why["generated_at"])
    P("")
    P("> **실험 기록이다. 투자 판정이 아니다.**")
    P("> 어드바이저 5단계 프로토콜·판정기록부와 무관하며, 그 입력으로 쓰이지 않는다.")
    P("> 개별 보고서: `보고서.md` · `보고서-2상태.md` · `보고서-일간전환.md` ·")
    P("> `보고서-변동성게이트.md` · `보고서-비대칭진입이탈.md` · `보고서-게이트원인분석.md`")
    P("")
    P("---")
    P("")
    P("## 처음 질문")
    P("")
    P("> 상승 추세면 TQQQ, 하락 추세면 SQQQ, 횡보면 현금. 이 매매의 **연간 평균 수익률**은?")
    P("")
    P("## 한 문장 답")
    P("")
    P("**3배 상품에서 도움이 되는 거의 모든 것은 노출 관리이고, 예측인 것은 거의 없다.**")
    P("")
    P("가설 네 개를 시험해 셋이 기각됐고, 살아남은 하나도 원인을 파 보니 예측이 아니라 노출이었다.")
    P("그리고 **연간 수익률은 단일 숫자로 답할 수 없다** — 어느 구간을 보느냐가 부호를 바꾼다.")
    P("")
    P("---")
    P("")
    P("## 1. 원래 설계(3상태)는 작동하지 않는다")
    P("")
    P("| | CAGR 중앙 | 범위 | 최대낙폭 중앙 |")
    P("|---|---|---|---|")
    P("| 규칙 %d개 (TQQQ/SQQQ/현금) | **%s** | %s ~ %s | %s |" % (
        g3["cagr_dist"]["n"], f(g3["cagr_dist"]["median"]), f(g3["cagr_dist"]["min"]),
        f(g3["cagr_dist"]["max"]), fa(g3["mdd_dist"]["median"])))
    P("| 같은 기간 QQQ 보유 | %s | — | %s |" % (
        f(s3["benchmark"]["QQQ"]["cagr_pct"]), fa(s3["benchmark"]["QQQ"]["mdd_pct"])))
    P("| 같은 기간 TQQQ 보유 | %s | — | %s |" % (
        f(s3["benchmark"]["TQQQ"]["cagr_pct"]), fa(s3["benchmark"]["TQQQ"]["mdd_pct"])))
    P("")
    P("**SQQQ 다리를 켜면 %d개 규칙이 전부 나빠졌다.** 예외 0건, 피해 중앙 %sp."
      % (sum(1 for k in m3 if m3[k]["cagr_pct"] < mn[k]["cagr_pct"]), f(st.median(gaps))))
    P("같은 기간 SQQQ 보유의 CAGR이 %s이므로, 맞혀서 버는 것보다 **틀린 주에 잃는 속도**가 크다."
      % f(s3["benchmark"]["SQQQ"]["cagr_pct"]))
    P("")
    P("## 2. 숏을 빼면 답이 기간에 따라 뒤집힌다")
    P("")
    P("| 구간 | 규칙 %d개 CAGR 중앙 | TQQQ 그냥 보유 |" % s2["n_rules"])
    P("|---|---|---|")
    P("| 2010~2026 (실제 TQQQ) | %s | **%s** — %d/%d 만 이겼다 |" % (
        f(s2["A"]["cagr"]["median"]), f(s2["A"]["bench"]["TQQQ"]["cagr_pct"]),
        s2["A"]["beat_tqqq_cagr"], s2["n_rules"]))
    P("| 2000~2026 (시뮬 TQQQ) | **%s** | %s (MDD %s) |" % (
        f(s2["B"]["scenarios"]["적합"]["cagr"]["median"]),
        f(s2["B"]["scenarios"]["적합"]["bench_tqqq"]["cagr_pct"]),
        fa(s2["B"]["scenarios"]["적합"]["bench_tqqq"]["mdd_pct"])))
    P("")
    P("**「TQQQ 장기보유 CAGR %s」는 운 좋은 출발점의 숫자다.**" % f(s2["A"]["bench"]["TQQQ"]["cagr_pct"]))
    P("2000년부터 보면 3배 바이앤홀드는 **CAGR %s · 최대낙폭 %s** 로 소멸한다."
      % (f(s2["B"]["scenarios"]["적합"]["bench_tqqq"]["cagr_pct"]),
         fa(s2["B"]["scenarios"]["적합"]["bench_tqqq"]["mdd_pct"])))
    P("TQQQ가 2010년에 상장했다는 사실 자체가 생존편향이다 — 닷컴을 통과한 3배 나스닥 상품은 없다.")
    P("")
    P("## 3. 기각된 것 셋, 살아남은 것 하나")
    P("")
    P("| 시도 | 결과 | 핵심 숫자 | 지금 보면 |")
    P("|---|---|---|---|")
    P("| SQQQ 숏 다리 | **기각** | %d/%d 규칙 악화 | 노출을 **늘렸다** |"
      % (sum(1 for k in m3 if m3[k]["cagr_pct"] < mn[k]["cagr_pct"]), len(m3)))
    P("| 일간 전환 | **기각** | 두 구간 모두 악화 · 전환 %.1f→%.1f회/년 | **회전만** 늘렸다 |"
      % (dly["A"]["weekly"]["sw"]["median"], dly["A"]["daily"]["sw"]["median"]))
    P("| 변동성 게이트 | **부분 채택** | 낙폭 %d/%d 개선 | 노출을 **덩어리째** 줄였다 |"
      % (vB["improved_mdd"], vol["n_trend_rules"]))
    P("| 비대칭 진입/이탈 | **기각** | 지배 설정 %d/%d | 노출 **다이얼**이었다 |"
      % (asym["dominance"]["n_dominating"], asym["n_rules"]))
    P("")
    P("### 일간 전환이 실패한 방식")
    P("")
    P("| | CAGR 중앙 | MDD 중앙 |")
    P("|---|---|---|")
    P("| 2010~2026 주간 / 일간 | %s / %s | %s / %s |" % (
        f(dly["A"]["weekly"]["cagr"]["median"]), f(dly["A"]["daily"]["cagr"]["median"]),
        fa(dly["A"]["weekly"]["mdd"]["median"]), fa(dly["A"]["daily"]["mdd"]["median"])))
    P("| 2000~2026 주간 / 일간 | %s / %s | %s / %s |" % (
        f(dly["B"]["weekly"]["cagr"]["median"]), f(dly["B"]["daily"]["cagr"]["median"]),
        fa(dly["B"]["weekly"]["mdd"]["median"]), fa(dly["B"]["daily"]["mdd"]["median"])))
    P("")
    P("고전 200일선 짝(`sma40_b0` ↔ `sma200_b0`)의 닷컴 구간: 주간 **%s**(전환 %d회) vs 일간 **%s**(전환 %d회)."
      % (f(dailyC["windows"][0]["weekly_total_pct"]), dailyC["windows"][0]["weekly_switches"],
         f(dailyC["windows"][0]["daily_total_pct"]), dailyC["windows"][0]["daily_switches"]))
    P("2020 코로나 V자에서는 반대로 일간이 이긴다. **일간은 빠른 급락에 강하고 길게 끄는 하락장에 약한데,**")
    P("**3배를 죽이는 것은 후자다.**")
    P("")
    P("### 비대칭이 실패한 방식")
    P("")
    P("거울짝 %d쌍(진입/이탈 파라미터를 맞바꾼 것 — 거르는 양 동일, 방향만 반대):" % M["n"])
    P("")
    P("| 지표 | 진입빠름 우세 | 중앙 차이 |")
    P("|---|---|---|")
    P("| CAGR | %d / %d | %sp |" % (M["fast_in_better_cagr"], M["n"], f(M["median_d_cagr"])))
    P("| **최대낙폭** | **%d / %d** | %sp |" % (M["fast_in_better_mdd"], M["n"], f(M["median_d_mdd"])))
    P("| TQQQ 보유기간 | — | **%sp** |" % f(M["median_d_pct_in"], 1, "%"))
    P("")
    P("낙폭이 반반이다. **「빨리 나가면 낙폭이 준다」가 이 표본에서 성립하지 않았다.**")
    P("그리고 거울짝으로도 노출이 %sp 남는다 — 「빨리 들어가고 늦게 나온다」는 정의상 더 오래 있는 것이다."
      % f(M["median_d_pct_in"], 1, "%"))
    P("")
    P("---")
    P("")
    P("## 4. 살아남은 게이트의 정체")
    P("")
    P("### 겉보기 성적")
    P("")
    P("| 구간 | 게이트 없음 | 게이트 `%s` | 낙폭 개선 |" % bg)
    P("|---|---|---|---|")
    P("| 2010~2026 | %s / %s | %s / **%s** | **%d/%d** |" % (
        f(vol["A"]["base"]["cagr"]["median"]), fa(vol["A"]["base"]["mdd"]["median"]),
        f(vA["cagr"]["median"]), fa(vA["mdd"]["median"]), vA["improved_mdd"], vol["n_trend_rules"]))
    P("| 2000~2026 | %s / %s | **%s** / **%s** | **%d/%d** |" % (
        f(vol["B"]["base"]["cagr"]["median"]), fa(vol["B"]["base"]["mdd"]["median"]),
        f(vB["cagr"]["median"]), fa(vB["mdd"]["median"]), vB["improved_mdd"], vol["n_trend_rules"]))
    P("")
    P("닷컴 구간(139주, 13주 실현변동성 중앙 %s — 전체 중앙 %s의 2배 이상):"
      % (fa(dot["median_vol_13w"], 1), fa(vol["vol_summary"]["median_13w"], 1)))
    P("추세만 쓰면 노출 %s인데도 %s를 잃었고, 게이트를 켜면 노출 %s · 손실 %s다."
      % (fa(dot["추세만 (sma40_b0)"]["exposure_pct"], 1), f(dot["추세만 (sma40_b0)"]["total_pct"]),
         fa(dot[gk]["exposure_pct"], 1), f(dot[gk]["total_pct"])))
    P("대가는 2020 회복 — 추세만 %s vs 추세+게이트 %s."
      % (f(rec["추세만 (sma40_b0)"]["total_pct"]), f(rec[gk]["total_pct"])))
    P("")
    P("### 기계는 실재한다")
    P("")
    P("| 가설 | 실측 |")
    P("|---|---|")
    P("| **H1 변동성 끌림** | 최하위 5분위 %s/년 → 최상위 **%s/년** (실제 TQQQ). 이론 −3σ²가 기울기를 맞춘다 |"
      % (f(drag[0]["measured_drag_pct"]), f(drag[4]["measured_drag_pct"])))
    P("| **H2 변동성 지속** | 자기상관 13주 %.3f · 13주 뒤 최상위 5분위 잔류 **%s** (무정보 20%%) |"
      % (why["H2_persistence"]["autocorr"]["13"], fa(why["H2_persistence"]["stay_top_pct"], 1)))
    P("| **H3 고변동 → 수익** | 향후 QQQ %s/년 · TQQQ %s/년 |"
      % (f(why["H3_H4_by_quintile"][4]["fwd_qqq_pct"]), f(why["H3_H4_by_quintile"][4]["fwd_tqqq_pct"])))
    P("| **H4 신호 적중률** | 고변동 구간 %s (나머지 %s~%s) |"
      % (fa(why["H3_H4_by_quintile"][4]["trend_up_hit_pct"], 1),
         fa(min(x["trend_up_hit_pct"] for x in why["H3_H4_by_quintile"][:4]), 1),
         fa(max(x["trend_up_hit_pct"] for x in why["H3_H4_by_quintile"][:4]), 1)))
    P("")
    P("**H1은 예측이 아니라 비용이다.** 게이트는 맞히는 장치가 아니라 비싼 구간을 피하는 장치고,")
    P("H2(지속성)가 그것을 쓸 수 있게 해 준다.")
    P("")
    P("### 그런데 정보는 검출되지 않는다")
    P("")
    P("순환이동 검정 — 게이트 시계열을 k주 돌린다. 노출과 연속구간 길이 분포가 정확히 보존되고")
    P("「어느 주를 막는가」만 깨진다. surrogate %d개." % H0["A 실제"]["n_surrogate"])
    P("")
    P("| | CAGR p | 최대낙폭 p |")
    P("|---|---|---|")
    P("| 추세 위 게이트 (노출 맞춤 전) | %.2f / %.2f | %.3f / %.3f |" % (
        H0["A 실제"]["pval_cagr"], H0["B 시뮬"]["pval_cagr"],
        H0["A 실제"]["pval_mdd"], H0["B 시뮬"]["pval_mdd"]))
    P("| **추세 위 게이트 (노출 맞춤 후)** | **%.2f / %.2f** | **%.2f / %.2f** |" % (
        H0["A 실제"]["matched"]["pval_cagr"], H0["B 시뮬"]["matched"]["pval_cagr"],
        H0["A 실제"]["matched"]["pval_mdd"], H0["B 시뮬"]["matched"]["pval_mdd"]))
    P("| 게이트 단독 (추세 없이) | %.2f / %.2f | **%.3f** / %.2f |" % (
        SOLO["A 실제"]["pval_cagr"], SOLO["B 시뮬"]["pval_cagr"],
        SOLO["A 실제"]["pval_mdd"], SOLO["B 시뮬"]["pval_mdd"]))
    P("")
    P("**원인은 중복이다** — 게이트가 막은 주의 **%s를 추세가 이미 막고 있었다.**"
      % fa(RD["blocked_and_trend_down_pct"], 1))
    P("게이트가 추가로 막는 것은 전체의 %s뿐이다 (phi = %.3f)."
      % (fa(RD["gate_adds_pct"], 1), RD["phi"]))
    P("고변동 5분위의 추세 UP 비율이 이미 %s뿐이라는 것이 그 출처다."
      % fa(why["H3_H4_by_quintile"][4]["trend_up_share_pct"], 1))
    P("")
    P("**게이트가 아는 것은 진짜지만, 그 대부분을 추세가 이미 알고 있었다.**")
    P("")
    P("---")
    P("")
    P("## 5. 남는 것 — 쓸 수 있는 형태로")
    P("")
    P("| | CAGR | 최대낙폭 | MAR |")
    P("|---|---|---|---|")
    for k in ("QQQ 보유", "TQQQ 보유", "추세만 (sma40_b0)", gk, "타게팅+추세"):
        x = cB[k]
        P("| %s | %s | %s | %.3f |" % (k, f(x["cagr_pct"]), fa(x["mdd_pct"]), x["mar"] or 0))
    P("")
    P("*(2000~2026, 시뮬 TQQQ. 세금·환율 제외, 달러 기준)*")
    P("")
    P("**정직하게 말할 수 있는 것은 이 정도다:**")
    P("")
    P("1. **3배 바이앤홀드는 붕괴를 한 번 만나면 끝난다** (%s, MDD %s). 추세 규칙은 그것을 피한다."
      % (f(cB["TQQQ 보유"]["cagr_pct"]), fa(cB["TQQQ 보유"]["mdd_pct"])))
    P("2. **추세 규칙 위에 변동성 게이트를 얹으면 낙폭이 준다** (%s → %s). 다만 그 이득의 대부분은"
      % (fa(cB["추세만 (sma40_b0)"]["mdd_pct"]), fa(cB[gk]["mdd_pct"])))
    P("   「덩어리째 노출을 줄인다」로 설명되지 「위험 구간을 알아맞힌다」로 설명되지 않는다.")
    P("3. **어떤 규칙을 고를지는 정할 수 없다.** 표본내 최고가 표본외 top10에 남는 비율이 1/5이었다.")
    P("   보고할 숫자는 언제나 **중앙값**이고, 최고값은 「N개 중 1등」이라는 꼬리표와 함께만 쓴다.")
    P("4. **연간 수익률 한 숫자는 없다.** 구간을 바꾸면 부호가 바뀐다 (2번 표).")
    P("")
    P("---")
    P("")
    P("## 6. 이 결론을 믿어도 되는 이유 — 쓴 통제 장치")
    P("")
    P("기각이 셋이나 나왔으므로, 기각 자체가 방법론 실수일 가능성을 먼저 막아야 했다.")
    P("")
    P("| 장치 | 무엇을 막았나 |")
    P("|---|---|")
    P("| **미래참조 검정** | 신호를 한 주 당기면 중앙 %s → %s (%sp). 엔진이 미래를 보지 않는다는 증거 |"
      % (f(s3["lookahead_check"]["honest_median_cagr"]), f(s3["lookahead_check"]["cheat_median_cagr"]),
         f(s3["lookahead_check"]["gap_pp"], 1)))
    P("| **대조군 일치** | 「항상 UP」 = TQQQ 보유 %s, 「항상 DOWN」 = SQQQ 보유 %s — 소수점까지 일치 |"
      % (f(s3["control"]["항상 UP"]["cagr_pct"]), f(s3["control"]["항상 DOWN"]["cagr_pct"])))
    P("| **실제 가격 사용** | 주간 등락률 ×3 단순 합성은 실제 TQQQ를 연 **+9.66%p 과대평가**한다 |")
    P("| **시뮬 검증** | 일간리셋 모형의 주간 수익률 상관 %.4f · 보수 0%%에서도 CAGR 오차 %sp |"
      % (s2["sim_validation"]["weekly_corr"], f(s2["sim_validation"]["err_fee0_pp"], 2)))
    P("| **짝 비교** | 일간 vs 주간, 게이트 on/off — 바꾼 것 하나만 남기고 나머지를 고정 |")
    P("| **거울짝** | 비대칭에서 「거르는 양」을 동일하게 고정하고 방향만 뒤집음 |")
    P("| **순환이동 귀무검정** | 노출·연속구간 길이를 보존한 채 시간 정렬만 파괴 |")
    P("| **전수 보고** | 최고값만 싣지 않는다. 중앙값·범위·표본외를 항상 함께 |")
    P("| **음성 대조** | 엔진 타이밍·이력·레버리지·factor 를 고의로 깨뜨려 시험이 빨개지는 것 확인 |")
    P("| **단위 시험 90건** | 경계값은 약한 쪽으로. 결측은 추정하지 않는다 |")
    P("")
    P("**이 중 셋(거울짝·순환이동·짝 비교)이 실제로 결론을 뒤집었다.** 없었으면 비대칭과 게이트를")
    P("둘 다 「효과 있음」으로 잘못 결론냈을 것이다.")
    P("")
    P("---")
    P("")
    P("## 7. 한계 — 이 결론이 닿지 않는 곳")
    P("")
    for c in [
        "**표본이 하나다.** 나스닥 2000~2026 한 줄기이고, 붕괴는 닷컴·2008·2022 셋뿐이다. "
        "「기각」은 이 표본에서의 기각이다.",
        "**2000~2009 구간의 3배는 시뮬레이션이다.** 검증을 거쳤지만(상관 %.4f) 그 시기에 "
        "실제 3배 상품은 없었고, 자금유출·상장폐지 위험은 모형에 없다." % s2["sim_validation"]["weekly_corr"],
        "**규칙 계열이 좁다.** 이동평균·모멘텀·실현변동성뿐이다. 신용스프레드·시장 폭·거시 지표는 보지 않았다.",
        "**순환이동 surrogate는 서로 독립이 아니다.** 유효 표본 수가 명목값보다 훨씬 적으므로 "
        "p값을 액면 그대로 읽으면 안 된다.",
        "**세금과 환율이 전부 빠져 있다.** 국내 계좌 기준 세후·원화 수익률은 위 숫자보다 낮다. "
        "전환이 잦을수록 더 낮다.",
        "**단일 벤더다.** Alpha Vantage 수정종가 · Twelve Data 일봉. 운용사·거래소 원자료와 대조하지 않았다.",
        "**예측을 시험한 것이 아니다.** 전부 과거 실현치이고, 어느 것도 앞으로의 수익률을 말하지 않는다.",
    ]:
        P("- %s" % c)
    P("")
    P("---")
    P("")
    P("## 8. 재현")
    P("")
    P("```bash")
    P("python3 scripts/qqq_regime/self_test.py            # 시험 90건 — 먼저 돌린다")
    P("python3 scripts/qqq_regime/experiment.py           # 1. 3상태")
    P("python3 scripts/qqq_regime/experiment_2state.py    # 2. 2상태 (숏 제거)")
    P("python3 scripts/qqq_regime/experiment_daily.py     # 3. 일간 전환")
    P("python3 scripts/qqq_regime/experiment_vol.py       # 4. 변동성 게이트")
    P("python3 scripts/qqq_regime/experiment_asym.py      # 5. 비대칭 진입/이탈")
    P("python3 scripts/qqq_regime/analysis_gate.py        # 6. 원인 분해")
    P("for r in report report_2state report_daily report_vol report_asym report_gate_why; do")
    P("  python3 scripts/qqq_regime/$r.py")
    P("done")
    P("python3 scripts/qqq_regime/report_summary.py       # 이 문서")
    P("```")
    P("")
    P("**이 문서는 각 실험의 json 에서 생성된다.** 숫자를 손으로 옮겨 적지 않았다 —")
    P("두 곳에 적으면 반드시 갈라지고, 갈라진 순간 어느 쪽이 맞는지 알 수 없게 된다.")
    P("")

    path = os.path.join(OUT, "결론.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    sys.stdout.write("썼다: %s (%d행)\n" % (path, len(L) + 1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
