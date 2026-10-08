from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / 'outputs' / 'tables'
M = ROOT / 'outputs' / 'mysql'
checks = []

def add(name, py_value, my_value, tol=0):
    if tol:
        same = abs(float(py_value)-float(my_value)) <= tol
    else:
        same = int(py_value) == int(my_value)
    checks.append({'check': name, 'python': round(float(py_value),6), 'mysql': round(float(my_value),6), 'match': same})

py = pd.read_csv(T/'01_overall_kpi.csv').iloc[0]
my = pd.read_csv(M/'overall_kpi.csv').iloc[0]
for col in ['behaviors','active_users','active_items','active_categories','pv_actions','buy_actions','cart_actions','fav_actions']:
    add(f'overall.{col}', py[col], my[col])
pm = pd.read_csv(T/'02_behavior_mix.csv').set_index('behavior_type'); mm = pd.read_csv(M/'behavior_mix.csv').set_index('behavior_type')
for b in pm.index: add(f'behavior.{b}.actions', pm.loc[b,'actions'], mm.loc[b,'actions'])
pf = pd.read_csv(T/'05_funnel_overall.csv'); mf = pd.read_csv(M/'funnel_strict.csv')
for i in range(3): add(f'funnel.{pf.loc[i,"stage"]}', pf.loc[i,'stage_users'], mf.loc[i,'stage_users'])
# 日/小时：对关键数值逐行对账。
pdaily=pd.read_csv(T/'03_daily_metrics.csv').sort_values('event_date'); mdaily=pd.read_csv(M/'daily_metrics.csv').sort_values('event_date')
for col in ['active_users','buyer_users','pv_actions','buy_actions']:
    for a,b in zip(pdaily[col],mdaily[col]): add(f'daily.{col}',a,b)
ph=pd.read_csv(T/'04_hourly_metrics.csv').sort_values('event_hour'); mh=pd.read_csv(M/'hourly_metrics.csv').sort_values('event_hour')
for col in ['active_users','buyer_users','pv_actions','buy_actions']:
    for a,b in zip(ph[col],mh[col]): add(f'hourly.{col}',a,b)
pr=pd.read_csv(T/'08_repurchase_summary.csv').iloc[0]; mr=pd.read_csv(M/'repurchase_window.csv').iloc[0]
for col in ['buyers','repeat_buyers','one_time_buyers']: add(f'repurchase.{col}',pr[col],mr[col])
add('repurchase.avg_buy_actions_per_buyer',pr.avg_buy_actions_per_buyer,mr.avg_buy_actions_per_buyer,tol=0.001)
# 周末/工作日。
pw=pd.read_csv(T/'09_weekend_user_day.csv').set_index('segment'); mw=pd.read_csv(M/'weekend_weekday_user_day.csv').set_index('segment')
for s in ['周末','工作日']:
    add(f'weekend.{s}.units',pw.loc[s,'units'],mw.loc[s,'user_days'])
    add(f'weekend.{s}.buyers',pw.loc[s,'buyers'],mw.loc[s,'buyer_user_days'])
    add(f'weekend.{s}.rate',pw.loc[s,'buyer_rate'],mw.loc[s,'buyer_rate'],tol=0.0001)
# 品类 Top20。
pc=pd.read_csv(T/'06_funnel_by_category.csv').set_index('category_id'); mc=pd.read_csv(M/'category_funnel_top20.csv').set_index('category_id')
for cid in mc.index:
    for col in ['pv_users','intent_users','buyer_users']:
        add(f'category.{cid}.{col}',pc.loc[cid,col],mc.loc[cid,col])
    add(f'category.{cid}.intent_to_buy',pc.loc[cid,'intent_to_buy'],mc.loc[cid,'intent_to_buy'],tol=0.0001)
out={'all_match':all(x['match'] for x in checks),'checks':checks,'count':len(checks)}
(M/'validation_python_vs_mysql.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print('all_match',out['all_match'],'checks',out['count'],'failed',sum(not x['match'] for x in checks))
