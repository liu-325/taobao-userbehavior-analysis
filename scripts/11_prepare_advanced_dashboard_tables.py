from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / 'outputs' / 'tables'
P = ROOT / 'outputs' / 'powerbi'

def save(df, name):
    df.to_csv(T/name, index=False, encoding='utf-8-sig')
    df.to_csv(P/name, index=False, encoding='utf-8-sig')
    print(name, df.shape)

ret = pd.read_csv(T/'17_retention_summary.csv')
# 长表转宽表，Power BI 里一个 segment 一行，避免把不同人群的行相加。
wide = ret.pivot_table(index='segment', columns='day_n', values=['any_retention','purchase_retention','eligible_users','any_users','purchase_users'], aggfunc='first').reset_index()
wide.columns = ['_'.join([str(x) for x in c if str(x)]) if isinstance(c, tuple) else c for c in wide.columns]
wide = wide.rename(columns={'segment':'用户群','any_retention_1':'任意留存_D1','any_retention_3':'任意留存_D3','any_retention_7':'任意留存_D7','purchase_retention_1':'购买留存_D1','purchase_retention_3':'购买留存_D3','purchase_retention_7':'购买留存_D7'})
save(wide, '23_retention_wide_dashboard.csv')

dim = pd.read_csv(T/'20_anomaly_dimension_summary.csv')
use = dim[dim['dimension'].isin(['user_structure','hour_bucket'])].copy()
use = use.sort_values(['dimension','delta'])
use = use.rename(columns={'dimension':'维度','value':'分组','prev_1130':'11月30日','curr_1201':'12月1日','delta':'差值'})
save(use, '24_anomaly_user_time_dashboard.csv')
topneg = pd.read_csv(T/'19_anomaly_combined_contributions.csv')
topneg = topneg[topneg.delta < 0].sort_values('delta').head(15).copy()
topneg['dimension_label'] = topneg.apply(lambda r: f"类目{r.category_id}｜{r.hour_bucket}｜{r.user_structure}", axis=1)
save(topneg, '25_anomaly_top_negative_dashboard.csv')
# 给适合单表过滤的版本加上简短标签。
topneg[['dimension_label','prev_1130','curr_1201','delta','negative_share','net_delta_share']].to_csv(P/'25_anomaly_top_negative_dashboard.csv', index=False, encoding='utf-8-sig')
print('advanced dashboard tables done')
