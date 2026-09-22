# IRP-003 계산 — 전환액 재대입 · 순편익 표 · 환헤지 비교 (원자료: ALL-006 §1-2 9/21 시세, FRED 9/17, BOK 8/27, Twelve Data 월봉)
HYT=12_217_853; NDX=1_850_526; SCHD=1_845_357; TDF=1_617_923; CASH=18_999
TOT0=HYT+NDX+SCHD+TDF+CASH; KODEX_US=0.6246
print("전체(9/21)",TOT0)
def room(s, pen_ndx, pen_kodex, cap, veu=0):
    tot=TOT0+pen_ndx+pen_kodex
    us=HYT+NDX+SCHD+TDF*s+pen_ndx+pen_kodex*KODEX_US
    tot2=tot  # VEU 매수는 예수금(측정 제외)→VEU(비미국): 분모에 veu 추가
    tot2=tot+veu
    r=cap*tot2-us
    X=r/(1-s); return us/tot2, r, X, X*0.5
print("\n=== 12월 전환액 재대입 (TDF→미국채, 축소 50%) ===")
for name,pn,pk in (("PEN 3.9/2.1 (IRP-002 원 등록)",3_900_000,2_100_000),("PEN 3.2/2.8 (ALL-006 재산출)",3_200_000,2_800_000)):
    for cap in (0.9453,0.9203):
        for s in (0.498,0.3444):
            e,r,X,X50=room(s,pn,pk,cap)
            print(f"{name} cap={cap:.4f} TDF미국={s:.1%}: 노출 {e:.2%} 여유 {r:,.0f} X={X:,.0f} X×50%={X50:,.0f} {'→ <300,000 미실행' if X50<300_000 else ''}")
# GLB-008 VEU 1주(약 117,000원) 반영: 3.2/2.8·92.03·49.8
e,r,X,X50=room(0.498,3_200_000,2_800_000,0.9203,veu=117_000)
print(f"+VEU 1주(117,000): 노출 {e:.2%} 여유 {r:,.0f} X50={X50:,.0f}")
# 조건 ① 임계 TDF 미국분 (여유 0) — 92.03/3.2/2.8 및 94.53/3.9/2.1
for cap,pn,pk in ((0.9203,3_200_000,2_800_000),(0.9453,3_900_000,2_100_000)):
    tot=TOT0+pn+pk; base=HYT+NDX+SCHD+pn+pk*KODEX_US
    s_star=(cap*tot-base)/TDF; print(f"조건① 임계 TDF 미국분 cap={cap}: {s_star:.1%}")
# IRP 위험자산 비율
print(f"\nIRP 위험자산 {(NDX+SCHD)/(NDX+SCHD+TDF+CASH):.2%}, 70% 여유 {0.70*(NDX+SCHD+TDF+CASH)-(NDX+SCHD):,.0f}")
# 순편익 표 (F007)
print("\n=== 순편익 표 (전환액 X 기준) ===")
FF=3.88; BOK=3.00; hedge=FF-BOK; UST=5.29
for X in (350_569, 330_000, 5_307):
    print(f"-- X={X:,}")
    for E in (6,8,10):
        tdf=0.735*E+0.178*3.0+0.078*2.97-0.40
        ustH=UST-hedge-0.05; ustU=UST-0.05  # 언헤지 TER 결측 → 0.05 가정 표기
        dragH=tdf-ustH; dragU=tdf-ustU
        cum26H=X*((1+tdf/100)**26-(1+ustH/100)**26); cum26U=X*((1+tdf/100)**26-(1+ustU/100)**26)
        print(f"  E={E}%: TDF {tdf:.2f}% vs UST(H) {ustH:.2f}% 열위 {dragH:+.2f}%p/년 = 연 {X*dragH/100:,.0f}원, 26년 누적 {cum26H:,.0f}원 | 언헤지 {ustU:.2f}% 열위 {dragU:+.2f}%p 26년 {cum26U:,.0f}원")
    # 편익 (사건당, 1회성): 닷컴 UST +31.4% vs TDF −30~−55% ; 금융위기 +36.9% vs TDF 2008 대리 −18.4/−24.6 ; 2022 −30.3 vs TDF −15
    for ev,u,t in (("닷컴(H)",0.314,(-0.30,-0.55)),("금융위기(H)",0.369,(-0.184,-0.246)),("긴축2022(H)",-0.303,(-0.15,-0.15))):
        print(f"  {ev}: 편익 {X*(u-t[0]):,.0f} ~ {X*(u-t[1]):,.0f}원")
    # 언헤지 원화 (KRW 약세: 닷컴 +10.6%, GFC +20.7%, 2022 +5.9%)
    for ev,u,fx,t in (("닷컴(언헤지)",0.314,1.106,(-0.30,-0.55)),("금융위기(언헤지)",0.369,1.207,(-0.184,-0.246)),("긴축2022(언헤지)",-0.303,1.059,(-0.15,-0.15))):
        ur=(1+u)*fx-1; print(f"  {ev}: UST 원화 {ur:+.1%} → 편익 {X*(ur-t[0]):,.0f} ~ {X*(ur-t[1]):,.0f}원")
# 예외 낙폭 개선 %p (F019): 포트폴리오 23.55M 기준, X=350,569
P=23_550_658
for X in (350_569,):
    for t in (-0.30,-0.55):
        print(f"예외 낙폭 개선 (X={X:,}, TDF 닷컴 {t:.0%}): {(0.314-t)*X/P*100:.2f}%p ; 통상(2022) 악화 {(-0.303+0.15)*X/P*100:.2f}%p")
