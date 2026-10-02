"""계좌별 수익률 최우선 전략 근거.
A) PEN/IRP (1배 한정): 나스닥100 vs 반도체(SMH) — BH·적립·롤링
B) GLB: VT(TQQQ, max3) + U1 오버라이드 하이브리드 vs VT 단독 vs 반반 · 목표변동성 25/30 표본 외
"""
import pandas as pd, numpy as np
from bt import *; from strats import *; from dca import dca_vt, dca_u1, irr
df = base(); S = sleeves(df)
smh = load("SMH").pct_change().reindex(df.index)
S["SMH"] = smh.fillna(0.0) + 0.004/252
# ---------- A ----------
d = df["2000-06-06":]
Sd = {k: v.loc[d.index] for k, v in S.items()}
def bh_ret(col): return sim(d, one(d, "Q", pd.Series(True, index=d.index)).rename(columns={"Q": col}) if col!="Q" else one(d,"Q",pd.Series(True,index=d.index)), Sd)[0]
rq = bh_ret("Q")
t = pd.DataFrame(np.nan, index=d.index, columns=["SMH"]); t.iloc[0] = 1.0; rs = sim(d, t, Sd)[0]
rows=[]
for a,b in [("2000-06","2026-09"),("2000-06","2012-12"),("2013-01","2026-09"),("2016-01","2026-09")]:
    for n,r in [("QQQ",rq),("SMH",rs)]:
        s=stats(r[a:b], d.rf[a:b]); rows.append((a,n,round(s["CAGR"]*100,1),round(s["MDD"]*100),round(s["Sharpe"],2)))
print("A-1 BH:"); print(pd.DataFrame(rows,columns=["구간","자산","CAGR","MDD","샤프"]).to_string(index=False))
eq={"QQQ":(1+rq).cumprod(),"SMH":(1+rs).cumprod()}
ms=d.index.to_series().groupby(d.index.to_period("M")).min().values
for yrs in (5,10):
    diffs=[]
    for s0 in ms:
        i=d.index.searchsorted(s0+pd.DateOffset(years=yrs))
        if i>=len(d): break
        s1=d.index[i]; c=lambda x:(x[s1]/x[s0])**(1/yrs)-1; diffs.append(c(eq["SMH"])-c(eq["QQQ"]))
    dd=np.array(diffs); print(f"A-2 SMH−QQQ {yrs}년 창 {len(dd)}개: 승률 {(dd>0).mean():.0%} 중앙 {np.median(dd)*100:+.1f}%p 최악 {dd.min()*100:+.1f}%p")
# 적립 10년 창
BHq=one(d,"Q",pd.Series(True,index=d.index)).ffill(); BHs=pd.DataFrame(0.0,index=d.index,columns=["SMH"]); BHs["SMH"]=1.0
out={"QQQ":[],"SMH":[]}
for s0 in ms[::3]:
    i=d.index.searchsorted(s0+pd.DateOffset(years=10))
    if i>=len(d): break
    w=d.loc[s0:d.index[i]]; Sw={k:v.loc[w.index] for k,v in Sd.items()}
    vq,f=dca_vt(w,Sw,BHq.loc[w.index]); vs,_=dca_vt(w,Sw,BHs.loc[w.index])
    out["QQQ"].append(irr(vq,f,w.index[0],w.index[-1])); out["SMH"].append(irr(vs,f,w.index[0],w.index[-1]))
O=pd.DataFrame(out); print("A-3 적립 10년 IRR:", {k:(round(O[k].median()*100,1),round(O[k].min()*100,1)) for k in O}, "SMH 승률", round((O.SMH>O.QQQ).mean(),2))
# ---------- B ----------
def hybrid(df, S, tv=0.25, lmax=3.0, lb=40, floorL=1.5):
    """VT(TQQQ L/3, 변경 시만) + U1 오버라이드: 합성 TQQQ ≤ 전고점×0.5 → L 하한 floorL, 목표가(전고점)·×1.25·×1.5 도달 시 하한 해제 단계."""
    base_t = vt3(df, tv, lmax=lmax, lookback=lb, sleeve="Q3", rebalance="change").ffill()
    L = base_t.Q3*3
    p3=(1+lev(df,3)).cumprod().values; ath=p3[0]; holding=False; target=None; stage=0; Lf=np.zeros(len(df))
    for i in range(len(df)):
        p=p3[i]
        if not holding:
            ath=max(ath,p)
            if p<=ath*0.5: holding=True; target=ath; stage=0
        else:
            if stage<3 and p>=target*(1,1.25,1.5)[stage]: stage+=1
            if stage==3 or (stage>0 and p<target*0.9): holding=False; ath=max(ath,p)
        Lf[i]= floorL*(1-stage/3) if holding else 0.0
    L2=np.maximum(L.values, Lf)
    w=pd.DataFrame(0.0,index=df.index,columns=["Q","Q2","Q3"]); w["Q3"]=L2/3
    return emit(df,w)
BH=one(df,"Q",pd.Series(True,index=df.index)).ffill()
C={"VT25 TQQQ max3":vt3(df,0.25,lmax=3,sleeve="Q3",rebalance="change"),
   "VT30 TQQQ max3":vt3(df,0.30,lmax=3,sleeve="Q3",rebalance="change"),
   "하이브리드 VT25+U1 floor1.5":hybrid(df,S),
   "하이브리드 VT30+U1 floor1.5":hybrid(df,S,tv=0.30)}
rows=[]
bh=sim(df,BH,S)[0]
for k,t in C.items():
    r=sim(df,t,S)[0]
    for a,b in [("1999-03","2026-09"),("2013-01","2026-09")]:
        s=stats(r[a:b],df.rf[a:b]); rows.append((k,a[:4],round(s["CAGR"]*100,1),round(s["MDD"]*100),round(s["Sharpe"],2)))
for a,b in [("1999-03","2026-09"),("2013-01","2026-09")]:
    s=stats(bh[a:b],df.rf[a:b]); rows.append(("QQQ BH",a[:4],round(s["CAGR"]*100,1),round(s["MDD"]*100),round(s["Sharpe"],2)))
print("\nB-1:"); print(pd.DataFrame(rows,columns=["안","시작","CAGR","MDD","샤프"]).pivot_table(index="안",columns="시작",values=["CAGR","MDD"],sort=False).to_string())
ms=df.index.to_series().groupby(df.index.to_period("M")).min().values
out={k:[] for k in ["QQQM","U1","반반 TQQQ3"]+list(C)}
for s0 in ms[::3]:
    i=df.index.searchsorted(s0+pd.DateOffset(years=10))
    if i>=len(df): break
    w=df.loc[s0:df.index[i]]; Sw={k:v.loc[w.index] for k,v in S.items()}
    vb,f=dca_vt(w,Sw,BH.loc[w.index]); vu,_=dca_u1(w); v3,_=dca_vt(w,Sw,C["VT25 TQQQ max3"].loc[w.index])
    vals={"QQQM":vb,"U1":vu,"반반 TQQQ3":.5*v3+.5*vu}
    for k,t in C.items(): vals[k]=dca_vt(w,Sw,t.loc[w.index])[0]
    for k,v in vals.items(): out[k].append(irr(v,f,w.index[0],w.index[-1]))
O=pd.DataFrame(out)
print("\nB-2 적립 10년 IRR 71창:"); print(pd.DataFrame({"중앙":O.median(),"평균":O.mean(),"최저":O.min(),"QQQM 승률":(O.sub(O.QQQM,axis=0)>0).mean(),"최근10년(2016-09)":O.iloc[-1]}).round(3).to_string())
