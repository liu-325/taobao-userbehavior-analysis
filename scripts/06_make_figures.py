from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import matplotlib.ticker as mtick

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / 'outputs' / 'tables'
P = ROOT / 'outputs' / 'powerbi'
F = ROOT / 'outputs' / 'figures'
P.mkdir(parents=True, exist_ok=True); F.mkdir(parents=True, exist_ok=True)
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.facecolor'] = '#f4f7fb'
plt.rcParams['axes.facecolor'] = '#ffffff'
NAVY='#17324d'; BLUE='#2878b5'; TEAL='#2a9d8f'; ORANGE='#ef8354'; GRAY='#7b8794'; LIGHT='#dce6f1'; PURPLE='#6c5ce7'

# Power BI 用数据单独拷到 outputs/powerbi，避免看板脚本去找原始 100m 日志。
for src in T.glob('*.csv'):
    if src.stat().st_size < 5*1024*1024:
        (P / src.name).write_bytes(src.read_bytes())

kpi = pd.read_csv(T/'01_overall_kpi.csv').iloc[0]
funnel = pd.read_csv(T/'05_funnel_overall.csv')
daily = pd.read_csv(T/'03_daily_metrics.csv', parse_dates=['event_date'])
hourly = pd.read_csv(T/'04_hourly_metrics.csv')
seg = pd.read_csv(T/'07_rfm_segments.csv')
cat = pd.read_csv(T/'06_funnel_by_category.csv')
tests = pd.read_csv(T/'11_statistical_tests.csv')
mix = pd.read_csv(T/'02_behavior_mix.csv')

def save(fig, name):
    fig.savefig(F/name, dpi=200, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close(fig)

def card(ax, title, value, note, color):
    ax.axis('off')
    ax.add_patch(FancyBboxPatch((0.02,0.08),0.96,0.84,boxstyle='round,pad=0.03,rounding_size=0.06',linewidth=0,facecolor='white',transform=ax.transAxes))
    ax.text(.08,.69,title,fontsize=11,color=GRAY,transform=ax.transAxes)
    ax.text(.08,.31,value,fontsize=22,weight='bold',color=color,transform=ax.transAxes)
    ax.text(.08,.12,note,fontsize=8,color=GRAY,transform=ax.transAxes)

# Page 1: 经营总览
fig = plt.figure(figsize=(16,9)); gs = fig.add_gridspec(4,4,hspace=.65,wspace=.45)
fig.suptitle('淘宝用户行为全链路经营看板 · 经营总览', x=.04, y=.97, ha='left', fontsize=22, weight='bold', color=NAVY)
fig.text(.04,.925,'口径：2017-11-25 至 2017-12-03（中国时区）｜清洗后 100,095,182 条行为｜数据无价格字段，不计算 GMV',fontsize=10,color=GRAY)
cards=[('行为总量',f"{int(kpi.behaviors):,}",'清洗后全量',''),('活跃用户',f"{int(kpi.active_users):,}",'去重用户',BLUE),('购买用户',f"{int(kpi.buyer_users):,}",f"占活跃用户 {kpi.buyer_penetration:.1%}",TEAL),('集合交集购买率',f"{funnel.stage_users.iloc[-1]/funnel.stage_users.iloc[0]:.1%}",'浏览→收藏/加购→购买',ORANGE)]
for i,(a,b,c,d) in enumerate(cards):
    ax=fig.add_subplot(gs[0,i]); card(ax,a,b,c,d or NAVY)
ax=fig.add_subplot(gs[1:3,:2]); ax.plot(daily.event_date,daily.active_users,marker='o',lw=2.6,color=BLUE,label='活跃用户'); ax.set_title('逐日活跃用户',loc='left',weight='bold',color=NAVY); ax.yaxis.set_major_formatter(mtick.StrMethodFormatter('{x:,.0f}')); ax.grid(axis='y',alpha=.2); ax.legend(frameon=False)
ax2=ax.twinx(); ax2.plot(daily.event_date,daily.buyer_rate,marker='s',color=ORANGE,lw=2.2,label='购买用户率'); ax2.yaxis.set_major_formatter(mtick.PercentFormatter(1)); ax2.legend(loc='lower right',frameon=False); ax2.set_ylim(.16,.22)
ax=fig.add_subplot(gs[1:3,2:]); bars=ax.bar(mix.behavior_type,mix.actions,color=[BLUE,ORANGE,TEAL,PURPLE]); ax.set_yscale('log'); ax.set_title('行为结构（对数刻度）',loc='left',weight='bold',color=NAVY); ax.grid(axis='y',alpha=.2,which='both'); ax.set_ylabel('行为数')
for b,v in zip(bars,mix.actions): ax.text(b.get_x()+b.get_width()/2,v*1.08,f'{v/1e6:.1f}M',ha='center',fontsize=9,color=GRAY)
ax=fig.add_subplot(gs[3,:]); ax.axis('off'); ax.text(.02,.54,'核心判断',fontsize=12,weight='bold',color=NAVY); ax.text(.02,.18,'周末流量显著抬升，但购买用户率低于工作日；12月2日活跃用户 970,401，购买率 17.98%，说明“来人”不等于“成交”，高峰时段的承接和召回更关键。',fontsize=11,color='#333333')
save(fig,'看板01_经营总览.png')

# Page 2: 漏斗
fig=plt.figure(figsize=(16,9)); fig.suptitle('转化漏斗：最大流失在收藏/加购→购买',x=.04,y=.97,ha='left',fontsize=22,weight='bold',color=NAVY)
fig.text(.04,.925,'严格包含式口径：下一层用户必须同时具备上一层行为；仅表示窗口内集合关系，不是完整行为路径。',fontsize=10,color=GRAY)
ax=fig.add_axes([.06,.15,.52,.7]); vals=funnel.stage_users.values; y=np.arange(len(vals))[::-1]; bars=ax.barh(y,vals,color=[BLUE,TEAL,ORANGE],height=.52)
ax.set_yticks(y); ax.set_yticklabels(funnel.stage); ax.set_xlim(0, vals.max()*1.18); ax.xaxis.set_major_formatter(mtick.StrMethodFormatter('{x:,.0f}')); ax.grid(axis='x',alpha=.2); ax.invert_yaxis()
for i,(bar,v) in enumerate(zip(bars,vals)):
    ax.text(v+vals.max()*.015,bar.get_y()+bar.get_height()/2,f'{v:,}',va='center',fontsize=12,weight='bold',color=NAVY)
    if i>0: ax.text(v*.52,bar.get_y()+bar.get_height()/2,f'{v/vals[i-1]:.1%}',va='center',ha='center',color='white',fontsize=13,weight='bold')
ax=fig.add_axes([.65,.52,.3,.29]); rates=[funnel.stage_to_next.iloc[0],funnel.stage_to_next.iloc[1]]; b=ax.bar(['浏览→意图','意图→购买'],rates,color=[TEAL,ORANGE]); ax.set_ylim(0,1); ax.yaxis.set_major_formatter(mtick.PercentFormatter(1)); ax.set_title('分环节转化率',loc='left',weight='bold',color=NAVY); ax.grid(axis='y',alpha=.2)
for bar,r in zip(b,rates): ax.text(bar.get_x()+bar.get_width()/2,r+.03,f'{r:.1%}',ha='center',fontsize=11,weight='bold',color=NAVY)
ax=fig.add_axes([.65,.14,.3,.28]); top=cat[cat.pv_users>=5000].nlargest(10,'pv_to_buy').sort_values('pv_to_buy'); ax.barh(top.category_id.astype(str),top.pv_to_buy,color=BLUE); ax.set_title('高转化类目（浏览用户≥5000）',loc='left',weight='bold',color=NAVY); ax.xaxis.set_major_formatter(mtick.PercentFormatter(1)); ax.grid(axis='x',alpha=.2); ax.tick_params(axis='y',labelsize=8)
save(fig,'看板02_转化漏斗.png')

# Page 3: 用户分层
fig=plt.figure(figsize=(16,9)); fig.suptitle('用户价值分层：高价值复购用户贡献 41.6% 购买行为',x=.04,y=.97,ha='left',fontsize=22,weight='bold',color=NAVY)
fig.text(.04,.925,'分层基于 R/F+互动强度 E；数据没有金额，不使用 M，也不称 RFM。',fontsize=10,color=GRAY)
ax=fig.add_axes([.07,.17,.54,.68]); seg2=seg.sort_values('buy_action_share'); y=np.arange(len(seg2)); h=.35
ax.barh(y-h/2,seg2.user_share,height=h,color=BLUE,label='用户占比'); ax.barh(y+h/2,seg2.buy_action_share,height=h,color=ORANGE,label='购买行为占比'); ax.set_yticks(y); ax.set_yticklabels(seg2.segment); ax.xaxis.set_major_formatter(mtick.PercentFormatter(1)); ax.legend(frameon=False); ax.grid(axis='x',alpha=.2); ax.set_title('用户份额 vs 购买行为份额',loc='left',weight='bold',color=NAVY)
ax=fig.add_axes([.67,.49,.27,.21]); s=seg.set_index('segment').loc['高价值复购用户']; p=seg.set_index('segment').loc['高互动潜力用户']; b=ax.bar(['高价值复购','高互动潜力'],[s.users,p.users],color=[TEAL,ORANGE]); ax.set_title('用户数',loc='left',weight='bold',color=NAVY); ax.yaxis.set_major_formatter(mtick.StrMethodFormatter('{x:,.0f}')); ax.grid(axis='y',alpha=.2)
for bar,v in zip(b,[s.users,p.users]): ax.text(bar.get_x()+bar.get_width()/2,v*1.02,f'{v:,.0f}',ha='center',fontsize=9,color=NAVY)
ax=fig.add_axes([.67,.18,.27,.21]); b=ax.bar(['高价值复购','高互动潜力'],[s.avg_buy_actions,p.avg_buy_actions],color=[TEAL,ORANGE]); ax.set_title('人均购买行为次数',loc='left',weight='bold',color=NAVY); ax.grid(axis='y',alpha=.2)
for bar,v in zip(b,[s.avg_buy_actions,p.avg_buy_actions]): ax.text(bar.get_x()+bar.get_width()/2,v+.08,f'{v:.2f}',ha='center',fontsize=9,color=NAVY)
ax=fig.add_axes([.07,.02,.87,.1]); ax.axis('off'); ax.text(.0,.55,f"高价值复购用户 {int(s.users):,} 人，占购买用户 {s.user_share:.1%}，贡献 {s.buy_action_share:.1%} 购买行为；高互动潜力用户 {int(p.users):,} 人，人均购买仅 {p.avg_buy_actions:.2f} 次。",fontsize=12,color='#333333')
save(fig,'看板03_用户分层.png')

# Page 4: 品类时段
fig=plt.figure(figsize=(16,9)); fig.suptitle('品类与时段：高峰流量没有同步转化为高购买率',x=.04,y=.97,ha='left',fontsize=22,weight='bold',color=NAVY)
fig.text(.04,.925,'时段对比是观察性分析；用户可跨时段重复出现，不能解释为因果。',fontsize=10,color=GRAY)
ax=fig.add_axes([.07,.54,.55,.35]); ax.plot(hourly.event_hour,hourly.active_users,color=BLUE,lw=2.5,label='活跃用户'); ax.set_xticks(range(0,24,2)); ax.set_ylabel('活跃用户'); ax.yaxis.set_major_formatter(mtick.StrMethodFormatter('{x:,.0f}')); ax.grid(alpha=.2); ax2=ax.twinx(); ax2.plot(hourly.event_hour,hourly.buyer_rate,color=ORANGE,lw=2.2,label='购买用户率'); ax2.yaxis.set_major_formatter(mtick.PercentFormatter(1)); ax.legend(loc='upper left',frameon=False); ax2.legend(loc='upper right',frameon=False); ax.set_title('24小时活跃与转化',loc='left',weight='bold',color=NAVY)
ax=fig.add_axes([.68,.54,.25,.35]); top=cat.nlargest(20,'pv_users'); sizes=top.pv_users/1000; sc=ax.scatter(top.pv_users,top.pv_to_buy,s=sizes,c=top.intent_to_buy,cmap='viridis',alpha=.75); ax.set_xscale('log'); ax.set_xlabel('浏览用户数（log）'); ax.set_ylabel('浏览→购买'); ax.yaxis.set_major_formatter(mtick.PercentFormatter(1)); ax.set_title('类目流量 vs 转化',loc='left',weight='bold',color=NAVY); ax.grid(alpha=.2); fig.colorbar(sc,ax=ax,label='意图→购买',format=mtick.PercentFormatter(1))
ax=fig.add_axes([.07,.12,.36,.28]); t=pd.read_csv(T/'09_weekend_user_day.csv'); bars=ax.bar(t.segment,t.buyer_rate,color=[ORANGE,BLUE]); ax.set_ylim(.17,.205); ax.yaxis.set_major_formatter(mtick.PercentFormatter(1)); ax.set_title('周末 vs 工作日购买用户率',loc='left',weight='bold',color=NAVY); ax.grid(axis='y',alpha=.2)
for bar,r in zip(bars,t.buyer_rate): ax.text(bar.get_x()+bar.get_width()/2,r+.002,f'{r:.2%}',ha='center',color=NAVY,weight='bold')
ax=fig.add_axes([.5,.12,.43,.28]); top=cat.nlargest(10,'buy_actions').sort_values('buy_actions'); ax.barh(top.category_id.astype(str),top.buy_actions,color=TEAL); ax.set_title('购买行为 TOP10 类目',loc='left',weight='bold',color=NAVY); ax.xaxis.set_major_formatter(mtick.StrMethodFormatter('{x:,.0f}')); ax.grid(axis='x',alpha=.2); ax.tick_params(axis='y',labelsize=8)
save(fig,'看板04_品类时段.png')
print('figures done')
