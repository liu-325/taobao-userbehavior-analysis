from pathlib import Path
import json
import numpy as np
import pandas as pd
import duckdb
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / 'outputs' / 'tables'
PBI = ROOT / 'outputs' / 'powerbi'
PBI.mkdir(parents=True, exist_ok=True)
RAW = Path(r'D:\datasets\UserBehavior\prepared\clean_events.parquet')
con = duckdb.connect()
con.execute("PRAGMA threads=8")
con.execute("SET memory_limit='12GB'")
con.execute("PRAGMA temp_directory='D:/datasets/UserBehavior/duckdb_tmp'")
con.execute(f"CREATE VIEW events AS SELECT * FROM read_parquet('{RAW.as_posix()}')")


def save(df, name):
    p = T / name
    df.to_csv(p, index=False, encoding='utf-8-sig')
    # Power BI 也同步一份，方便模型直接导入。
    df.to_csv(PBI / name, index=False, encoding='utf-8-sig')
    print(name, df.shape)
    return p


# 1. 三种漏斗口径。这里不硬套 1%-5% 的行业经验，而是先把这份数据真实口径拆开。
tags = con.execute("""
WITH base AS (
  SELECT user_id,
         MAX(CASE WHEN behavior_code=1 THEN 1 ELSE 0 END) AS has_pv,
         MAX(CASE WHEN behavior_code IN (3,4) THEN 1 ELSE 0 END) AS has_intent,
         MAX(CASE WHEN behavior_code=2 THEN 1 ELSE 0 END) AS has_buy,
         MIN(CASE WHEN behavior_code=1 THEN event_ts END) AS min_pv_ts,
         MAX(CASE WHEN behavior_code IN (3,4) THEN event_ts END) AS max_intent_ts,
         MAX(CASE WHEN behavior_code=2 THEN event_ts END) AS max_buy_ts
  FROM events GROUP BY user_id
), intent_after AS (
  SELECT e.user_id, MIN(e.event_ts) AS min_intent_after_pv
  FROM events e JOIN base b USING(user_id)
  WHERE e.behavior_code IN (3,4) AND e.event_ts > b.min_pv_ts
  GROUP BY e.user_id
)
SELECT
  COUNT(*) AS active_users,
  COUNT(*) FILTER (WHERE has_pv=1) AS pv_users,
  COUNT(*) FILTER (WHERE has_intent=1) AS intent_users_all,
  COUNT(*) FILTER (WHERE has_buy=1) AS buyer_users_all,
  COUNT(*) FILTER (WHERE has_pv=1 AND has_intent=1) AS set_pv_intent_users,
  COUNT(*) FILTER (WHERE has_pv=1 AND has_intent=1 AND has_buy=1) AS set_pv_intent_buy_users,
  COUNT(*) FILTER (WHERE has_pv=1 AND min_pv_ts < max_intent_ts) AS ordered_pv_intent_users,
  COUNT(*) FILTER (WHERE i.min_intent_after_pv IS NOT NULL AND b.max_buy_ts > i.min_intent_after_pv) AS ordered_pv_intent_buy_users,
  COUNT(*) FILTER (WHERE has_buy=1 AND has_intent=0) AS buyers_without_intent
FROM base b LEFT JOIN intent_after i USING(user_id)
""").fetchdf().iloc[0]
rows = [
  {
    '口径': '用户级整体转化（只看最终是否购买）',
    'top_stage': '全部活跃用户', 'top_users': int(tags.active_users),
    'middle_stage': 'PV用户（独立集合）', 'middle_users': int(tags.pv_users),
    'bottom_stage': '购买用户（全部购买者）', 'bottom_users': int(tags.buyer_users_all),
    'top_to_middle': tags.pv_users/tags.active_users,
    'middle_to_bottom': tags.buyer_users_all/tags.pv_users,
    'overall': tags.buyer_users_all/tags.active_users,
    '说明': '分母为9天内有任意行为的用户；购买用户不要求先收藏/加购。'
  },
  {
    '口径': '用户级PV→收藏/加购→购买（集合交集）',
    'top_stage': 'PV用户', 'top_users': int(tags.pv_users),
    'middle_stage': 'PV且收藏/加购用户', 'middle_users': int(tags.set_pv_intent_users),
    'bottom_stage': 'PV+收藏/加购+购买用户', 'bottom_users': int(tags.set_pv_intent_buy_users),
    'top_to_middle': tags.set_pv_intent_users/tags.pv_users,
    'middle_to_bottom': tags.set_pv_intent_buy_users/tags.set_pv_intent_users,
    'overall': tags.set_pv_intent_buy_users/tags.pv_users,
    '说明': '三个阶段是包含关系，但不校验行为先后顺序。'
  },
  {
    '口径': '有向路径归因漏斗（时间顺序）',
    'top_stage': 'PV用户', 'top_users': int(tags.pv_users),
    'middle_stage': 'PV后收藏/加购用户', 'middle_users': int(tags.ordered_pv_intent_users),
    'bottom_stage': 'PV后收藏/加购再购买用户', 'bottom_users': int(tags.ordered_pv_intent_buy_users),
    'top_to_middle': tags.ordered_pv_intent_users/tags.pv_users,
    'middle_to_bottom': tags.ordered_pv_intent_buy_users/tags.ordered_pv_intent_users,
    'overall': tags.ordered_pv_intent_buy_users/tags.pv_users,
    '说明': '按event_ts校验先后顺序，适合定位路径流失，但仍不是session转化。'
  }
]
funnel_cmp = pd.DataFrame(rows)
save(funnel_cmp, '15_funnel_definition_comparison.csv')

# 2. 留存：先取 user-date 去重，再用 cohort 计算 D1/D3/D7。
activity = con.execute("SELECT DISTINCT user_id, event_date FROM events").fetchdf()
purchase = con.execute("SELECT DISTINCT user_id, event_date FROM events WHERE behavior_code=2").fetchdf()
first_seen = activity.groupby('user_id', as_index=False)['event_date'].min().rename(columns={'event_date':'first_date'})
activity = activity.merge(first_seen, on='user_id', how='left')
purchase = purchase.merge(first_seen, on='user_id', how='left')
max_date = activity.event_date.max()
ret_days = [1,3,7]
cohort_rows=[]
for cohort_date, g in activity.groupby('first_date'):
    cohort_size = g.user_id.nunique()
    row = {'cohort_date': str(cohort_date), 'cohort_size': int(cohort_size)}
    for n in ret_days:
        target = cohort_date + pd.Timedelta(days=n)
        row[f'D{n}_any_users'] = int(activity[(activity.first_date==cohort_date) & (activity.event_date==target)].user_id.nunique())
        row[f'D{n}_purchase_users'] = int(purchase[(purchase.first_date==cohort_date) & (purchase.event_date==target)].user_id.nunique())
        row[f'D{n}_any_rate'] = row[f'D{n}_any_users']/cohort_size
        row[f'D{n}_purchase_rate'] = row[f'D{n}_purchase_users']/cohort_size
    cohort_rows.append(row)
retention_by_cohort = pd.DataFrame(cohort_rows)
save(retention_by_cohort, '16_retention_by_cohort.csv')

# 全量和特定人群的留存，Dn只在窗口足够长的 cohort 上计算，避免把窗口截断误算成流失。
uv = pd.read_csv(PBI/'user_value_scores.csv', usecols=['user_id','segment'])
segments = {
  '全部用户': first_seen.user_id,
  '窗口内复购用户': purchase.groupby('user_id').event_date.nunique().loc[lambda s:s>=2].index,
  '高价值复购用户': uv.loc[uv.segment=='高价值复购用户','user_id'],
}
retention_rows=[]
curve_rows=[]
for seg_name, users in segments.items():
    users=set(users)
    fs=first_seen[first_seen.user_id.isin(users)]
    for n in ret_days:
        eligible_dates = set(fs.loc[fs.first_date <= max_date-pd.Timedelta(days=n),'first_date'].unique())
        base=fs[fs.first_date.isin(eligible_dates)].user_id
        cohort_map=fs.set_index('user_id').first_date
        targets=base.map(lambda x: cohort_map[x]+pd.Timedelta(days=n))
        # 先用 user_id 映射 cohort，再按目标日期合并，避免逐行 apply。
        sub=activity[activity.user_id.isin(set(base))].copy()
        sub['target_date']=sub.user_id.map(cohort_map)+pd.Timedelta(days=n)
        any_count=sub[sub.event_date==sub.target_date].user_id.nunique()
        psub=purchase[purchase.user_id.isin(set(base))].copy()
        psub['target_date']=psub.user_id.map(cohort_map)+pd.Timedelta(days=n)
        p_count=psub[psub.event_date==psub.target_date].user_id.nunique()
        row={'segment':seg_name,'day_n':n,'eligible_users':len(base),'any_users':int(any_count),'purchase_users':int(p_count),'any_retention':any_count/len(base),'purchase_retention':p_count/len(base)}
        retention_rows.append(row); curve_rows.append(row)
retention_summary=pd.DataFrame(retention_rows)
save(retention_summary, '17_retention_summary.csv')
save(pd.DataFrame(curve_rows), '18_retention_curve.csv')

# 3. 异动归因：11/30 -> 12/1，购买行为量下降，但活跃用户上升。
buy_dims = con.execute("""
WITH fs AS (
  SELECT user_id, MIN(event_date) AS first_date FROM events GROUP BY user_id
), buy AS (
  SELECT e.user_id, e.event_date, e.event_hour, e.category_id,
         CASE WHEN f.first_date=e.event_date THEN '当日首次出现用户' ELSE '历史已出现用户' END AS user_structure,
         CASE
           WHEN e.event_hour BETWEEN 0 AND 5 THEN '00-05'
           WHEN e.event_hour BETWEEN 6 AND 11 THEN '06-11'
           WHEN e.event_hour BETWEEN 12 AND 17 THEN '12-17'
           ELSE '18-23' END AS hour_bucket
  FROM events e JOIN fs f USING(user_id)
  WHERE e.behavior_code=2 AND e.event_date IN (DATE '2017-11-30', DATE '2017-12-01')
)
SELECT event_date, category_id, hour_bucket, user_structure, COUNT(*) AS buy_actions
FROM buy GROUP BY 1,2,3,4
""").fetchdf()
pivot = buy_dims.pivot_table(index=['category_id','hour_bucket','user_structure'],columns='event_date',values='buy_actions',aggfunc='sum',fill_value=0).reset_index()
pivot.columns=['category_id','hour_bucket','user_structure','prev_1130','curr_1201']
pivot['delta']=pivot.curr_1201-pivot.prev_1130
net_delta=pivot.delta.sum()
neg_pool=abs(pivot.loc[pivot.delta<0,'delta'].sum())
pos_pool=pivot.loc[pivot.delta>0,'delta'].sum()
pivot['negative_share']=pivot.delta.apply(lambda x: -x/neg_pool if x<0 else 0)
pivot['direction']=np.where(pivot.delta<0,'negative','positive')
pivot['net_delta_share']=pivot.delta/net_delta if net_delta else np.nan
pivot=pivot.sort_values('delta')
save(pivot, '19_anomaly_combined_contributions.csv')
# 维度汇总：给业务方看的归因表。
dim_frames=[]
for dim in ['user_structure','hour_bucket','category_id']:
    x=pivot.groupby(dim,as_index=False).agg(prev_1130=('prev_1130','sum'),curr_1201=('curr_1201','sum'),delta=('delta','sum'))
    x['dimension']=dim; x=x.rename(columns={dim:'value'}); dim_frames.append(x)
dim_summary=pd.concat(dim_frames,ignore_index=True)
dim_summary['share_of_negative_pool']=dim_summary.delta.apply(lambda x: -x/neg_pool if x<0 else 0)
dim_summary['share_of_net_delta']=dim_summary.delta/net_delta if net_delta else np.nan
save(dim_summary, '20_anomaly_dimension_summary.csv')
anomaly_summary=pd.DataFrame([{
 'prev_date':'2017-11-30','curr_date':'2017-12-01','prev_buy_actions':int(pivot.prev_1130.sum()),'curr_buy_actions':int(pivot.curr_1201.sum()),
 'delta_buy_actions':int(net_delta),'delta_pct':net_delta/pivot.prev_1130.sum(),
 'negative_pool':int(neg_pool),'positive_pool':int(pos_pool),
 'top_negative_cell':pivot.iloc[0].to_dict() if len(pivot) else {},
 'note':'份额分母是负向贡献合计，不是净下降，避免正负抵消造成误解。'
}])
save(anomaly_summary, '21_anomaly_summary.csv')

# 4. A/B 样本量：明确 32,538 是绝对 +1pp，不是相对 5%。
baseline=float(tags.set_pv_intent_buy_users/tags.set_pv_intent_users)
scenarios=[]
for name,mde_abs in [('绝对+1个百分点',0.01),('相对+5%',baseline*0.05)]:
    p2=baseline+mde_abs
    h=proportion_effectsize(baseline,p2)
    n=NormalIndPower().solve_power(effect_size=h,alpha=0.05,power=0.8,ratio=1,alternative='two-sided')
    scenarios.append({'scenario':name,'baseline_rate':baseline,'mde_absolute':mde_abs,'mde_relative':mde_abs/baseline,'target_rate':p2,'alpha':0.05,'power':0.8,'n_per_group':int(np.ceil(n)),'n_total':int(np.ceil(n)*2),'primary_metric':'收藏/加购→购买转化率','guardrails':'客均行为量、退款/退货率、投诉率、取消订阅率'})
ab=pd.DataFrame(scenarios)
save(ab,'22_ab_sample_size_plan.csv')

meta = {
 'funnel': json.loads(funnel_cmp.to_json(orient='records',force_ascii=False)),
 'retention': json.loads(retention_summary.to_json(orient='records',force_ascii=False)),
 'anomaly': json.loads(anomaly_summary.to_json(orient='records',force_ascii=False)),
 'ab': json.loads(ab.to_json(orient='records',force_ascii=False))
}
(T/'15_22_advanced_metrics.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(meta,ensure_ascii=False,indent=2))
