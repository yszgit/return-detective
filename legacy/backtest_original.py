"""Backtest: daily scan per (style, category). Flag when trailing-28d count >= MIN and the
style's category share is far above the company baseline (binomial z). Compare to a
'monthly report' baseline that only reviews at month end with a 30-return threshold."""
import duckdb, pandas as pd, numpy as np
con = duckdb.connect('/home/claude/final/aldo.duckdb')
CATS = ['Quality','Fit: too small','Fit: too big','Expectation gap','Fulfilment error','Damaged in transit']
base = con.execute("select category, count(*)*1.0/(select count(*) from ret) p from ret group by 1").df().set_index('category')['p']
d = con.execute("""select style, rdate, category, count(*) n from ret where style is not null group by 1,2,3""").df()
d['rdate']=pd.to_datetime(d['rdate'])
tot = d.groupby(['style','rdate'])['n'].sum().rename('tot').reset_index()
MIN={'Quality':5,'Fit: too small':10,'Fit: too big':10,'Expectation gap':6,'Fulfilment error':6,'Damaged in transit':5}
LIFT={'Quality':4,'Fit: too small':2.5,'Fit: too big':2.5,'Expectation gap':3,'Fulfilment error':3,'Damaged in transit':4}
cases=[]
days = pd.date_range(d.rdate.min(), d.rdate.max())
for cat in CATS:
    c = d[d.category==cat][['style','rdate','n']]
    m = tot.merge(c, on=['style','rdate'], how='left').fillna({'n':0})
    m = m.set_index('rdate').groupby('style')[['tot','n']].apply(lambda g: g.reindex(days, fill_value=0).rolling('28D').sum()).reset_index()
    m.columns=['style','rdate','tot28','n28']
    p=base[cat]
    m['share']=m.n28/m.tot28.replace(0,np.nan)
    m['z']=(m.n28-m.tot28*p)/np.sqrt(m.tot28*p*(1-p)).replace(0,np.nan)
    hit = m[(m.n28>=MIN[cat])&(m.share>=LIFT[cat]*p)&(m.z>=4)]
    first = hit.groupby('style').agg(flag_date=('rdate','min')).reset_index()
    first['category']=cat
    cases.append(first)
cases=pd.concat(cases)
# outcomes: count of that category returns for style before/after flag; monthly-report baseline
allc = con.execute("select style, category, rdate from ret").df(); allc['rdate']=pd.to_datetime(allc.rdate)
rows=[]
for r in cases.itertuples():
    s=allc[(allc['style']==r.style)&(allc['category']==r.category)].sort_values('rdate')
    before=(s.rdate<=r.flag_date).sum(); after=(s.rdate>r.flag_date).sum()
    # monthly report: at month end, flag if month count >=30 and share >= LIFT*p
    mon=s.groupby(s.rdate.dt.to_period('M')).size()
    sm=allc[allc['style']==r.style].groupby(allc[allc['style']==r.style].rdate.dt.to_period('M')).size()
    rep=None
    for per,cnt in mon.items():
        if cnt>=30 and cnt/sm.get(per,1)>=LIFT[r.category]*base[r.category]:
            rep=per.end_time.normalize(); break
    rb = (s.rdate<=rep).sum() if rep is not None else None
    rows.append(dict(style=r.style, category=r.category, flag_date=r.flag_date.date(), returns_at_flag=before, after_flag=after,
                     total=len(s), report_date=rep.date() if rep is not None else None, returns_at_report=rb))
out=pd.DataFrame(rows)
out.to_csv('/home/claude/final/cases_backtest.csv', index=False)
print(len(out),'cases'); print(out.groupby('category').size())
both=out.dropna(subset=['report_date'])
print('cases also caught by monthly report:', len(both))
both=both.assign(lead_days=(pd.to_datetime(both.report_date)-pd.to_datetime(both.flag_date)).dt.days)
print(both[['returns_at_flag','returns_at_report','lead_days']].describe())
print(out.sort_values('total',ascending=False).head(25).to_string())
