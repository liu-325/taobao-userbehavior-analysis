# 最终交付清单

## 数据与分析
- `scripts/00_download_data.ps1`：公开数据下载与哈希记录
- `scripts/01_profile_data.py`：原始数据质量检查
- `scripts/02_prepare_analysis_data.py`：DuckDB 全量清洗与派生字段
- `scripts/04_analyze_business.py`：漏斗、用户分层、复购、留存、统计检验和建议量化
- `scripts/10_advanced_business_analysis.py`：双口径漏斗、cohort 留存、异动归因、A/B 样本量
- `sql/01_create_schema.sql`：MySQL 建库建表
- `sql/02_add_indexes.sql`：实际时间索引设计
- `sql/02b_optional_indexes_if_capacity.sql`：磁盘充足时的用户/品类组合索引
- `sql/03_core_queries.sql`：MySQL 8 CTE、JOIN、窗口函数和复杂口径
- `outputs/profile/`：数据质量与清洗汇总
- `outputs/tables/`：完整分析结果表
- `outputs/mysql/`：MySQL 实跑结果、耗时和 Python/MySQL 对账

## 报告与看板
- `reports/淘宝用户行为全链路经营分析报告.pdf`：8 页业务报告，已渲染检查
- `reports/淘宝用户行为全链路经营分析报告.md`：可编辑报告源
- `reports/面试讲稿_淘宝用户行为项目.md`：3 分钟讲法和追问清单
- `powerbi/TaobaoDashboard.pbix`：5 页 Power BI，已打开验证
- `powerbi/TaobaoDashboard.pbip`：Power BI 项目源码
- `powerbi/screenshots/`：5 页 Desktop Bridge 实际渲染截图

## 简历与岗位
- `简历调试/胡成红-数据分析师-湘潭大学-2027届.pdf`：更新后的同文件名简历
- `简历调试/胡成红-数据分析师-湘潭大学-2027届-v9.pdf`：独立 v9 版本
- `简历调试/岗位地图-2027数据分析-20261008.xlsx`：可投+保底岗位地图
- `简历调试/岗位地图-2027数据分析-20261008.md`：快速阅读版

## 关键真实数字
- 原始 100,150,807 行；异常时间窗 55,576 行；完全重复 49 行；清洗后 100,095,182 行。
- 用户级整体购买转化 68.06%；PV→购买 68.33%。
- 集合交集归因漏斗：984,105 → 855,498 → 600,278；整体 61.00%。
- 有向路径漏斗：984,105 → 850,377 → 530,839；整体 53.94%。
- 购买留存 D1/D3/D7=14.94%/14.65%/17.60%；高价值复购用户 D7=36.58%。
- 12/1 购买行为环比下降 5.17%；历史已出现用户贡献净下降 70.6%，18-23 时段贡献 43.7%。
- A/B：+1pp 绝对 MDE 每组 32,538；相对 +5% 每组 2,574；α=0.05、power=0.8、1:1。
