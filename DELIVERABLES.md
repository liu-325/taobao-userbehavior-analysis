# 最终交付清单

## 数据与分析
- `scripts/00_download_data.ps1`：公开数据下载与哈希记录
- `scripts/01_profile_data.py`：原始数据质量检查
- `scripts/02_prepare_analysis_data.py`：DuckDB 全量清洗与派生字段
- `scripts/04_analyze_business.py`：漏斗、用户分层、复购、留存、统计检验和建议量化
- `sql/01_create_schema.sql`：MySQL 建库建表
- `sql/02_add_indexes.sql`：时间索引设计
- `sql/03_core_queries.sql`：MySQL 8 CTE、JOIN、窗口函数和复杂口径
- `outputs/profile/`：数据质量与清洗汇总
- `outputs/tables/`：14 张全量分析结果表
- `outputs/mysql/`：MySQL 实跑结果与耗时

## 报告与看板
- `reports/淘宝用户行为全链路经营分析报告.pdf`：6 页业务报告，已渲染检查
- `reports/淘宝用户行为全链路经营分析报告.md`：可编辑报告源
- `reports/面试讲稿_淘宝用户行为项目.md`：3 分钟讲法和追问清单
- `powerbi/TaobaoDashboard.pbix`：已用 Power BI Desktop 打开验证
- `powerbi/TaobaoDashboard.pbip`：Power BI 项目源码
- `powerbi/screenshots/`：4 页 Desktop Bridge 实际渲染截图

## 简历与岗位
- `简历调试/胡成红-数据分析师-湘潭大学-2027届.pdf`：更新后的同文件名简历
- `简历调试/胡成红-数据分析师-湘潭大学-2027届-v8.pdf`：独立 v8 版本
- `简历调试/岗位地图-2027数据分析-20261008.xlsx`：可投+保底岗位地图
- `简历调试/岗位地图-2027数据分析-20261008.md`：快速阅读版

## 关键真实数字
- 原始 100,150,807 行；异常时间窗 55,576 行；完全重复 49 行；清洗后 100,095,182 行。
- 严格漏斗：984,105 → 855,498 → 600,278；整体购买转化 61.00%；意图→购买 70.17%。
- 高价值复购用户 156,022 人，占购买用户 23.20%，贡献 41.73% 购买行为。
- 周末 18.35% vs 工作日 19.93%；晚间 14.22% vs 白天 13.90%（观察性差异，效应量接近 0）。
