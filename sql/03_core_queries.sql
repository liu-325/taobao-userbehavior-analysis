-- name: overall_kpi
-- 第一版我直接对 FROM_UNIXTIME(event_ts) 做日期过滤，EXPLAIN 显示 type=ALL 且要读整表。
-- 后来改成先用 event_ts 的整数边界缩小范围，下一步建索引才能命中；输出时才转中国时区。
SELECT
  COUNT(*) AS behaviors,
  COUNT(DISTINCT user_id) AS active_users,
  COUNT(DISTINCT item_id) AS active_items,
  COUNT(DISTINCT category_id) AS active_categories,
  SUM(CASE WHEN behavior_code=1 THEN 1 ELSE 0 END) AS pv_actions,
  SUM(CASE WHEN behavior_code=2 THEN 1 ELSE 0 END) AS buy_actions,
  SUM(CASE WHEN behavior_code=3 THEN 1 ELSE 0 END) AS cart_actions,
  SUM(CASE WHEN behavior_code=4 THEN 1 ELSE 0 END) AS fav_actions,
  COUNT(DISTINCT CASE WHEN behavior_code=1 THEN user_id END) AS pv_users,
  COUNT(DISTINCT CASE WHEN behavior_code=2 THEN user_id END) AS buyer_users,
  COUNT(DISTINCT CASE WHEN behavior_code IN (3,4) THEN user_id END) AS intent_users
FROM fact_user_behavior
WHERE event_ts BETWEEN 1511539200 AND 1512316799;

-- name: behavior_mix
SELECT
  CASE behavior_code
    WHEN 1 THEN 'pv' WHEN 2 THEN 'buy' WHEN 3 THEN 'cart' WHEN 4 THEN 'fav'
  END AS behavior_type,
  COUNT(*) AS actions,
  COUNT(DISTINCT user_id) AS users,
  COUNT(DISTINCT item_id) AS items
FROM fact_user_behavior
WHERE event_ts BETWEEN 1511539200 AND 1512316799
GROUP BY behavior_code
ORDER BY behavior_code;

-- name: funnel_strict
-- 集合交集归因漏斗：下一层必须同时包含上一层，所以转化率不会超过 100%。
WITH flags AS (
  SELECT user_id,
         MAX(CASE WHEN behavior_code=1 THEN 1 ELSE 0 END) AS has_pv,
         MAX(CASE WHEN behavior_code IN (3,4) THEN 1 ELSE 0 END) AS has_intent,
         MAX(CASE WHEN behavior_code=2 THEN 1 ELSE 0 END) AS has_buy
  FROM fact_user_behavior
  WHERE event_ts BETWEEN 1511539200 AND 1512316799
  GROUP BY user_id
)
SELECT stage, stage_users
FROM (
  SELECT 0 AS ord, '浏览用户' AS stage, COUNT(*) AS stage_users FROM flags WHERE has_pv=1
  UNION ALL
  SELECT 1, '收藏/加购用户', COUNT(*) FROM flags WHERE has_pv=1 AND has_intent=1
  UNION ALL
  SELECT 2, '购买用户', COUNT(*) FROM flags WHERE has_pv=1 AND has_intent=1 AND has_buy=1
) t
ORDER BY ord;

-- name: daily_metrics
-- 先把 session 设成 UTC，再加 8 小时得到中国业务日期，避免服务器时区一变口径就变。
SET SESSION time_zone = '+00:00';
WITH first_seen AS (
  SELECT user_id,
         DATE(DATE_ADD(FROM_UNIXTIME(MIN(event_ts)), INTERVAL 8 HOUR)) AS first_date
  FROM fact_user_behavior
  WHERE event_ts BETWEEN 1511539200 AND 1512316799
  GROUP BY user_id
), daily AS (
  SELECT DATE(DATE_ADD(FROM_UNIXTIME(event_ts), INTERVAL 8 HOUR)) AS event_date,
         COUNT(DISTINCT user_id) AS active_users,
         COUNT(DISTINCT CASE WHEN behavior_code=2 THEN user_id END) AS buyer_users,
         SUM(CASE WHEN behavior_code=1 THEN 1 ELSE 0 END) AS pv_actions,
         SUM(CASE WHEN behavior_code=2 THEN 1 ELSE 0 END) AS buy_actions
  FROM fact_user_behavior
  WHERE event_ts BETWEEN 1511539200 AND 1512316799
  GROUP BY event_date
)
SELECT d.*, COUNT(f.user_id) AS first_seen_users
FROM daily d
LEFT JOIN first_seen f ON f.first_date = d.event_date
GROUP BY d.event_date, d.active_users, d.buyer_users, d.pv_actions, d.buy_actions
ORDER BY d.event_date;

-- name: hourly_metrics
SET SESSION time_zone = '+00:00';
SELECT
  HOUR(DATE_ADD(FROM_UNIXTIME(event_ts), INTERVAL 8 HOUR)) AS event_hour,
  COUNT(DISTINCT user_id) AS active_users,
  COUNT(DISTINCT CASE WHEN behavior_code=2 THEN user_id END) AS buyer_users,
  SUM(CASE WHEN behavior_code=1 THEN 1 ELSE 0 END) AS pv_actions,
  SUM(CASE WHEN behavior_code=2 THEN 1 ELSE 0 END) AS buy_actions
FROM fact_user_behavior
WHERE event_ts BETWEEN 1511539200 AND 1512316799
GROUP BY event_hour
ORDER BY event_hour;

-- name: repurchase_window
WITH buyer AS (
  SELECT user_id,
         SUM(CASE WHEN behavior_code=2 THEN 1 ELSE 0 END) AS buy_actions
  FROM fact_user_behavior
  WHERE event_ts BETWEEN 1511539200 AND 1512316799
  GROUP BY user_id
  HAVING SUM(CASE WHEN behavior_code=2 THEN 1 ELSE 0 END) > 0
)
SELECT COUNT(*) AS buyers,
       SUM(CASE WHEN buy_actions>=2 THEN 1 ELSE 0 END) AS repeat_buyers,
       SUM(CASE WHEN buy_actions=1 THEN 1 ELSE 0 END) AS one_time_buyers,
       AVG(buy_actions) AS avg_buy_actions_per_buyer
FROM buyer;

-- name: weekend_weekday_user_day
SET SESSION time_zone = '+00:00';
WITH user_day AS (
  SELECT
    DATE(DATE_ADD(FROM_UNIXTIME(event_ts), INTERVAL 8 HOUR)) AS event_date,
    user_id,
    MAX(CASE WHEN DAYOFWEEK(DATE_ADD(FROM_UNIXTIME(event_ts), INTERVAL 8 HOUR)) IN (1,7) THEN 1 ELSE 0 END) AS is_weekend,
    MAX(CASE WHEN behavior_code=2 THEN 1 ELSE 0 END) AS buyer
  FROM fact_user_behavior
  WHERE event_ts BETWEEN 1511539200 AND 1512316799
  GROUP BY event_date, user_id
)
SELECT
  CASE WHEN is_weekend=1 THEN '周末' ELSE '工作日' END AS segment,
  COUNT(*) AS user_days,
  SUM(buyer) AS buyer_user_days,
  AVG(buyer) AS buyer_rate
FROM user_day
GROUP BY is_weekend;

-- name: rfm_window
-- 这里用 NTILE 展示 MySQL 8 窗口函数能力，作为 Python 分层的对照；
-- 正式简历数字仍以固定 qcut 口径的分析脚本为准，避免两种切分混用。
WITH buyer_features AS (
  SELECT user_id,
         8 - FLOOR((MAX(event_ts)-1511539200)/86400) AS recency_days,
         SUM(CASE WHEN behavior_code=2 THEN 1 ELSE 0 END) AS buy_actions,
         SUM(CASE WHEN behavior_code IN (3,4) THEN 1 ELSE 0 END) AS engagement_actions
  FROM fact_user_behavior
  WHERE event_ts BETWEEN 1511539200 AND 1512316799
  GROUP BY user_id
  HAVING SUM(CASE WHEN behavior_code=2 THEN 1 ELSE 0 END) > 0
), scored AS (
  SELECT *,
         NTILE(5) OVER (ORDER BY recency_days ASC) AS r_tile,
         NTILE(5) OVER (ORDER BY buy_actions DESC) AS f_tile,
         NTILE(5) OVER (ORDER BY engagement_actions DESC) AS e_tile
  FROM buyer_features
)
SELECT
  CASE
    WHEN f_tile >= 4 AND r_tile >= 4 THEN '高价值复购用户'
    WHEN e_tile >= 4 AND f_tile <= 2 THEN '高互动潜力用户'
    WHEN r_tile <= 2 AND f_tile >= 3 THEN '高价值流失风险'
    WHEN r_tile >= 4 AND f_tile >= 3 THEN '近期购买用户'
    ELSE '一般购买用户'
  END AS segment,
  COUNT(*) AS users,
  SUM(buy_actions) AS buy_actions
FROM scored
GROUP BY segment
ORDER BY buy_actions DESC;

-- name: category_funnel_top20
WITH cu AS (
  SELECT category_id, user_id,
         MAX(CASE WHEN behavior_code=1 THEN 1 ELSE 0 END) AS has_pv,
         MAX(CASE WHEN behavior_code IN (3,4) THEN 1 ELSE 0 END) AS has_intent,
         MAX(CASE WHEN behavior_code=2 THEN 1 ELSE 0 END) AS has_buy
  FROM fact_user_behavior
  WHERE event_ts BETWEEN 1511539200 AND 1512316799
  GROUP BY category_id, user_id
), agg AS (
  SELECT category_id,
         SUM(CASE WHEN has_pv=1 THEN 1 ELSE 0 END) AS pv_users,
         SUM(CASE WHEN has_pv=1 AND has_intent=1 THEN 1 ELSE 0 END) AS intent_users,
         SUM(CASE WHEN has_pv=1 AND has_intent=1 AND has_buy=1 THEN 1 ELSE 0 END) AS buyer_users
  FROM cu GROUP BY category_id
)
SELECT *, buyer_users / NULLIF(intent_users,0) AS intent_to_buy
FROM agg
WHERE pv_users >= 200
ORDER BY pv_users DESC
LIMIT 20;
