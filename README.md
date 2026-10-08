# 淘宝用户行为全链路经营分析

学生个人项目：用阿里公开的淘宝 UserBehavior 数据，完整走一遍“数据质量检查→清洗→MySQL 取数→Python 统计检验→可视化→业务建议”。
数据源：阿里天池 UserBehavior，100,150,807 条原始行为。清洗后 100,095,182 条，987,991 个用户；时间窗 2017-11-25 至 2017-12-03。
主要结论：严格漏斗浏览 984,105 → 收藏/加购 855,498 → 购买 600,278；最大流失在收藏/加购→购买，环节转化 70.17%。
分层结论：高价值复购用户 156,022 人，占购买用户 23.20%，贡献 41.73% 的购买行为。
时段结论：周末购买用户率 18.35%，工作日 19.93%；晚间 14.22%，白天 13.90%。均为观察性对比，p 值显著但 Cohen's h 接近 0。
注意：数据没有价格，不能算 GMV；购买是行为事件而不是订单，复购/留存也只看 9 天窗口。
交付：`powerbi/TaobaoDashboard.pbix` 是可打开看板；`powerbi/TaobaoDashboard.pbip` 是源码项目；`powerbi/screenshots/` 是 Desktop Bridge 实际渲染的 4 页截图；`reports/` 是业务报告和面试讲稿。
复现：运行 `scripts/00_download_data.ps1`，再运行 `scripts/02_prepare_analysis_data.py`、`scripts/04_analyze_business.py`；MySQL 设置 `MYSQL_PWD` 后运行 `scripts/03_import_mysql.ps1` 和 `scripts/05_run_mysql_queries.py`。
原始数据、DuckDB 临时库和 5 GB TSV 已被 `.gitignore` 排除。代码保留真实修正痕迹：时间窗一开始切错、品类转化率出现过大于 100%、大表先建索引会拖慢导入。
