-- 可选：磁盘空间充足时再加用户/品类组合索引。
-- 先说清楚，100m 行每多一个二级索引会多占约 1.5-2GB。
ALTER TABLE fact_user_behavior
  ADD INDEX idx_user_ts_beh (user_id, event_ts, behavior_code),
  ADD INDEX idx_cat_ts_beh (category_id, event_ts, behavior_code);
