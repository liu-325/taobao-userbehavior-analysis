from pathlib import Path
import json, time
import duckdb

RAW = Path(r"D:\datasets\UserBehavior\UserBehavior.csv")
OUT_DIR = Path(r"D:\datasets\UserBehavior\prepared")
OUT_DIR.mkdir(parents=True, exist_ok=True)
ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "outputs" / "profile" / "prepare_summary.json"
SUMMARY.parent.mkdir(parents=True, exist_ok=True)

con = duckdb.connect(str(OUT_DIR / "prepare.duckdb"))
con.execute("PRAGMA threads=8")
con.execute("SET memory_limit='12GB'")
con.execute("PRAGMA temp_directory='D:/datasets/UserBehavior/duckdb_tmp'")
# 先读成 view；真正的清洗结果下面才落表，原始文件不动。
con.execute(f"""
CREATE OR REPLACE VIEW raw AS
SELECT * FROM read_csv_auto(
  '{RAW.as_posix()}', header=false,
  names=['user_id','item_id','category_id','behavior_type','event_ts'],
  types={{'user_id':'BIGINT','item_id':'BIGINT','category_id':'BIGINT','behavior_type':'VARCHAR','event_ts':'BIGINT'}},
  sample_size=2000000
)
""")

start = time.time()
# 原先只看 2017-11-25 0 点到 12 月 3 日，后来发现最早的有效记录在凌晨 1 点，
# 直接砍会误伤正常数据；改成按中国时区转成业务日期再过滤。
con.execute("""
CREATE OR REPLACE TABLE clean_events AS
WITH src AS (
  SELECT
    user_id::INTEGER AS user_id,
    item_id::INTEGER AS item_id,
    category_id::INTEGER AS category_id,
    CASE behavior_type
      WHEN 'pv' THEN 1 WHEN 'buy' THEN 2 WHEN 'cart' THEN 3 WHEN 'fav' THEN 4
    END::UTINYINT AS behavior_code,
    behavior_type,
    event_ts::INTEGER AS event_ts,
    CAST(timezone('Asia/Shanghai', to_timestamp(event_ts)) AS DATE) AS event_date,
    CAST(date_part('hour', timezone('Asia/Shanghai', to_timestamp(event_ts))) AS UTINYINT) AS event_hour,
    CAST(date_part('dow', timezone('Asia/Shanghai', to_timestamp(event_ts))) AS UTINYINT) AS weekday, -- 0=Sunday
    CASE WHEN date_part('dow', timezone('Asia/Shanghai', to_timestamp(event_ts))) IN (0,6) THEN 1 ELSE 0 END::UTINYINT AS is_weekend,
    CAST(date_diff('day', DATE '2017-11-25', CAST(timezone('Asia/Shanghai', to_timestamp(event_ts)) AS DATE)) AS UTINYINT) AS event_day
  FROM raw
  WHERE CAST(timezone('Asia/Shanghai', to_timestamp(event_ts)) AS DATE) BETWEEN DATE '2017-11-25' AND DATE '2017-12-03'
    AND behavior_type IN ('pv','buy','cart','fav')
)
SELECT DISTINCT
  user_id, item_id, category_id, behavior_code, behavior_type, event_ts,
  event_date, event_hour, weekday, is_weekend, event_day
FROM src
""")
clean_rows = con.execute("SELECT COUNT(*) FROM clean_events").fetchone()[0]
valid_rows = con.execute("""
SELECT COUNT(*) FROM raw
WHERE CAST(timezone('Asia/Shanghai', to_timestamp(event_ts)) AS DATE) BETWEEN DATE '2017-11-25' AND DATE '2017-12-03'
""").fetchone()[0]
raw_rows = con.execute("SELECT COUNT(*) FROM raw").fetchone()[0]

# 后续 Python 用 parquet，速度比每次重读 CSV 好很多；MySQL 用无表头的 TSV。
parquet_path = OUT_DIR / "clean_events.parquet"
con.execute(f"COPY clean_events TO '{parquet_path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
tsv_path = OUT_DIR / "clean_events.tsv"
con.execute(f"COPY (SELECT user_id,item_id,category_id,behavior_code,event_ts,event_date,event_hour,weekday,is_weekend,event_day FROM clean_events) TO '{tsv_path.as_posix()}' (FORMAT CSV, HEADER false, DELIMITER '\t')")

summary = {
  "raw_rows": int(raw_rows),
  "invalid_window_rows": int(raw_rows - valid_rows),
  "valid_rows_before_dedup": int(valid_rows),
  "clean_rows": int(clean_rows),
  "exact_duplicate_rows_removed": int(valid_rows - clean_rows),
  "clean_user_count": int(con.execute("SELECT COUNT(DISTINCT user_id) FROM clean_events").fetchone()[0]),
  "clean_item_count": int(con.execute("SELECT COUNT(DISTINCT item_id) FROM clean_events").fetchone()[0]),
  "clean_category_count": int(con.execute("SELECT COUNT(DISTINCT category_id) FROM clean_events").fetchone()[0]),
  "min_event_ts": int(con.execute("SELECT MIN(event_ts) FROM clean_events").fetchone()[0]),
  "max_event_ts": int(con.execute("SELECT MAX(event_ts) FROM clean_events").fetchone()[0]),
  "min_event_date": str(con.execute("SELECT MIN(event_date) FROM clean_events").fetchone()[0]),
  "max_event_date": str(con.execute("SELECT MAX(event_date) FROM clean_events").fetchone()[0]),
  "elapsed_sec": round(time.time() - start, 1),
  "parquet": str(parquet_path),
  "tsv": str(tsv_path)
}
SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
