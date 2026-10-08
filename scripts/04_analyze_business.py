from pathlib import Path
import json, math
import numpy as np
import pandas as pd
import duckdb
from scipy import stats
from statsmodels.stats.proportion import proportions_ztest, confint_proportions_2indep

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "tables"
OUT.mkdir(parents=True, exist_ok=True)
PARQUET = Path(r"D:\datasets\UserBehavior\prepared\clean_events.parquet")
con = duckdb.connect()
con.execute("PRAGMA threads=8")
con.execute("SET memory_limit='12GB'")
con.execute("PRAGMA temp_directory='D:/datasets/UserBehavior/duckdb_tmp'")
con.execute(f"CREATE VIEW events AS SELECT * FROM read_parquet('{PARQUET.as_posix()}')")


def save(df, name, excel=False):
    path = OUT / name
    df.to_csv(path, index=False, encoding='utf-8-sig')
    if excel:
        df.to_excel(OUT / (Path(name).stem + '.xlsx'), index=False)
    print(name, df.shape)
    return path


# 1. 总体 KPI。先说明白：这份数据没有价格字段，所以不能算 GMV，只能算购买行为量/购买用户。
kpi = con.execute("""
SELECT
  COUNT(*) AS behaviors,
  COUNT(DISTINCT user_id) AS active_users,
  COUNT(DISTINCT item_id) AS active_items,
  COUNT(DISTINCT category_id) AS active_categories,
  COUNT(*) FILTER (WHERE behavior_code=1) AS pv_actions,
  COUNT(*) FILTER (WHERE behavior_code=2) AS buy_actions,
  COUNT(*) FILTER (WHERE behavior_code=3) AS cart_actions,
  COUNT(*) FILTER (WHERE behavior_code=4) AS fav_actions,
  COUNT(DISTINCT CASE WHEN behavior_code=1 THEN user_id END) AS pv_users,
  COUNT(DISTINCT CASE WHEN behavior_code=2 THEN user_id END) AS buyer_users,
  COUNT(DISTINCT CASE WHEN behavior_code IN (3,4) THEN user_id END) AS intent_users
FROM events
""").fetchdf()
r = kpi.iloc[0]
kpi['buyer_penetration'] = kpi['buyer_users'] / kpi['active_users']
kpi['pv_user_to_buyer_rate'] = kpi['buyer_users'] / kpi['pv_users']
kpi['intent_user_to_buyer_rate'] = kpi['buyer_users'] / kpi['intent_users']
kpi['buy_per_active_user'] = kpi['buy_actions'] / kpi['active_users']
kpi['pv_per_active_user'] = kpi['pv_actions'] / kpi['active_users']
save(kpi, '01_overall_kpi.csv')

# 2. 行为结构。这里可以看到浏览占绝对多数，购买行为其实很稀疏。
mix = con.execute("""
SELECT behavior_type, COUNT(*) AS actions,
       COUNT(DISTINCT user_id) AS users,
       COUNT(DISTINCT item_id) AS items
FROM events GROUP BY behavior_type
ORDER BY CASE behavior_type WHEN 'pv' THEN 1 WHEN 'cart' THEN 2 WHEN 'fav' THEN 3 WHEN 'buy' THEN 4 END
""").fetchdf()
mix['action_share'] = mix['actions'] / mix['actions'].sum()
save(mix, '02_behavior_mix.csv')

# 3. 日报。new_users 只代表“在这个窗口里第一次出现”，不是平台真正的新客。
daily = con.execute("""
WITH first_seen AS (
  SELECT user_id, MIN(event_date) AS first_date FROM events GROUP BY user_id
), d AS (
  SELECT event_date,
         COUNT(DISTINCT user_id) AS active_users,
         COUNT(DISTINCT CASE WHEN behavior_code=2 THEN user_id END) AS buyer_users,
         COUNT(*) FILTER (WHERE behavior_code=1) AS pv_actions,
         COUNT(*) FILTER (WHERE behavior_code=2) AS buy_actions,
         COUNT(*) FILTER (WHERE behavior_code=3) AS cart_actions,
         COUNT(*) FILTER (WHERE behavior_code=4) AS fav_actions
  FROM events GROUP BY event_date
)
SELECT d.*, COUNT(*) FILTER (WHERE f.first_date=d.event_date) AS first_seen_users
FROM d LEFT JOIN first_seen f ON f.first_date = d.event_date
GROUP BY ALL ORDER BY event_date
""").fetchdf()
daily['buyer_rate'] = daily['buyer_users'] / daily['active_users']
daily['buy_actions_per_active_user'] = daily['buy_actions'] / daily['active_users']
daily['buy_to_pv_action_ratio'] = daily['buy_actions'] / daily['pv_actions']
save(daily, '03_daily_metrics.csv')

# 4. 小时趋势。业务上这个比“周几”更容易落地到推送时间。
hourly = con.execute("""
SELECT event_hour,
       COUNT(DISTINCT user_id) AS active_users,
       COUNT(DISTINCT CASE WHEN behavior_code=2 THEN user_id END) AS buyer_users,
       COUNT(*) FILTER (WHERE behavior_code=1) AS pv_actions,
       COUNT(*) FILTER (WHERE behavior_code=2) AS buy_actions,
       COUNT(*) FILTER (WHERE behavior_code=3) AS cart_actions,
       COUNT(*) FILTER (WHERE behavior_code=4) AS fav_actions
FROM events GROUP BY event_hour ORDER BY event_hour
""").fetchdf()
hourly['buyer_rate'] = hourly['buyer_users'] / hourly['active_users']
hourly['buy_actions_per_active_user'] = hourly['buy_actions'] / hourly['active_users']
hourly['buy_to_pv_action_ratio'] = hourly['buy_actions'] / hourly['pv_actions']
save(hourly, '04_hourly_metrics.csv')

# 5. 用户集合漏斗。不是严格行为序列漏斗：一个用户只要在窗口内有过某行为就会进对应层。
funnel = con.execute("""
WITH flags AS (
  SELECT user_id,
         MAX(CASE WHEN behavior_code=1 THEN 1 ELSE 0 END) AS has_pv,
         MAX(CASE WHEN behavior_code IN (3,4) THEN 1 ELSE 0 END) AS has_intent,
         MAX(CASE WHEN behavior_code=2 THEN 1 ELSE 0 END) AS has_buy
  FROM events GROUP BY user_id
)
SELECT stage, stage_users FROM (
  SELECT 0 AS ord, '浏览用户' AS stage, COUNT(*) FILTER (WHERE has_pv=1) AS stage_users FROM flags
  UNION ALL
  SELECT 1, '收藏/加购用户', COUNT(*) FILTER (WHERE has_pv=1 AND has_intent=1) FROM flags
  UNION ALL
  SELECT 2, '购买用户', COUNT(*) FILTER (WHERE has_pv=1 AND has_intent=1 AND has_buy=1) FROM flags
) ORDER BY ord
""").fetchdf()
funnel['stage_to_next'] = funnel['stage_users'].shift(-1) / funnel['stage_users']
funnel['stage_from_first'] = funnel['stage_users'] / funnel.loc[0, 'stage_users']
save(funnel, '05_funnel_overall.csv')

# 6. 品类漏斗。类别 ID 没有名称，所以不硬编业务名，报告里按 ID 和相对表现讲。
cat = con.execute("""WITH cu AS (
  SELECT category_id, user_id,
         COUNT(*) FILTER (WHERE behavior_code=1) AS pv_actions,
         COUNT(*) FILTER (WHERE behavior_code=2) AS buy_actions,
         COUNT(*) FILTER (WHERE behavior_code=3) AS cart_actions,
         COUNT(*) FILTER (WHERE behavior_code=4) AS fav_actions,
         MAX(CASE WHEN behavior_code=1 THEN 1 ELSE 0 END) AS has_pv,
         MAX(CASE WHEN behavior_code IN (3,4) THEN 1 ELSE 0 END) AS has_intent,
         MAX(CASE WHEN behavior_code=2 THEN 1 ELSE 0 END) AS has_buy
  FROM events GROUP BY category_id, user_id
)
SELECT category_id,
       SUM(pv_actions+buy_actions+cart_actions+fav_actions) AS actions,
       COUNT(*) FILTER (WHERE has_pv=1) AS pv_users,
       COUNT(*) FILTER (WHERE has_pv=1 AND has_intent=1) AS intent_users,
       COUNT(*) FILTER (WHERE has_pv=1 AND has_intent=1 AND has_buy=1) AS buyer_users,
       COUNT(*) FILTER (WHERE has_buy=1) AS all_buyer_users,
       COUNT(*) FILTER (WHERE has_buy=1 AND has_intent=0) AS direct_buy_without_intent_users,
       SUM(pv_actions) AS pv_actions,
       SUM(buy_actions) AS buy_actions,
       SUM(cart_actions) AS cart_actions,
       SUM(fav_actions) AS fav_actions
FROM cu
GROUP BY category_id
HAVING COUNT(*) FILTER (WHERE has_pv=1) >= 200
ORDER BY pv_users DESC
""").fetchdf()
cat['pv_to_intent'] = cat['intent_users'] / cat['pv_users']
cat['intent_to_buy'] = cat['buyer_users'] / cat['intent_users'].replace(0, np.nan)
cat['pv_to_buy'] = cat['buyer_users'] / cat['pv_users']
cat['direct_buy_share'] = cat['direct_buy_without_intent_users'] / cat['all_buyer_users']
cat['buy_to_pv_action_ratio'] = cat['buy_actions'] / cat['pv_actions']
save(cat, '06_funnel_by_category.csv')

# 7. 用户价值分层。数据没有金额，所以不硬叫 RFM；使用 R/F + 互动强度 E。
buyer = con.execute("""
SELECT user_id,
       8 - MAX(event_day) AS recency_days,
       COUNT(*) FILTER (WHERE behavior_code=2) AS buy_actions,
       COUNT(*) FILTER (WHERE behavior_code IN (3,4)) AS engagement_actions,
       COUNT(*) FILTER (WHERE behavior_code=1) AS pv_actions,
       COUNT(DISTINCT CASE WHEN behavior_code=2 THEN event_date END) AS purchase_days,
       MAX(event_day) AS last_buy_day_0based
FROM events
GROUP BY user_id
HAVING COUNT(*) FILTER (WHERE behavior_code=2) > 0
""").fetchdf()
# 用数据自己的分位数切档，避免我手拍阈值后解释不通。
def score_low_good(s):
    # 间隔天数越小越好，所以低分位给 5 分。rank(method='first') 防止大量并列值把 qcut 卡住。
    return 6 - pd.qcut(s.rank(method='first'), 5, labels=False).astype(int)
def score_high_good(s):
    return pd.qcut(s.rank(method='first'), 5, labels=False).astype(int) + 1
buyer['r_score'] = score_low_good(buyer['recency_days'])
buyer['f_score'] = score_high_good(buyer['buy_actions'])
buyer['e_score'] = score_high_good(buyer['engagement_actions'])

def segment(x):
    if x.f_score >= 4 and x.r_score >= 4:
        return '高价值复购用户'
    if x.e_score >= 4 and x.f_score <= 2:
        return '高互动潜力用户'
    if x.r_score <= 2 and x.f_score >= 3:
        return '高价值流失风险'
    if x.r_score >= 4 and x.f_score >= 3:
        return '近期购买用户'
    return '一般购买用户'
buyer['segment'] = buyer.apply(segment, axis=1)
seg = buyer.groupby('segment', as_index=False).agg(
    users=('user_id','nunique'), buy_actions=('buy_actions','sum'),
    engagement_actions=('engagement_actions','sum'), avg_recency_days=('recency_days','mean'),
    avg_buy_actions=('buy_actions','mean')
)
seg['user_share'] = seg['users'] / seg['users'].sum()
seg['buy_action_share'] = seg['buy_actions'] / seg['buy_actions'].sum()
seg = seg.sort_values('buy_action_share', ascending=False)
save(seg, '07_rfm_segments.csv')
# Power BI 要用用户明细，就导出精简列，别把 100m 日志往看板里硬塞。
buyer[['user_id','recency_days','buy_actions','engagement_actions','pv_actions','purchase_days','r_score','f_score','e_score','segment']].to_csv(
    ROOT / 'outputs' / 'powerbi' / 'user_value_scores.csv', index=False, encoding='utf-8-sig')

# 8. 复购。窗口只有 9 天，所以“复购”是窗口内重复购买，不能说长期复购率。
repurchase = con.execute("""
WITH b AS (
  SELECT user_id, COUNT(*) AS buy_actions FROM events WHERE behavior_code=2 GROUP BY user_id
)
SELECT COUNT(*) AS buyers,
       COUNT(*) FILTER (WHERE buy_actions>=2) AS repeat_buyers,
       COUNT(*) FILTER (WHERE buy_actions=1) AS one_time_buyers,
       AVG(buy_actions) AS avg_buy_actions_per_buyer,
       AVG(buy_actions) FILTER (WHERE buy_actions>=2) AS avg_buy_actions_repeat_buyers
FROM b
""").fetchdf()
repurchase['repeat_buyer_rate'] = repurchase['repeat_buyers'] / repurchase['buyers']
save(repurchase, '08_repurchase_summary.csv')

# 9. 准实验对比：周末 vs 工作日，用户-日为单位。用户可重复出现，后面报告要写清相关性局限。
user_day = con.execute("""
SELECT event_date, user_id,
       MAX(is_weekend) AS is_weekend,
       MAX(CASE WHEN behavior_code=2 THEN 1 ELSE 0 END) AS buyer,
       COUNT(*) FILTER (WHERE behavior_code=1) AS pv_actions,
       COUNT(*) FILTER (WHERE behavior_code=2) AS buy_actions
FROM events GROUP BY event_date, user_id
""").fetchdf()
weekend = user_day[user_day.is_weekend == 1]
weekday = user_day[user_day.is_weekend == 0]
seg_time = pd.DataFrame([
    {'segment':'周末','units':len(weekend),'buyers':int(weekend.buyer.sum())},
    {'segment':'工作日','units':len(weekday),'buyers':int(weekday.buyer.sum())},
])
seg_time['buyer_rate'] = seg_time['buyers'] / seg_time['units']
save(seg_time, '09_weekend_user_day.csv')

# 10. 时段：用户-小时为单位，白天 06:00-17:59，晚上 18:00-23:59。
user_hour = con.execute("""
SELECT event_hour, user_id,
       CASE WHEN event_hour BETWEEN 6 AND 17 THEN '白天(06-17)' ELSE '晚上(18-23)' END AS daypart,
       MAX(CASE WHEN behavior_code=2 THEN 1 ELSE 0 END) AS buyer,
       COUNT(*) FILTER (WHERE behavior_code=1) AS pv_actions,
       COUNT(*) FILTER (WHERE behavior_code=2) AS buy_actions
FROM events
WHERE event_hour BETWEEN 6 AND 23
GROUP BY event_hour, user_id
""").fetchdf()
seg_hour = user_hour.groupby('daypart', as_index=False).agg(units=('user_id','size'), buyers=('buyer','sum'))
seg_hour['buyer_rate'] = seg_hour['buyers'] / seg_hour['units']
save(seg_hour, '10_hour_daypart_user_hour.csv')

# 11. 检验：z 检验 + 卡方 + 效应量。样本大时 p 值会很容易显著，所以同时看百分点差、RR 和 Cohen's h。
def test_two_groups(a_name, a_success, a_n, b_name, b_success, b_n, unit):
    counts = np.array([a_success, b_success], dtype=float)
    nobs = np.array([a_n, b_n], dtype=float)
    z, p = proportions_ztest(counts, nobs, alternative='two-sided')
    p1, p2 = counts / nobs
    # 卡方是作为稳健性检查，和两比例 z 检验在 2x2 表里结果一致。
    table = [[a_success, a_n-a_success], [b_success, b_n-b_success]]
    chi2, chi_p, dof, expected = stats.chi2_contingency(table, correction=False)
    diff = p1 - p2
    rr = p1 / p2 if p2 > 0 else np.nan
    odds_ratio = ((a_success/(a_n-a_success)) / (b_success/(b_n-b_success))) if (a_n>a_success and b_n>b_success) else np.nan
    h = 2*np.arcsin(np.sqrt(p1)) - 2*np.arcsin(np.sqrt(p2))
    try:
        ci_low, ci_high = confint_proportions_2indep(a_success, a_n, b_success, b_n, method='newcomb')
    except Exception:
        ci_low = ci_high = np.nan
    return {
      'comparison': f'{a_name} vs {b_name}', 'unit': unit,
      'group_a': a_name, 'n_a': int(a_n), 'success_a': int(a_success), 'rate_a': p1,
      'group_b': b_name, 'n_b': int(b_n), 'success_b': int(b_success), 'rate_b': p2,
      'rate_difference_pp': diff*100, 'ci95_low_pp': ci_low*100, 'ci95_high_pp': ci_high*100,
      'relative_lift_pct': (rr-1)*100 if pd.notna(rr) else np.nan,
      'risk_ratio': rr, 'odds_ratio': odds_ratio, 'cohens_h': h,
      'z_stat': z, 'z_p_value': p, 'chi2_stat': chi2, 'chi2_p_value': chi_p
    }
wk = weekend.buyer.sum(); wd = weekday.buyer.sum()
tests = [
    test_two_groups('周末', wk, len(weekend), '工作日', wd, len(weekday), '用户-日'),
]
daytime = seg_hour[seg_hour.daypart.str.startswith('白天')].iloc[0]
evening = seg_hour[seg_hour.daypart.str.startswith('晚上')].iloc[0]
tests.append(test_two_groups('晚上(18-23)', evening.buyers, evening.units, '白天(06-17)', daytime.buyers, daytime.units, '用户-小时'))
tests_df = pd.DataFrame(tests)
save(tests_df, '11_statistical_tests.csv')

# 12. 留存/回访：9 天数据只适合叫窗口内回访，不适合包装成标准 30 日留存。
retention = con.execute("""
WITH first_seen AS (
  SELECT user_id, MIN(event_date) AS cohort_date FROM events GROUP BY user_id
), pairs AS (
  SELECT f.cohort_date,
         date_diff('day', f.cohort_date, e.event_date) AS day_n,
         COUNT(DISTINCT e.user_id) AS users
  FROM first_seen f JOIN events e USING(user_id)
  WHERE date_diff('day', f.cohort_date, e.event_date) BETWEEN 0 AND 8
  GROUP BY 1,2
)
SELECT * FROM pairs ORDER BY cohort_date, day_n
""").fetchdf()
# D0 为 100%，后面是相对首次出现日的窗口内回访。
base = retention[retention.day_n==0].set_index('cohort_date')['users']
retention['cohort_size'] = retention['cohort_date'].map(base)
retention['retention_rate'] = retention['users'] / retention['cohort_size']
save(retention, '12_retention_descriptive.csv')

# 13. 行为转移矩阵，按 user_id 取 1% 用户，避免把 100m 全序列都拉回 pandas。
trans = con.execute("""
WITH sampled AS (
  SELECT user_id, event_ts, item_id, behavior_type FROM events WHERE user_id % 100 = 0
), seq AS (
  SELECT user_id, behavior_type,
         LEAD(behavior_type) OVER (PARTITION BY user_id ORDER BY event_ts, item_id) AS next_behavior
  FROM sampled
)
SELECT behavior_type AS from_behavior, next_behavior AS to_behavior, COUNT(*) AS transitions
FROM seq WHERE next_behavior IS NOT NULL
GROUP BY 1,2 ORDER BY transitions DESC
""").fetchdf()
save(trans, '13_behavior_transition_matrix.csv')

# 14. 建议量化：用当前观察到的比例做增量估算，不是拍脑袋承诺。
funnel_map = dict(zip(funnel.stage, funnel.stage_users))
high_pot = buyer[buyer.segment == '高互动潜力用户']
high_val = buyer[buyer.segment == '高价值复购用户']
# 所有进入 buyer 表的人都至少买过一次，所以“购买率”都是 100%，没有比较意义。
# 这里改成比较购买频次，估算的是“多出来的购买行为次数”，不是承诺新增人数。
potential_avg_buy = high_pot.buy_actions.mean() if len(high_pot) else np.nan
high_value_avg_buy = high_val.buy_actions.mean() if len(high_val) else np.nan
intent_users = int(funnel_map['收藏/加购用户'])
pv_users = int(funnel_map['浏览用户'])
buyers = int(funnel_map['购买用户'])
current_intent_to_buy = buyers / intent_users
current_pv_to_intent = intent_users / pv_users
weekend_rate = weekend.buyer.mean()
weekday_rate = weekday.buyer.mean()
incremental_if_weekend = max(0, (weekday_rate - weekend_rate)) * len(weekend)
incremental_if_potential = len(high_pot)  # 保守口径：每人多买 1 次，不假设直接追平 5.39 次
incremental_if_evening = max(0, (evening.buyer_rate - daytime.buyer_rate)) * evening.units
recs = pd.DataFrame([
  {'lever':'收藏/加购→购买提升1个百分点', 'est_incremental_buyers':intent_users*0.01, 'basis':'以当前收藏/加购用户数为基数'},
  {'lever':'浏览→收藏/加购提升1个百分点', 'est_incremental_buyers':pv_users*0.01*current_intent_to_buy, 'basis':'按当前加购/收藏→购买转化折算'},
  {'lever':'高互动潜力用户人均多购买1次', 'est_incremental_buyers':incremental_if_potential, 'basis':f'高互动潜力用户 {len(high_pot)} 人；不假设追平高价值用户 {high_value_avg_buy:.2f} 次'},
  {'lever':'周末购买率回到工作日水平', 'est_incremental_buyers':incremental_if_weekend, 'basis':'用户-日粒度，受用户重复出现影响'},
  {'lever':'晚间购买率较白天继续高出当前差值', 'est_incremental_buyers':incremental_if_evening, 'basis':'用户-小时粒度，仅描述性估算'},
])
save(recs, '14_recommendation_estimates.csv')

# 15. 生成报告/看板需要的公共元数据。
quality = {
  'raw_rows': 100150807,
  'invalid_window_rows': 55576,
  'valid_rows_before_dedup': 100095231,
  'exact_duplicate_rows_removed': 49,
  'clean_rows': 100095182,
  'clean_users': int(kpi.active_users.iloc[0]),
  'clean_items': int(kpi.active_items.iloc[0]),
  'clean_categories': int(kpi.active_categories.iloc[0]),
  'behavior_mix': mix.set_index('behavior_type')['actions'].to_dict(),
  'paucity_note': '原始数据无价格/订单金额，无法计算 GMV；用购买行为次数与购买用户数替代。'
}
(ROOT/'outputs'/'profile'/'analysis_metrics.json').write_text(json.dumps(quality, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
print('analysis done')
