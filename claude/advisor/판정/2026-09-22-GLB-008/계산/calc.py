import math, random, datetime as dt
random.seed(7)
# ---------- 1. 250만 공제 매년 활용 ----------
V0=12_669_976
def glb(r, harvest, cost=0.002, ter=0.0015, div=0.0007, years=26):
    g=r-ter-div; V=V0; B=V0
    for y in range(1,years+1):
        V*=1+g
        if harvest and y<years:
            gain=V-B
            if gain>0:
                h=min(gain,2_500_000); S=V*h/gain; c=cost*S
                B+=h-c; V-=c
    tax=0.22*max(V-B-2_500_000,0)
    return V-tax
def isa(r, ter=0.000068, div=0.0007, fx=0.0015, rate=0.099, exempt=2_000_000, years=26):
    v0=V0*(1-fx); g=r-ter-div; V=v0*(1+g)**years
    return V-rate*max(V-v0-exempt,0)
print("=== 250만 공제 매년 활용 ===")
for r in (0.06,0.08,0.10):
    a=glb(r,False); ah=glb(r,True); ah0=glb(r,True,cost=0.0)
    b=isa(r); b10=isa(r,ter=0.0010); b30=isa(r,ter=0.0030); bx=isa(r,rate=0.154,exempt=0); bx30=isa(r,ter=0.0030,rate=0.154,exempt=0)
    print(f"r={r:.0%} A={a:,.0f} A_harv(0.2%)={ah:,.0f} A_harv(0)={ah0:,.0f} | B={b:,.0f} B10={b10:,.0f} B30={b30:,.0f} Bx={bx:,.0f} Bx30={bx30:,.0f}")
    print(f"   B-A={b-a:,.0f}  B-Ah={b-ah:,.0f}~{b-ah0:,.0f}  B30-Ah={b30-ah:,.0f}~{b30-ah0:,.0f}  Bx-Ah={bx-ah:,.0f}~{bx-ah0:,.0f}  Bx30-Ah={bx30-ah:,.0f}~{bx30-ah0:,.0f}")
# ---------- 2. HYT monthly closes 2003-05..2026-09 ----------
c_new=[7.98,8.28,8.35,8.56,8.62,8.74,8.52,8.81,8.86, 8.90,9.48,9.51,9.50,9.52,9.79,9.75,9.65,9.55,9.58,9.88,9.90,
9.81,9.91,9.88,10.06,9.94,9.86,9.69,9.70,9.66,9.79,9.70,9.60, 9.43,8.73,8.43,8.63,9.25,9.08,8.92,8.56,8.76,8.72,8.96,9.28,
8.74,9.10,8.70,8.55,9.58,10.05,9.53,10.34,10.31,10.77,10.81,11.17, 12.34,12.11,12.17,12.20,12.60,12.44,12.32,12.07,12.00,11.74,11.43,11.10,
11.43,11.55,10.60,10.68,11.11,10.58,10.17,10.06,9.36,8.80,10.41,11.29, 11.20,11.17,10.93,10.75,10.51,10.64,10.72,10.16,10.58,10.26,10.25,10.01,
9.28,9.70,9.82,10.51,10.70,10.59,10.46,10.50,10.61,10.59,10.56,10.87, 10.94,10.96,11.18,11.30,11.13,11.34,10.96,11.15,11.27,10.92,11.16,11.05,
10.83,10.48,10.52,10.82,10.88,10.76,10.44,10.27,10.28,9.97,9.77,9.61, 9.78,9.96,10.39,9.87,9.97,10.58,10.79,11.20,11.39,11.16,11.52,11.25,
11.40,11.61,11.85,11.83,12.07,11.92,12.29,12.29,12.22,12.26,12.51,12.00, 12.17,11.74,12.08,11.76,11.37,11.80,11.98,12.57,13.03,12.90,12.72,12.93,
12.39,12.62,12.81,13.15,12.96,12.83,12.43,12.16,12.38,12.42,12.44,12.19, 11.38,11.61,11.41,10.57,11.21,11.31,11.97,12.04,11.81,11.73,11.79,11.65,
11.63,11.40,11.44,11.55,11.20,11.48,10.60,10.62,11.41,11.01,10.66,10.56, 10.60,10.22,9.69,9.89,9.47,8.99,8.30,8.19,7.45,6.51,6.30,7.06,
6.27,6.14,7.16,8.03,10.14,10.37,11.04,11.74,11.74,10.83,11.30,11.71, 11.77,11.91,12.40,12.53,12.15,12.17,13.47,13.69,13.65,13.62,13.50,13.72,
13.17,12.96,12.95,12.86,12.48,12.22,11.94,12.17,12.41,12.42,13.21,12.70, 12.18,12.82,13.12,13.79,14.32,14.30,13.85,13.70,13.46,13.92,14.52,14.64,
14.75,15.00,14.72,14.62,14.52,14.02,13.72,13.75,13.83,14.60,14.63,14.86, 14.84,14.23,14.22,13.91,13.61,13.51,15.00,15.02]
c=list(reversed(c_new)); n=len(c); print("months",n, "first",c[0],"last",c[-1])
lr=[math.log(c[i]/c[i-1]) for i in range(1,n)]
def sd(x): m=sum(x)/len(x); return math.sqrt(sum((v-m)**2 for v in x)/(len(x)-1))
sig_all=sd(lr)*math.sqrt(12); sig_10=sd(lr[-120:])*math.sqrt(12); sig_5=sd(lr[-60:])*math.sqrt(12)
mu_all=math.log(c[-1]/c[0])/((n-1)/12); mu_10=math.log(c[-1]/c[-121])/10
print(f"sigma all={sig_all:.3f} 10y={sig_10:.3f} 5y={sig_5:.3f}; price drift all={mu_all:.3%} 10y={mu_10:.3%}")
S0=7.98; B=9.00; T=(dt.date(2029,2,22)-dt.date(2026,9,22)).days/365.25; H=29
print("T years",round(T,3))
# empirical: within next H months, max close >= threshold
thr=B/S0; hits=0; tot=0
for i in range(0,n-H):
    tot+=1
    if max(c[i+1:i+H+1])>=c[i]*thr: hits+=1
print(f"empirical P(max close in {H}m >= +{thr-1:.2%}) = {hits}/{tot} = {hits/tot:.2%}")
# from local 12m-low starts
hits2=tot2=0
for i in range(12,n-H):
    if c[i]<=min(c[i-12:i+1]):
        tot2+=1
        if max(c[i+1:i+H+1])>=c[i]*thr: hits2+=1
print(f"  starting at 12m low: {hits2}/{tot2} = {hits2/tot2 if tot2 else 0:.2%}")
# analytic first passage
def Phi(x): return 0.5*(1+math.erf(x/math.sqrt(2)))
def p_hit(mu,sig):
    nu=mu-sig*sig/2; b=math.log(B/S0)
    return Phi((-b+nu*T)/(sig*math.sqrt(T))) + math.exp(2*nu*b/(sig*sig))*Phi((-b-nu*T)/(sig*math.sqrt(T)))
# MC for E[t|hit]
def mc(mu,sig,N=40000):
    dtm=1/12; steps=H; hit=0; tsum=0
    for _ in range(N):
        s=S0; 
        for k in range(1,steps+1):
            s*=math.exp((mu-sig*sig/2)*dtm+sig*math.sqrt(dtm)*random.gauss(0,1))
            if s>=B: hit+=1; tsum+=k*dtm; break
    return hit/N, (tsum/hit if hit else float('nan'))
c_drag=0.0372; g=B/S0-1
print("\n=== $9 도달 확률 ===")
for name,mu,sig in (("drift0/sig10y",0.0,sig_10),("drift0/sig_all",0.0,sig_all),("drift-3%/sig10y",mu_10,sig_10),("drift-2.7%/sig_all",mu_all,sig_all),("drift0/sig5y",0.0,sig_5)):
    p=p_hit(mu,sig); pm,et=mc(mu,sig)
    pstar=c_drag*T/(g-c_drag*et+c_drag*T)
    ev=pm*(g-c_drag*et)-(1-pm)*c_drag*T
    print(f"{name}: analytic p={p:.3f} MC p={pm:.3f} E[t|hit]={et:.2f}y  breakeven p*={pstar:.3f}  EV(wait)={ev:+.3%}")
# F103 basis
g0=9/8.24-1; T0=2.48
for et in (T0/2,):
    print(f"F103 basis (g={g0:.2%},T={T0}): p*={c_drag*T0/(g0-c_drag*et+c_drag*T0):.3f} with E[t|hit]=T/2")
# ---------- 3. deadline arithmetic ----------
val0=12_669_976; gain0=val0*(9/8.24-1); cost0=0.0372*val0; yrs0=gain0/cost0
print(f"\nF103: gain={gain0:,.0f} cost/yr={cost0:,.0f} breakeven={yrs0:.3f}y -> {dt.date(2026,9,1)+dt.timedelta(days=yrs0*365.25)}")
val1=1114*7.98*1374.38; gain1=val1*(9/7.98-1); cost1=0.0372*val1; yrs1=gain1/cost1
print(f"today: val={val1:,.0f} gain={gain1:,.0f} cost/yr={cost1:,.0f} breakeven={yrs1:.3f}y -> {dt.date(2026,9,22)+dt.timedelta(days=yrs1*365.25)}; cost to 2029-02-22={cost1*T:,.0f}")
# ---------- 4. 2008 KRW co-drawdowns (monthly method: May-08 close -> Dec-08 close / Dec-08 low x Dec FX; check Nov) ----------
fx={'may':1029.1,'nov':1467.9,'dec':1242.2}
data={'HYT':(11.74,6.27,5.02,6.14,4.59),'QQQ':(50.01,29.74,26.84,29.12,25.05),'SPY':(140.35,90.24,81.86,90.09,74.34),'EFA':(76.71,44.86,38.09,41.73,35.53),'VYM':(48.15,33.60,30.65,33.75,27.86)}
dd={}
for k,(mc_,dc,dl,nc,nl) in data.items():
    peak=mc_*fx['may']; close=min(dc*fx['dec'],nc*fx['nov'])/peak-1; low=min(dl*fx['dec'],nl*fx['nov'])/peak-1
    dd[k]=(close,low); print(f"{k}: close {close:.1%} low {low:.1%}")
w=(dd['SPY'][0]*0.6246+dd['EFA'][0]*0.3754, dd['SPY'][1]*0.6246+dd['EFA'][1]*0.3754); dd['WORLD']=w; print(f"WORLD(0.6246 SPY+EFA): close {w[0]:.1%} low {w[1]:.1%}")
tdf=(0.735*w[0],0.735*w[1]); dd['TDF']=tdf; print(f"TDF proxy(0.735 world): close {tdf[0]:.1%} low {tdf[1]:.1%}")
# 2022 co-drawdowns from ALL-007 §1-4
dd22={'QQQ':(-0.291,-0.323),'WORLD':(-0.145,-0.171),'VYM':(-0.010,-0.042),'HYT':(-0.250,-0.277),'TDF':(-0.15,-0.15),'CASH':(0,0)}
dd['CASH']=(0,0)
HYTv=12_217_853; NDX=1_850_526; SCHD=1_845_357; TDFv=1_617_923; CASH=18_999
ports={'지금':{'HYT':HYTv,'QQQ':NDX,'VYM':SCHD,'TDF':TDFv,'CASH':CASH},
 'PEN-005 실행 후(3.2M/2.8M)':{'HYT':HYTv,'QQQ':NDX+3_200_000,'WORLD':2_800_000,'VYM':SCHD,'TDF':TDFv,'CASH':CASH},
 '확정 종착(HYT→QQQM, PEN 3.2/2.8)':{'HYT':0,'QQQ':NDX+3_200_000+HYTv,'WORLD':2_800_000,'VYM':SCHD,'TDF':TDFv,'CASH':CASH},
 'QQQ 100%':{'QQQ':1}}
print("\n=== 시나리오 낙폭 (원화) ===")
for pn,p in ports.items():
    tot=sum(p.values())
    r08=[sum(p[k]/tot*dd[k][i] for k in p) for i in (0,1)]; r22=[sum(p[k]/tot*dd22[k][i] for k in p) for i in (0,1)]
    print(f"{pn}: 2008 close {r08[0]:.1%} low {r08[1]:.1%} | 2022 close {r22[0]:.1%} low {r22[1]:.1%} | HYT w={p.get('HYT',0)/tot:.1%}")
# old GLB-006 assumption HYT -30 -> new
print("\n분배금: 1114*0.0779 =",1114*0.0779,"USD =",round(1114*0.0779*1374.38),"KRW/월 ; 연",round(12*1114*0.0779*1374.38))
print("VXUS 1주 87.15 USD =",round(87.15*1374.38),"KRW")
