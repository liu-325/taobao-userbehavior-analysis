# 淘宝用户行为全链路经营分析

学生个人项目：用阿里公开的淘宝 UserBehavior 数据，完成“质量检查→清洗→MySQL取数→留存/漏斗/异动归因→Power BI→业务建议”。
数据源：100,150,807 条原始行为；清洗后 100,095,182 条、987,991 用户，时间窗 2017-11-25 至 12-03。
漏斗：用户级整体购买转化 68.06%；PV→购买 68.33%；集合交集归因漏斗 984,105→855,498→600,278（61.00%）；有向路径漏斗整体 53.94%。
分层：高价值复购用户 156,022 人，占购买用户 23.20%，贡献 41.73% 购买行为。
留存：购买留存 D1/D3/D7=14.94%/14.65%/17.60%；高价值复购用户 D7=36.58%。
异动：12/1 购买行为环比下降 5.17%；历史已出现用户贡献净下降 70.6%，18-23 时段贡献 43.7%。
实验：基线70.17%、绝对MDE+1pp、α=0.05、power=0.8，每组32,538人；相对+5%场景2,574/组。
注意：数据没有价格和订单金额，不计算 GMV；购买是行为事件而不是订单，留存只代表9天观察窗口。
交付：`powerbi/TaobaoDashboard.pbix`、`powerbi/TaobaoDashboard.pbip`、`powerbi/screenshots/`、`reports/`。
复现：运行 `scripts/00_download_data.ps1`，再运行 `scripts/02_prepare_analysis_data.py`、`scripts/04_analyze_business.py`、`scripts/10_advanced_business_analysis.py`；MySQL 设置 `MYSQL_PWD` 后运行 `scripts/03_import_mysql.ps1` 和 `scripts/05_run_mysql_queries.py`。
