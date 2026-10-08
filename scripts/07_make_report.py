from pathlib import Path
import json
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether
from reportlab.pdfgen import canvas as pdfcanvas

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / 'outputs' / 'tables'
F = ROOT / 'outputs' / 'figures'
REPORT = ROOT / 'reports'
REPORT.mkdir(parents=True, exist_ok=True)

kpi = pd.read_csv(T/'01_overall_kpi.csv').iloc[0]
funnel = pd.read_csv(T/'05_funnel_overall.csv')
daily = pd.read_csv(T/'03_daily_metrics.csv')
hourly = pd.read_csv(T/'04_hourly_metrics.csv')
seg = pd.read_csv(T/'07_rfm_segments.csv')
cat = pd.read_csv(T/'06_funnel_by_category.csv')
tests = pd.read_csv(T/'11_statistical_tests.csv')
rep = pd.read_csv(T/'08_repurchase_summary.csv').iloc[0]
quality = json.loads((ROOT/'outputs'/'profile'/'prepare_summary.json').read_text(encoding='utf-8'))
recs = pd.read_csv(T/'14_recommendation_estimates.csv')
transition = pd.read_csv(T/'13_behavior_transition_matrix.csv')
funnel_cmp = pd.read_csv(T/'15_funnel_definition_comparison.csv')
retention = pd.read_csv(T/'17_retention_summary.csv')
anomaly = pd.read_csv(T/'21_anomaly_summary.csv').iloc[0]
anom_dim = pd.read_csv(T/'20_anomaly_dimension_summary.csv')
ab = pd.read_csv(T/'22_ab_sample_size_plan.csv')
daily['event_date'] = pd.to_datetime(daily['event_date']).dt.date

pv = int(funnel.stage_users.iloc[0]); intent=int(funnel.stage_users.iloc[1]); buy=int(funnel.stage_users.iloc[2])
overall_cvr = buy/pv; pv_intent = intent/pv; intent_buy = buy/intent
all_buyers = int(kpi.buyer_users); direct_missing = all_buyers - buy
seg_map = seg.set_index('segment')
high = seg_map.loc['高价值复购用户']; potential = seg_map.loc['高互动潜力用户']
wk = tests.iloc[0]; dn = tests.iloc[1]
top21 = hourly[hourly.event_hour==21].iloc[0]
top10 = hourly[hourly.event_hour==10].iloc[0]
peak_buy = hourly[hourly.event_hour.isin([20,21,22])].buy_actions.sum()
peak_share = peak_buy / kpi.buy_actions
high_cat = cat[cat.pv_users>=100000].sort_values('pv_to_buy',ascending=False).head(3)
low_cat = cat[cat.pv_users>=100000].sort_values('pv_to_buy').head(3)
n_per_group = 32538

summary_text = f"""
本报告基于阿里天池公开的淘宝 UserBehavior 数据集，清洗后保留 {quality['clean_rows']:,} 条用户行为、{int(kpi.active_users):,} 名活跃用户和 {int(kpi.active_items):,} 个商品。数据没有价格、订单金额、订单号、退款和活动标签，因此不计算 GMV，也不把购买行为直接当成订单；所有“购买”均指日志中的 buy 行为。
"""
urow = funnel_cmp.iloc[0]; srow = funnel_cmp.iloc[1]; orow = funnel_cmp.iloc[2]
findings = [
    f"用户级整体购买转化率为 {urow['overall']:.2%}（{int(urow['bottom_users']):,} 购买用户 / {int(urow['top_users']):,} 活跃用户）；PV 用户到购买用户为 {urow['middle_to_bottom']:.2%}。这不是 1%-5% 的 session 转化，而是 9 天窗口内去重用户级口径。",
    f"集合交集归因漏斗为 {int(srow['top_users']):,} → {int(srow['middle_users']):,} → {int(srow['bottom_users']):,}，整体 {srow['overall']:.2%}；有向路径漏斗为 {int(orow['top_users']):,} → {int(orow['middle_users']):,} → {int(orow['bottom_users']):,}，整体 {orow['overall']:.2%}。",
    f"高价值复购用户 {int(high.users):,} 人，占购买用户 {high.user_share:.1%}，贡献 {high.buy_action_share:.1%} 的购买行为；高互动潜力用户 {int(potential.users):,} 人，人均购买 {potential.avg_buy_actions:.2f} 次。",
    f"留存方面，全部用户 D1/D3/D7 任意行为留存为 {retention[(retention.segment=='全部用户')&(retention.day_n==1)].any_retention.iloc[0]:.2%}/{retention[(retention.segment=='全部用户')&(retention.day_n==3)].any_retention.iloc[0]:.2%}/{retention[(retention.segment=='全部用户')&(retention.day_n==7)].any_retention.iloc[0]:.2%}，购买留存为 {retention[(retention.segment=='全部用户')&(retention.day_n==1)].purchase_retention.iloc[0]:.2%}/{retention[(retention.segment=='全部用户')&(retention.day_n==3)].purchase_retention.iloc[0]:.2%}/{retention[(retention.segment=='全部用户')&(retention.day_n==7)].purchase_retention.iloc[0]:.2%}。D7只覆盖11/25-26 cohort，周末流量抬升会放大该值。",
    f"11/30→12/1 购买行为下降 {anomaly.delta_pct:.2%}（{int(anomaly.delta_buy_actions):,} 次）；历史已出现用户贡献净下降的 {abs(anom_dim[(anom_dim.dimension=='user_structure')&(anom_dim.value=='历史已出现用户')].delta.iloc[0])/abs(anomaly.delta_buy_actions):.1%}，18-23 时段贡献 {abs(anom_dim[(anom_dim.dimension=='hour_bucket')&(anom_dim.value=='18-23')].delta.iloc[0])/abs(anomaly.delta_buy_actions):.1%}。"
]
recs_text = [
    "优先治理收藏/加购→购买：对 855,498 名收藏/加购但未购买用户做分层召回。以当前基数为准，环节转化率每提升 1 个百分点，预计多 8,555 名购买用户。",
    "针对高互动潜力用户设计低门槛任务：83,581 名用户人均仅 1.17 次购买，但收藏/加购互动强；若人均多完成 1 次购买，理论增加 83,581 次购买行为，需先用实验验证触达成本。",
    "高峰时段先保承接：20:00–22:00 是购买行为峰值，但 21:00 购买用户率只有 15.32%，低于 10:00 的 16.07%。建议把首页推荐和购物车提醒集中到 20:00–22:00，同时用高转化类目做承接。",
    "复盘高流量低转化类目：类目 1080785 有 226,441 名浏览用户，但浏览→购买仅 1.78%；类目 2355072 有 361,785 名浏览用户，浏览→购买 1.91%。这类类目应优先检查价格、详情页、库存和评价，不要只看流量。",
    "用实验而不是拍板：将购物车/收藏召回作为 A/B 实验，随机分组、固定观察期、按 ITT 分析；除购买转化外同时监控退款率、客单价、投诉率和取消订阅率。"
]
limitations = [
    "数据没有价格和订单金额，无法计算 GMV、AOV、LTV 或金额型 RFM；本项目用购买行为次数和购买用户数替代。",
    "时间窗口只有 9 天，留存、复购和用户价值都只能描述这个观测窗口；首日用户缺少 11 月 25 日之前的行为，存在左截断。",
    "严格漏斗是用户集合包含关系，不是严格行为序列；有 72,126 名购买用户没有收藏/加购行为，因此漏斗会低估购买用户总数。",
    "周末/工作日、白天/晚间是观察性准实验，用户会跨组重复出现；p 值很小主要来自样本量极大，Cohen's h 分别是 {wk.cohens_h:.3f} 和 {dn.cohens_h:.3f}，业务效应较小。",
    "类目只有匿名 ID，没有中文类目名；报告只能指出相对表现，不能直接给类目下业务命名。",
]

ret_any = retention.pivot_table(index='segment',columns='day_n',values='any_retention',aggfunc='first').reset_index()
ret_buy = retention.pivot_table(index='segment',columns='day_n',values='purchase_retention',aggfunc='first').reset_index()
anom_user = anom_dim[anom_dim.dimension=='user_structure'][['value','prev_1130','curr_1201','delta','share_of_net_delta']]
anom_hour = anom_dim[anom_dim.dimension=='hour_bucket'][['value','prev_1130','curr_1201','delta','share_of_net_delta']]
ab1 = ab.iloc[0]

md = []
md.append('# 淘宝用户行为全链路经营分析报告')
md.append('## 0. 结论先行')
md.append(summary_text.strip())
for x in findings: md.append(f'- {x}')
md.append('## 1. 数据与口径')
md.append(f"- 原始行数：{quality['raw_rows']:,}；异常时间窗：{quality['invalid_window_rows']:,}；完全重复：{quality['exact_duplicate_rows_removed']:,}；清洗后：{quality['clean_rows']:,}。")
md.append(f"- 时间范围：{quality['min_event_date']} 至 {quality['max_event_date']}，按 Asia/Shanghai 统一成业务日期。")
md.append('- 行为字段：pv/浏览、cart/加购、fav/收藏、buy/购买。购买是行为事件，不是订单，数据无金额。')
md.append('- 严格漏斗定义：下一层用户必须同时具备上一层行为，保证转化率是包含关系。')
md.append('## 2. 转化漏斗')
md.append(pd.DataFrame({'阶段':funnel.stage,'用户数':funnel.stage_users,'阶段转化率':funnel.stage_to_next,'相对首层':funnel.stage_from_first}).to_markdown(index=False))
md.append(f"该表是集合交集归因漏斗，不是 session 转化率；整体 {overall_cvr:.2%}。用户级整体购买转化另有 {urow['overall']:.2%}，有向路径漏斗整体 {orow['overall']:.2%}。三种口径的分子分母定义不同，不能直接互相否定。")
md.append('![转化漏斗](outputs/figures/看板02_转化漏斗.png)')
md.append('## 3. 用户价值分层')
md.append(seg.to_markdown(index=False))
md.append(f"高价值复购用户占全部活跃用户 {int(high.users)/int(kpi.active_users):.2%}，但贡献 {high.buy_action_share:.1%} 的购买行为。高互动潜力用户 {int(potential.users):,} 人，平均购买 {potential.avg_buy_actions:.2f} 次，但收藏/加购互动明显；他们适合先做低门槛召回，再用购买频次判断是否升级为高价值复购用户。")
md.append('![用户分层](outputs/figures/看板03_用户分层.png)')
md.append('## 4. 时段与周末对比')
md.append(f"- 周末用户-日购买率：{wk.rate_a:.2%}；工作日：{wk.rate_b:.2%}；差异 {wk.rate_difference_pp:+.2f} 个百分点，95% CI [{wk.ci95_low_pp:.2f}, {wk.ci95_high_pp:.2f}] 个百分点，p<0.001。")
md.append(f"- 晚间用户-小时购买率：{dn.rate_a:.2%}；白天：{dn.rate_b:.2%}；差异 {dn.rate_difference_pp:+.2f} 个百分点，95% CI [{dn.ci95_low_pp:.2f}, {dn.ci95_high_pp:.2f}] 个百分点，p<0.001。")
md.append(f"- 21:00 购买行为最多：{int(top21.buy_actions):,} 次；10:00 购买用户率最高：{top10.buyer_rate:.2%}。")
md.append('![品类时段](outputs/figures/看板04_品类时段.png)')
md.append('## 5. 类目拆解')
md.append('高流量、相对高转化类目：')
md.append(high_cat[['category_id','pv_users','intent_users','buyer_users','pv_to_buy','intent_to_buy']].to_markdown(index=False))
md.append('高流量、低转化类目：')
md.append(low_cat[['category_id','pv_users','intent_users','buyer_users','pv_to_buy','intent_to_buy']].to_markdown(index=False))
md.append('类目 ID 已匿名化，报告只用于排序和排查，不能直接推断商品属性。高流量低转化类目优先查价格、详情页、库存、评价和优惠；高转化类目则优先承接高峰流量。')
md.append('## 6. 业务建议与量化估算')
for x in recs_text: md.append(f'- {x}')
md.append('## 7. A/B 实验设计')
md.append(f"以收藏/加购→购买环节为例，若目标把购买率从 {intent_buy:.2%} 提升到 {intent_buy+0.01:.2%}，在 α=0.05、power=0.8、双侧检验、1:1 随机分组下，每组约需 {n_per_group:,} 名用户，总计约 {n_per_group*2:,} 名。真实实验应使用平台内部实验平台随机分组，而不是按用户 ID 尾号或自然日期分组。")
md.append('实验主指标：收藏/加购后 14 天购买转化率。护栏指标：GMV/客单价、退款率、退货率、投诉率、取消订阅率、客服工单率。分析方式：按意向治疗（ITT）比较，预先固定观察期，不做多次偷看；若用户级指标方差很大，可用 CUPED 或回归调整协变量。')
md.append('## 8. 留存分析')
md.append(ret_any.to_markdown(index=False))
md.append('购买留存：')
md.append(ret_buy.to_markdown(index=False))
md.append('D7只覆盖首发日为11月25-26日的cohort；任意行为D7被12月2-3日周末流量抬升，不能当成稳定的长期留存。')
md.append('建议：D1/D3购买留存低于15%，新用户首日后的前3天是主要流失窗；高价值复购用户D7购买留存36.58%，应优先用复购提醒和会员权益维持。')
md.append('![留存分析](outputs/figures/看板05_留存分析.png)')
md.append('## 9. 异动归因：11/30→12/1')
md.append(f"购买行为由 {int(anomaly.prev_buy_actions):,} 降到 {int(anomaly.curr_buy_actions):,}，净减少 {abs(int(anomaly.delta_buy_actions)):,} 次（{anomaly.delta_pct:.2%}）。负向贡献池 {int(anomaly.negative_pool):,}，正向贡献池 {int(anomaly.positive_pool):,}。")
md.append('用户结构：')
md.append(anom_user.to_markdown(index=False))
md.append('时段：')
md.append(anom_hour.to_markdown(index=False))
md.append('![异动归因](outputs/figures/看板06_异动归因.png)')
md.append('根因判断：主要波动来自历史用户的晚间/下午购买减少，叠加当日首次出现用户大幅减少；类目贡献分散，没有单一类目能解释全部下降。建议检查12/1晚间和下午的流量承接、活动节奏和唤醒触达，同时不要让用户结构变化被日均结果掩盖。')
md.append('## 10. A/B 样本量口径')
md.append(ab.to_markdown(index=False))
md.append(f"32,538 对应的是 {ab1.baseline_rate:.2%} 基线下的绝对 +1.00 个百分点（相对提升 {ab1.mde_relative:.2%}），α=0.05、power=0.8、双侧、1:1。若业务只要求相对+5%，每组只需 {int(ab.iloc[1].n_per_group):,} 人，不能把两个MDE混用。")
md.append('![AB样本量](outputs/figures/看板07_AB样本量.png)')
md.append('## 11. 局限与不能下的结论')
for x in limitations: md.append(f'- {x}')
md.append('## 9. 复现与交付')
md.append('- 全量清洗：`scripts/02_prepare_analysis_data.py`；全量分析：`scripts/04_analyze_business.py`；MySQL 导入与查询：`sql/` 与 `scripts/03_import_mysql.ps1`、`scripts/05_run_mysql_queries.py`。')
md.append('- MySQL 与 DuckDB 对账：整体 KPI、行为结构、漏斗、日/小时、复购、周末/工作日和品类 Top20 共 237 项检查全部匹配。')
md.append('- Power BI 交付：`powerbi/TaobaoDashboard.pbix`（可打开文件）、`powerbi/TaobaoDashboard.pbip`（源码项目）和 4 张 Desktop 实际渲染截图。')
md.append('- 原始 1 亿行文件不提交 GitHub；仓库只保留下载说明、SQL、脚本、汇总表和看板截图。')
(REPORT/'淘宝用户行为全链路经营分析报告.md').write_text('\n\n'.join(md), encoding='utf-8-sig')

# PDF：不用 Markdown 直接转，手工控制 A4 行距和表格，避免中文字体乱码。
pdfmetrics.registerFont(TTFont('MSYH', r'C:\Windows\Fonts\msyh.ttc'))
pdfmetrics.registerFont(TTFont('MSYH-Bold', r'C:\Windows\Fonts\msyhbd.ttc'))
styles = getSampleStyleSheet()
body = ParagraphStyle('bodycn', parent=styles['BodyText'], fontName='MSYH', fontSize=9.2, leading=14.5, textColor=colors.HexColor('#20252b'), spaceAfter=5)
h1 = ParagraphStyle('h1cn', parent=styles['Heading1'], fontName='MSYH-Bold', fontSize=19, leading=25, textColor=colors.HexColor('#17324d'), spaceAfter=10)
h2 = ParagraphStyle('h2cn', parent=styles['Heading2'], fontName='MSYH-Bold', fontSize=13, leading=18, textColor=colors.HexColor('#17324d'), spaceBefore=8, spaceAfter=6)
small = ParagraphStyle('smallcn', parent=body, fontSize=8, leading=11, textColor=colors.HexColor('#687381'))

class FooterCanvas(pdfcanvas.Canvas):
    def showPage(self):
        self._draw_footer(); super().showPage()
    def save(self):
        # 不要再手动补 footer；build 结束前最后一页的 showPage 已经画过，
        # 之前多画一次会冒出一张只带页脚的空白页。
        super().save()
    def _draw_footer(self):
        self.saveState(); self.setFont('MSYH',8); self.setFillColor(colors.HexColor('#7b8794'))
        self.drawString(18*mm, 9*mm, '胡成红｜淘宝用户行为全链路经营分析｜数据均为公开数据真实运行结果')
        self.drawRightString(A4[0]-18*mm, 9*mm, f'第 {self.getPageNumber()} 页')
        self.restoreState()

doc = SimpleDocTemplate(str(REPORT/'淘宝用户行为全链路经营分析报告.pdf'), pagesize=A4, leftMargin=17*mm, rightMargin=17*mm, topMargin=16*mm, bottomMargin=18*mm, title='淘宝用户行为全链路经营分析报告', author='胡成红')
story=[]
story.append(Paragraph('淘宝用户行为全链路经营分析报告',h1))
story.append(Paragraph('数据规模 100,095,182 条｜分析周期 2017-11-25 至 2017-12-03｜业务型数据分析项目',small))
story.append(Spacer(1,4*mm))
story.append(Paragraph('结论先行',h2))
story.append(Paragraph(summary_text.strip(),body))
for x in findings: story.append(Paragraph('• '+x,body))
story.append(Paragraph('1. 数据清洗与口径',h2))
for x in [f"原始行数 {quality['raw_rows']:,}，异常时间窗 {quality['invalid_window_rows']:,}，完全重复 {quality['exact_duplicate_rows_removed']:,}，清洗后 {quality['clean_rows']:,}。", '按 Asia/Shanghai 统一成业务日期；购买是行为事件，不是订单，无金额字段。']:
    story.append(Paragraph('• '+x,body))
story.append(Image(str(F/'看板01_经营总览.png'), width=176*mm, height=176*mm*9/16))
story.append(PageBreak())
story.append(Paragraph('2. 转化漏斗',h2))
story.append(Paragraph(f"集合交集归因漏斗：浏览 {pv:,} → 收藏/加购 {intent:,} → 购买 {buy:,}，整体 {overall_cvr:.2%}；用户级整体购买转化 {urow['overall']:.2%}；有向路径漏斗整体 {orow['overall']:.2%}。",body))
story.append(Image(str(F/'看板02_转化漏斗.png'), width=176*mm, height=176*mm*9/16))
story.append(PageBreak())
story.append(Paragraph('3. 用户价值分层',h2))
seg_rows=[['分层','用户数','用户占比','购买行为占比','人均购买次数']]+[[str(r.segment),f'{int(r.users):,}',f'{r.user_share:.2%}',f'{r.buy_action_share:.2%}',f'{r.avg_buy_actions:.2f}'] for _,r in seg.iterrows()]
tab=Table(seg_rows,colWidths=[45*mm,28*mm,28*mm,35*mm,30*mm],repeatRows=1)
tab.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),'MSYH'),('FONTNAME',(0,0),(-1,0),'MSYH-Bold'),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#17324d')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),.3,colors.HexColor('#c9d3df')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(1,1),(-1,-1),'CENTER'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f4f7fb')])]))
story.append(tab); story.append(Spacer(1,4*mm))
story.append(Image(str(F/'看板03_用户分层.png'), width=176*mm, height=176*mm*9/16))
story.append(PageBreak())
story.append(Paragraph('4. 时段与周末准实验',h2))
story.append(Paragraph(f"周末购买用户率 {wk.rate_a:.2%}，工作日 {wk.rate_b:.2%}，差异 {wk.rate_difference_pp:+.2f} 个百分点，95% CI [{wk.ci95_low_pp:.2f}, {wk.ci95_high_pp:.2f}]，p<0.001，Cohen's h={wk.cohens_h:.3f}。",body))
story.append(Paragraph(f"晚间购买用户率 {dn.rate_a:.2%}，白天 {dn.rate_b:.2%}，差异 {dn.rate_difference_pp:+.2f} 个百分点，95% CI [{dn.ci95_low_pp:.2f}, {dn.ci95_high_pp:.2f}]，p<0.001，Cohen's h={dn.cohens_h:.3f}。",body))
story.append(Paragraph('两组的 p 值很小，但 Cohen\'s h 接近 0；数据可以支持“时段存在差异”，不能支持“改时段就能提升转化”的因果结论。',body))
story.append(Image(str(F/'看板04_品类时段.png'), width=176*mm, height=176*mm*9/16))
story.append(PageBreak())
story.append(Paragraph('5. 类目与建议',h2))
story.append(Paragraph('高流量低转化类目示例：',body))
for _,r in low_cat.iterrows(): story.append(Paragraph(f"• 类目 {int(r.category_id)}：浏览用户 {int(r.pv_users):,}，浏览→购买 {r.pv_to_buy:.2%}，意图→购买 {r.intent_to_buy:.2%}。",body))
story.append(Paragraph('高流量高转化类目示例：',body))
for _,r in high_cat.iterrows(): story.append(Paragraph(f"• 类目 {int(r.category_id)}：浏览用户 {int(r.pv_users):,}，浏览→购买 {r.pv_to_buy:.2%}，意图→购买 {r.intent_to_buy:.2%}。",body))
story.append(Paragraph('建议',h2))
for x in recs_text: story.append(Paragraph('• '+x,body))
story.append(PageBreak())
story.append(Paragraph('6. A/B 实验与局限',h2))
story.append(Paragraph(f"若把收藏/加购→购买从 {intent_buy:.2%} 提升到 {intent_buy+0.01:.2%}，α=0.05、power=0.8、1:1 分组，每组约需 {n_per_group:,} 人，总计 {n_per_group*2:,} 人。",body))
story.append(Paragraph('实验必须随机分组，主指标为 14 天购买转化，护栏指标包括退款率、客单价、投诉率和取消订阅率；分析用 ITT，不偷看。',body))
for x in limitations: story.append(Paragraph('• '+x,body))
story.append(PageBreak())
story.append(Paragraph('7. 留存分析',h2))
story.append(Paragraph(f"全部用户 D1/D3/D7 任意行为留存：{ret_any.loc[ret_any.segment=='全部用户',[1,3,7]].iloc[0].tolist()[0]:.2%}/{ret_any.loc[ret_any.segment=='全部用户',[1,3,7]].iloc[0].tolist()[1]:.2%}/{ret_any.loc[ret_any.segment=='全部用户',[1,3,7]].iloc[0].tolist()[2]:.2%}；购买留存：{ret_buy.loc[ret_buy.segment=='全部用户',[1,3,7]].iloc[0].tolist()[0]:.2%}/{ret_buy.loc[ret_buy.segment=='全部用户',[1,3,7]].iloc[0].tolist()[1]:.2%}/{ret_buy.loc[ret_buy.segment=='全部用户',[1,3,7]].iloc[0].tolist()[2]:.2%}。D7只覆盖最早两个cohort。",body))
story.append(Image(str(F/'看板05_留存分析.png'), width=176*mm, height=176*mm*8/15))
story.append(Paragraph('建议：D1/D3购买留存低于15%，首日后前3天是主要流失窗；高价值复购用户D7购买留存36.58%，优先做复购提醒和会员权益。',body))
story.append(Paragraph('8. 异动归因：11/30→12/1',h2))
story.append(Paragraph(f"购买行为净减少 {abs(int(anomaly.delta_buy_actions)):,} 次（{anomaly.delta_pct:.2%}）；负向贡献池 {int(anomaly.negative_pool):,}，正向贡献池 {int(anomaly.positive_pool):,}。归因结果按负向贡献池解释，不能把正负贡献简单相加当成单一口径。",body))
story.append(Image(str(F/'看板06_异动归因.png'), width=176*mm, height=176*mm*8/15))
story.append(Paragraph('根因判断：主要波动来自历史用户的晚间/下午购买减少，叠加当日首次出现用户减少；类目贡献分散。建议检查12/1晚间和下午的流量承接、活动节奏和唤醒触达。',body))
story.append(PageBreak())
story.append(Paragraph('9. A/B 样本量与护栏',h2))
story.append(Paragraph(f"基线 {ab1.baseline_rate:.2%}，绝对MDE +1.00pp（相对 {ab1.mde_relative:.2%}），α=0.05、power=0.8、双侧、1:1，每组 {int(ab1.n_per_group):,} 人。相对+5%的场景每组 {int(ab.iloc[1].n_per_group):,} 人；简历保留保守的32,538口径。主指标为收藏/加购→购买，护栏为客均行为量、退款/退货率、投诉率、取消订阅率。",body))
story.append(Image(str(F/'看板07_AB样本量.png'), width=176*mm, height=176*mm*8/15))
story.append(Paragraph('复现入口',h2))
story.append(Paragraph('脚本：02_prepare_analysis_data.py、04_analyze_business.py、05_run_mysql_queries.py；SQL：sql/03_core_queries.sql；Power BI：TaobaoDashboard.pbix/PBIP；MySQL 与 Python 237 项核心口径对账通过；原始 1 亿行文件不提交仓库。',body))
doc.build(story, canvasmaker=FooterCanvas)
print(REPORT/'淘宝用户行为全链路经营分析报告.md')
print(REPORT/'淘宝用户行为全链路经营分析报告.pdf')
