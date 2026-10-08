from pathlib import Path
import os, json, time, sys, re
import pandas as pd
import pymysql
from pymysql.cursors import DictCursor

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / 'sql' / '03_core_queries.sql'
OUT = ROOT / 'outputs' / 'mysql'
OUT.mkdir(parents=True, exist_ok=True)
text = SQL_PATH.read_text(encoding='utf-8')
blocks = {}
current = None
buf = []
for line in text.splitlines():
    if line.startswith('-- name:'):
        if current:
            blocks[current] = '\n'.join(buf).strip().rstrip(';')
        current = line.split(':',1)[1].strip(); buf = []
    else:
        buf.append(line)
if current:
    blocks[current] = '\n'.join(buf).strip().rstrip(';')

conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', password=os.environ['MYSQL_PWD'], database='taobao_userbehavior', charset='utf8mb4', cursorclass=DictCursor, init_command="SET SESSION time_zone='+00:00'")
timings = []
try:
    with conn.cursor() as cur:
        for name, sql in blocks.items():
            # 已经成功的不重复跑，省得每次都在百万级表上重算。
            if (OUT / f'{name}.csv').exists() and '--force' not in sys.argv:
                print(name, 'skip-existing', flush=True)
                continue
            sql = re.sub(r"SET SESSION time_zone\s*=\s*'\+00:00';\s*", '', sql, flags=re.I)
            # 每个查询单独计时，方便解释哪一步真正慢，不把总耗时糊成一团。
            t0 = time.time()
            cur.execute(sql)
            rows = cur.fetchall()
            df = pd.DataFrame(rows)
            df.to_csv(OUT / f'{name}.csv', index=False, encoding='utf-8-sig')
            sec = round(time.time()-t0, 2)
            timings.append({'query': name, 'seconds': sec, 'rows': len(df)})
            print(name, len(df), f'{sec}s', flush=True)
finally:
    conn.close()
(OUT / 'mysql_query_timings.json').write_text(json.dumps(timings, ensure_ascii=False, indent=2), encoding='utf-8')
