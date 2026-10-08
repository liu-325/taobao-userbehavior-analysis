from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

ROOT=Path(__file__).resolve().parents[1]
T=ROOT/'outputs'/'tables'; F=ROOT/'outputs'/'figures'; F.mkdir(parents=True,exist_ok=True)
plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei']; plt.rcParams['axes.unicode_minus']=False
NAVY='#17324d'; BLUE='#2878b5'; TEAL='#2a9d8f'; ORANGE='#ef8354'; GRAY='#7b8794'; PURPLE='#6c5ce7'
ret=pd.read_csv(T/'17_retention_summary.csv'); dim=pd.read_csv(T/'20_anomaly_dimension_summary.csv'); ab=pd.read_csv(T/'22_ab_sample_size_plan.csv'); fun=pd.read_csv(T/'15_funnel_definition_comparison.csv')

def save(fig,name): fig.savefig(F/name,dpi=200,bbox_inches='tight',facecolor=fig.get_facecolor()); plt.close(fig)

# 留存图：任意行为和购买留存分开画，避免单位误解。
fig=plt.figure(figsize=(15,8)); gs=fig.add_gridspec(2,1,hspace=.45); fig.suptitle('Cohort 留存：D1 / D3 / D7',x=.04,y=.97,ha='left',fontsize=22,weight='bold',color=NAVY)
fig.text(.04,.92,'D7只有11月25-26日 cohort 可完整观察；用户在该日之后第N天有行为/购买才算留存。',fontsize=10,color=GRAY)
for row,metric,title in [(0,'any_retention','任意行为留存'),(1,'purchase_retention','购买留存')]:
 ax=fig.add_subplot(gs[row]); sub=ret[ret.segment.isin(['全部用户','窗口内复购用户','高价值复购用户'])]
 for i,seg in enumerate(['全部用户','窗口内复购用户','高价值复购用户']):
  x=sub[sub.segment==seg]; ax.plot(x.day_n,x[metric],marker='o',lw=2.5,label=seg,color=[BLUE,TEAL,ORANGE][i])
  for _,r in x.iterrows(): ax.text(r.day_n,r[metric]+.015,f'{r[metric]:.1%}',ha='center',fontsize=9,color=NAVY)
 ax.set_xticks([1,3,7]); ax.yaxis.set_major_formatter(mtick.PercentFormatter(1)); ax.set_ylim(0,1.08); ax.grid(axis='y',alpha=.2); ax.set_title(title,loc='left',weight='bold',color=NAVY); ax.legend(frameon=False,ncol=3)
save(fig,'看板05_留存分析.png')

# 异动归因图。
fig=plt.figure(figsize=(15,8)); fig.suptitle('11/30 → 12/1 购买行为下降归因',x=.04,y=.97,ha='left',fontsize=22,weight='bold',color=NAVY)
fig.text(.04,.92,'净变化 -11,449 次；负向贡献池 37,614 次，正向贡献池 26,165 次。',fontsize=10,color=GRAY)
ax=fig.add_axes([.08,.15,.42,.7]);
ud=dim[(dim.dimension=='user_structure')].sort_values('delta'); bars=ax.barh(ud.value,ud.delta,color=[GRAY,TEAL]); ax.axvline(0,color='#333',lw=1); ax.set_title('用户结构贡献',loc='left',weight='bold',color=NAVY); ax.grid(axis='x',alpha=.2)
for b,v in zip(bars,ud.delta): ax.text(v + (-250 if v<0 else 250),b.get_y()+b.get_height()/2,f'{v:+,}',va='center',ha='right' if v<0 else 'left',color=NAVY,fontsize=10)
ax2=fig.add_axes([.56,.15,.38,.7]); hd=dim[(dim.dimension=='hour_bucket')].sort_values('delta'); bars=ax2.barh(hd.value,hd.delta,color=[GRAY if x<0 else TEAL for x in hd.delta]); ax2.axvline(0,color='#333',lw=1); ax2.set_title('时段贡献',loc='left',weight='bold',color=NAVY); ax2.grid(axis='x',alpha=.2)
for b,v in zip(bars,hd.delta): ax2.text(v + (-120 if v<0 else 120),b.get_y()+b.get_height()/2,f'{v:+,}',va='center',ha='right' if v<0 else 'left',color=NAVY,fontsize=10)
save(fig,'看板06_异动归因.png')

# A/B 样本量图。
fig=plt.figure(figsize=(15,7)); fig.suptitle('A/B 样本量方案：32,538 对应绝对 +1 个百分点',x=.04,y=.96,ha='left',fontsize=21,weight='bold',color=NAVY)
fig.text(.04,.9,'α=0.05，power=0.8，双侧，1:1；基线为收藏/加购→购买转化率 70.17%。',fontsize=10,color=GRAY)
ax=fig.add_axes([.08,.18,.38,.62]); b=ax.bar(ab.scenario,ab.n_per_group,color=[BLUE,ORANGE]); ax.set_ylabel('每组样本量'); ax.grid(axis='y',alpha=.2)
for bar,v in zip(b,ab.n_per_group): ax.text(bar.get_x()+bar.get_width()/2,v*1.02,f'{v:,}',ha='center',weight='bold',color=NAVY)
ax2=fig.add_axes([.57,.18,.35,.62]); x=np.arange(len(ab)); ax2.bar(x-.18,ab.baseline_rate,.36,color=GRAY,label='baseline'); ax2.bar(x+.18,ab.target_rate,.36,color=TEAL,label='target'); ax2.set_xticks(x); ax2.set_xticklabels(ab.scenario); ax2.yaxis.set_major_formatter(mtick.PercentFormatter(1)); ax2.grid(axis='y',alpha=.2); ax2.legend(frameon=False); ax2.set_title('基线 vs 目标转化率',loc='left',weight='bold',color=NAVY)
save(fig,'看板07_AB样本量.png')

print('advanced figures done')
