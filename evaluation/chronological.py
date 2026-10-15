"""Event-triggered v2 replay with strictly prior-day baselines and complete follow-up."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from rd.data import rows, detection_filter
from rd.config import DATA_DIR
from rd.detect import MIN_COUNT, MIN_LIFT, MIN_Z, WINDOW_DAYS


def run(output_path, start=None, end=None):
    daily=pd.DataFrame(rows(f'''select style,category,return_date,count(*) as n from returns
        where {detection_filter()} group by style,category,return_date'''))
    if daily.empty:
        raise ValueError('No eligible records for chronological replay.')
    daily['return_date']=pd.to_datetime(daily.return_date)
    dates=pd.date_range(daily.return_date.min(),daily.return_date.max(),freq='D')
    styles=np.array(sorted(daily['style'].unique()))
    mapping={value:i for i,value in enumerate(styles)}
    style_index=daily['style'].map(mapping).to_numpy(dtype=int)
    day_index=(daily.return_date-dates[0]).dt.days.to_numpy(dtype=int)
    totals=np.zeros((len(styles),len(dates)),dtype=np.int32)
    np.add.at(totals,(style_index,day_index),daily.n.to_numpy(dtype=np.int32))
    cum_totals=np.cumsum(totals,axis=1)
    window_totals=cum_totals.copy()
    window_totals[:,WINDOW_DAYS:]-=cum_totals[:,:-WINDOW_DAYS]
    company=totals.sum(axis=0)
    company_prior=np.cumsum(company)-company
    begin=0 if start is None else int(np.searchsorted(dates.values,np.datetime64(start)))
    finish=len(dates)-1 if end is None else int(np.searchsorted(dates.values,np.datetime64(end),side='right'))-1
    begin=max(0,begin);finish=min(len(dates)-1,finish)
    if begin>finish:
        raise ValueError('Evaluation range does not overlap this dataset.')
    records=[]
    for category in MIN_COUNT:
        mask=(daily.category==category).to_numpy()
        values=np.zeros_like(totals)
        np.add.at(values,(style_index[mask],day_index[mask]),daily.loc[mask,'n'].to_numpy(dtype=np.int32))
        cumulative=np.cumsum(values,axis=1)
        rolling=cumulative.copy()
        rolling[:,WINDOW_DAYS:]-=cumulative[:,:-WINDOW_DAYS]
        cat_company=values.sum(axis=0)
        prior=np.cumsum(cat_company)-cat_company
        # Match rd.data's four-decimal numeric transport, on both backends.
        p=np.round(np.divide(prior,company_prior,out=np.zeros(len(dates)),where=company_prior>0),4)
        variance=window_totals*p*(1-p)
        z=np.divide(rolling-window_totals*p,np.sqrt(variance),out=np.zeros_like(variance),where=variance>0)
        share=np.divide(rolling,window_totals,out=np.zeros_like(variance),where=window_totals>0)
        lift=np.divide(share,p,out=np.zeros_like(variance),where=p>0)
        hit=(rolling>=MIN_COUNT[category])&(lift>=MIN_LIFT[category])&(z>=MIN_Z)&(totals>0)
        hit[:,:begin]=False;hit[:,finish+1:]=False
        has_hit=hit.any(axis=1)
        first=hit.argmax(axis=1)
        first_report=np.full(len(styles),-1,dtype=int)
        for last in pd.date_range(dates[begin].replace(day=1),dates[finish],freq='ME'):
            if last<dates[begin]:
                continue
            day=int((last-dates[0]).days)
            month_begin=max(0,int((last.replace(day=1)-dates[0]).days))
            cn=cumulative[:,day]-(cumulative[:,month_begin-1] if month_begin else 0)
            tn=cum_totals[:,day]-(cum_totals[:,month_begin-1] if month_begin else 0)
            month_share=np.divide(cn,tn,out=np.zeros(len(styles)),where=tn>0)
            found=(cn>=30)&(p[day]>0)&(month_share>=MIN_LIFT[category]*p[day])
            first_report[(first_report<0)&found]=day
        for index in np.flatnonzero(has_hit):
            fd=int(first[index]);rd=int(first_report[index]);future=min(fd+28,len(dates)-1)
            future_cat=int(cumulative[index,future]-cumulative[index,fd])
            future_all=int(cum_totals[index,future]-cum_totals[index,fd])
            complete=future-fd==28
            persistent=bool(future_cat>=3 and future_all>0 and future_cat/future_all>=2*p[fd]) if complete else None
            records.append({'style':styles[index],'category':category,'flag_date':str(dates[fd].date()),
                'returns_at_flag':int(cumulative[index,fd]),
                'after_flag':int(cumulative[index,-1]-cumulative[index,fd]),'total':int(cumulative[index,-1]),
                'sustained_next_28d':persistent,'followup_complete':complete,
                'following_28d_category_returns':future_cat,'following_28d_all_returns':future_all,
                'baseline_share_at_flag':float(p[fd]),'window_returns':int(window_totals[index,fd]),
                'window_category_returns':int(rolling[index,fd]),
                'report_date':str(dates[rd].date()) if rd>=0 else None,
                'returns_at_report':int(cumulative[index,rd]) if rd>=0 else None,
                'lead_days':rd-fd if rd>=0 else None})
    columns=['style','category','flag_date','returns_at_flag','after_flag','total','sustained_next_28d',
             'followup_complete','following_28d_category_returns','following_28d_all_returns','baseline_share_at_flag',
             'window_returns','window_category_returns','report_date','returns_at_report','lead_days']
    df=pd.DataFrame(records,columns=columns)
    output_path=Path(output_path)
    output_path.parent.mkdir(parents=True,exist_ok=True)
    df.to_csv(output_path,index=False)
    complete=df[df.followup_complete] if len(df) else df
    comparable=df.dropna(subset=['report_date'])
    manifest=DATA_DIR/'manifest.json'
    summary={'dataset_version':2,'baseline':'strictly prior calendar days','trigger':'eligible style return arrival',
             'evaluation_from':str(dates[begin].date()),'evaluation_through':str(dates[finish].date()),
             'dataset_manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest() if manifest.is_file() else None,
             'signals':len(df),'complete_followup_cases':len(complete),
             'persistence_proxy':float(complete.sustained_next_28d.astype(bool).mean()) if len(complete) else None,
             'comparable_cases':len(comparable),'median_lead_days':float(comparable.lead_days.median()) if len(comparable) else None,
             'model_calls':0,'accuracy':None,
             'limitations':['No confirmed problem labels; persistence is not accuracy.',
                            'Month-end comparator uses >=30 records and different frequency; this is not incremental LLM value.',
                            'Undated final statuses, flags, shipment counts and fees are not historical features.'],
             'thresholds':{'window_days':WINDOW_DAYS,'min_count':MIN_COUNT,'min_lift':MIN_LIFT,'min_z':MIN_Z}}
    output_path.with_suffix('.summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
    return df,summary
