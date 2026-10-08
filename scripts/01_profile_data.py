from pathlib import Path
import json
import duckdb

# 这步就是先“看清数据”，不要一上来就删行。
RAW = Path(r"D:\datasets\UserBehavior\UserBehavior.csv")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "profile"
OUT.mkdir(parents=True, exist_ok=True)

con = duckdb.connect()
con.execute("PRAGMA threads=8")
con.execute("PRAGMA temp_directory='D:/datasets/UserBehavior/duckdb_tmp'")
con.execute(f"CREATE VIEW raw AS SELECT * FROM read_csv_auto('{RAW.as_posix()}', header=false, names=['user_id','item_id','category_id','behavior_type','event_ts'], types={{'user_id':'BIGINT','item_id':'BIGINT','category_id':'BIGINT','behavior_type':'VARCHAR','event_ts':'BIGINT'}}, sample_size=2000000)")

# 用 filter 一次扫出大部分基础统计，避免来回读 3.4GB 文件。
row = con.execute("""
SELECT
  COUNT(*) AS raw_rows,
  COUNT(DISTINCT user_id) AS users,
  COUNT(DISTINCT item_id) AS items,
  COUNT(DISTINCT category_id) AS categories,
  COUNT(DISTINCT behavior_type) AS behavior_types,
  SUM(CASE WHEN user_id IS NULL OR item_id IS NULL OR category_id IS NULL OR behavior_type IS NULL OR event_ts IS NULL THEN 1 ELSE 0 END) AS null_rows,
  SUM(CASE WHEN behavior_type NOT IN ('pv','buy','cart','fav') THEN 1 ELSE 0 END) AS bad_behavior_rows,
  MIN(event_ts) AS min_ts,
  MAX(event_ts) AS max_ts,
  SUM(CASE WHEN behavior_type='pv' THEN 1 ELSE 0 END) AS pv_rows,
  SUM(CASE WHEN behavior_type='buy' THEN 1 ELSE 0 END) AS buy_rows,
  SUM(CASE WHEN behavior_type='cart' THEN 1 ELSE 0 END) AS cart_rows,
  SUM(CASE WHEN behavior_type='fav' THEN 1 ELSE 0 END) AS fav_rows
FROM raw
""").fetchdf().to_dict('records')[0]

# 把时间戳按中国时区转成业务日期，不要直接拿 UTC 日期做日报。
# 一开始我用“区间整数”过滤，结果把 11 月 25 日凌晨的正常记录也误算成异常；
# 这里改成按业务日期过滤，异常值单独计数，报告里能说清楚删了什么。
time_row = con.execute("""
WITH x AS (
  SELECT *, CAST(timezone('Asia/Shanghai', to_timestamp(event_ts)) AS DATE) AS event_date
  FROM raw
)
SELECT
  MIN(event_date) FILTER (WHERE event_date BETWEEN DATE '2017-11-25' AND DATE '2017-12-03') AS min_date,
  MAX(event_date) FILTER (WHERE event_date BETWEEN DATE '2017-11-25' AND DATE '2017-12-03') AS max_date,
  COUNT(*) FILTER (WHERE event_date BETWEEN DATE '2017-11-25' AND DATE '2017-12-03') AS valid_window_rows,
  COUNT(*) - COUNT(*) FILTER (WHERE event_date BETWEEN DATE '2017-11-25' AND DATE '2017-12-03') AS invalid_window_rows,
  COUNT(*) FILTER (WHERE event_ts < 0) AS negative_ts_rows,
  COUNT(*) FILTER (WHERE event_ts >= 0 AND event_ts < 1511539200) AS before_2017_11_25_rows,
  COUNT(*) FILTER (WHERE event_ts > 1512316799) AS after_2017_12_03_rows
FROM x
""").fetchdf().to_dict('records')[0]

data = {**{k: int(v) if hasattr(v, 'item') else v for k, v in row.items()}, **{k: str(v) for k, v in time_row.items()}}
(OUT / "data_quality.json").write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
