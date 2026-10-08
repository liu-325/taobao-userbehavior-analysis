-- 这台机器的 C 盘空间比较紧，实际只建最常用的时间+行为索引。
-- 查询先按 event_ts 范围缩小，再按 behavior_code 判断 pv/buy/cart/fav。
ALTER TABLE fact_user_behavior
  ADD INDEX idx_ts_beh (event_ts, behavior_code);
