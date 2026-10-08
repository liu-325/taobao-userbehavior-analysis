-- 这个库只放淘宝行为日志，避免和旧 test/Olist 数据混在一起。
CREATE DATABASE IF NOT EXISTS taobao_userbehavior
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;
USE taobao_userbehavior;

-- 明细表先不加索引，LOAD DATA 先快速灌进去；否则每插一行都维护索引会很慢。
-- 行为编码：1=pv, 2=buy, 3=cart, 4=fav。
CREATE TABLE IF NOT EXISTS fact_user_behavior (
  user_id INT UNSIGNED NOT NULL,
  item_id INT UNSIGNED NOT NULL,
  category_id INT UNSIGNED NOT NULL,
  behavior_code TINYINT UNSIGNED NOT NULL,
  event_ts INT UNSIGNED NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
