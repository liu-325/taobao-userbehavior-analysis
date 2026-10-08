from pathlib import Path
import json, uuid, shutil, hashlib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'outputs' / 'powerbi'
PBIP = ROOT / 'powerbi' / 'TaobaoDashboard.pbip'
REPORT = ROOT / 'powerbi' / 'TaobaoDashboard.Report'
MODEL = ROOT / 'powerbi' / 'TaobaoDashboard.SemanticModel'
for p in [REPORT, MODEL]:
    if p.exists(): shutil.rmtree(p)
(REPORT/'definition'/'pages').mkdir(parents=True, exist_ok=True)
(MODEL/'definition'/'tables').mkdir(parents=True, exist_ok=True)

def guid(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'taobao-userbehavior-analysis/' + name))

def sid(name):
    # PBIR/PBIP 里页面和视觉容器名统一用 20 位十六进制，别再用 p1/v1 这种简写。
    return hashlib.md5(('taobao-userbehavior-analysis/' + name).encode('utf-8')).hexdigest()[:20]

def mtype(col, series):
    if pd.api.types.is_integer_dtype(series): return 'Int64.Type', 'int64'
    if pd.api.types.is_float_dtype(series): return 'type number', 'double'
    if 'date' in str(col).lower(): return 'type date', 'dateTime'
    return 'type text', 'string'

# 看板不要直接拿数值 category_id 当分类轴，Power BI 会把它画成连续坐标；先导出字符串标签。
_cat = pd.read_csv(DATA/'06_funnel_by_category.csv')
_top = _cat[_cat['pv_users'] >= 5000].nlargest(8, 'pv_to_buy').copy()
_top['category_label'] = '类目 ' + _top['category_id'].astype(str)
_top[['category_label','category_id','pv_users','intent_users','buyer_users','pv_to_buy','intent_to_buy']].to_csv(DATA/'top_category_dashboard.csv', index=False, encoding='utf-8-sig')
# 原字段叫 segment 容易和用户分层混淆，看板里改成 day_type。
_time = pd.read_csv(DATA/'09_weekend_user_day.csv').rename(columns={'segment':'day_type'})
_time.to_csv(DATA/'time_segment_dashboard.csv', index=False, encoding='utf-8-sig')

table_files = {
 'OverallKPI':'01_overall_kpi.csv',
 'BehaviorMix':'02_behavior_mix.csv',
 'DailyMetrics':'03_daily_metrics.csv',
 'HourlyMetrics':'04_hourly_metrics.csv',
 'FunnelOverall':'05_funnel_overall.csv',
 'CategorySummary':'06_funnel_by_category.csv',
 'RfmSegments':'07_rfm_segments.csv',
 'WeekendWeekday':'09_weekend_user_day.csv',
 'DaypartRates':'10_hour_daypart_user_hour.csv',
 'TestResults':'11_statistical_tests.csv',
 'TopCategory':'top_category_dashboard.csv',
 'TimeSegment':'time_segment_dashboard.csv',
}

def csv_expr(table, file):
    return f'File.Contents(DataFolder & "/{file}")'

def tmdl_table(table, file):
    df = pd.read_csv(DATA/file, nrows=20)
    lines=[f'table {table}', f'\tlineageTag: {guid(table+"-table")}']
    # 先写列，类型按读到的样本判断；日期只给 DailyMetrics 的 event_date。
    for col in df.columns:
        py, tab = mtype(col, df[col])
        summarize = 'sum' if any(k in col for k in ['actions','users','rows','share','rate','count','behaviors','conversion']) else 'none'
        lines += [f'\tcolumn {col}', f'\t\tdataType: {tab}', f'\t\tsummarizeBy: {summarize}', f'\t\tsourceColumn: {col}']
    # 关键 measure，避免报表里到处写裸聚合。
    measures=[]
    if table=='OverallKPI':
        measures=[('行为总量','SUM(OverallKPI[behaviors])','#,##0'),('活跃用户','SUM(OverallKPI[active_users])','#,##0'),('购买用户','SUM(OverallKPI[buyer_users])','#,##0'),('购买用户率','DIVIDE([购买用户],[活跃用户])','0.00%'),('购买行为','SUM(OverallKPI[buy_actions])','#,##0')]
    elif table=='FunnelOverall':
        measures=[('漏斗用户数','SUM(FunnelOverall[stage_users])','#,##0')]
    elif table=='RfmSegments':
        measures=[('分群用户数','SUM(RfmSegments[users])','#,##0'),('分群购买行为','SUM(RfmSegments[buy_actions])','#,##0'),('购买贡献','SUM(RfmSegments[buy_action_share])','0.00%')]
    elif table=='WeekendWeekday':
        measures=[('周末工作日购买率','AVERAGE(WeekendWeekday[buyer_rate])','0.00%')]
    elif table=='DaypartRates':
        measures=[('时段购买率','AVERAGE(DaypartRates[buyer_rate])','0.00%')]
    elif table=='CategorySummary':
        measures=[('类目浏览用户','SUM(CategorySummary[pv_users])','#,##0'),('类目购买用户','SUM(CategorySummary[buyer_users])','#,##0'),('类目浏览购买率','AVERAGE(CategorySummary[pv_to_buy])','0.00%')]
    elif table=='HourlyMetrics':
        measures=[('小时购买行为','SUM(HourlyMetrics[buy_actions])','#,##0')]
    for name,expr,fmt in measures:
        lines += [f'\tmeasure \'{name}\' = {expr}', f'\t\tformatString: {fmt}', f'\t\tlineageTag: {guid(table+"-"+name)}']
    lines += [f'\tpartition {table}-{guid(table+"-partition")[:8]} = m', '\t\tmode: import', '\t\tsource =', '\t\t\tlet', f'\t\t\t\tSource = Csv.Document({csv_expr(table,file)},[Delimiter=",",Encoding=65001,QuoteStyle=QuoteStyle.Csv]),', '\t\t\t\tPromoted = Table.PromoteHeaders(Source,[PromoteAllScalars=true]),', '\t\t\t\tTyped = Table.TransformColumnTypes(Promoted,{'+ ','.join([f'{{"{c}", {mtype(c,df[c])[0]}}}' for c in df.columns]) + '})', '\t\t\tin', '\t\t\t\tTyped', f'\tannotation PBI_ResultType = Table']
    return '\n'.join(lines)+'\n'

for table,file in table_files.items():
    (MODEL/'definition'/'tables'/f'{table}.tmdl').write_text(tmdl_table(table,file),encoding='utf-8')

(MODEL/'definition.pbism').write_text(json.dumps({'version':'4.1','settings':{'qnaEnabled':True}},indent=2),encoding='utf-8')
(MODEL/'definition'/'database.tmdl').write_text('database\n\tcompatibilityLevel: 1601\n',encoding='utf-8')
model_lines=['model Model','\tculture: en-US','\tdefaultPowerBIDataSourceVersion: powerBI_V3','\tsourceQueryCulture: en-US','\tannotation PBI_ProTooling = ["TMDLView_Desktop"]']
for table in table_files: model_lines.append(f'ref table {table}')
(MODEL/'definition'/'model.tmdl').write_text('\n'.join(model_lines)+'\n',encoding='utf-8')
(MODEL/'definition'/'expressions.tmdl').write_text(f'expression DataFolder = "{DATA.as_posix()}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n\tlineageTag: {guid("DataFolder")}\n\n\tannotation PBI_ResultType = Text\n',encoding='utf-8')
# 不需要关系也能做单表筛选；所有页面都放各自可交互 slicer。

(REPORT/'definition.pbir').write_text(json.dumps({'version':'4.0','datasetReference':{'byPath':{'path':'../TaobaoDashboard.SemanticModel'}}},indent=2),encoding='utf-8')
(REPORT/'definition'/'version.json').write_text(json.dumps({'$schema':'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json','version':'2.0.0'},indent=2),encoding='utf-8')
# Base theme 是报告渲染需要的静态资源，不当成模型表。
(REPORT/'StaticResources'/'SharedResources'/'BaseThemes').mkdir(parents=True,exist_ok=True)
shutil.copy2(ROOT/'powerbi'/'theme'/'CY23SU04.json', REPORT/'StaticResources'/'SharedResources'/'BaseThemes'/'CY23SU04.json')
(REPORT/'definition'/'report.json').write_text(json.dumps({'$schema':'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/1.3.0/schema.json','themeCollection':{'baseTheme':{'name':'CY23SU04','reportVersionAtImport':'5.46','type':'SharedResources'}},'layoutOptimization':'None','settings':{'useStylableVisualContainerHeader':True,'exportDataMode':'AllowSummarizedAndUnderlying'},'resourcePackages':[{'name':'SharedResources','type':'SharedResources','items':[{'name':'CY23SU04','path':'BaseThemes/CY23SU04.json','type':'BaseTheme'}]}]},ensure_ascii=False,indent=2),encoding='utf-8')

def lit(v): return {'expr':{'Literal':{'Value':v}}}
def text_visual(name,x,y,w,h,text,size=18,color='#17324d',align='left'):
    return {
      '$schema':'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json',
      'name':name,
      'position':{'x':x,'y':y,'z':1,'height':h,'width':w,'tabOrder':1},
      'visual':{
        'visualType':'textbox',
        'objects':{'general':[{'properties':{'paragraphs':[{'textRuns':[{'value':text,'textStyle':{'fontSize':f'{size}pt','color':color,'fontWeight':('bold' if size>=14 else 'normal')}}],'horizontalTextAlignment':align}]}}]},
        'drillFilterOtherVisuals':True
      }
    }
def card(name,x,y,w,h,entity,measure,title=None):
    return {'$schema':'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json','name':name,'position':{'x':x,'y':y,'z':5,'height':h,'width':w,'tabOrder':5},'visual':{'visualType':'card','query':{'queryState':{'Values':{'projections':[{'field':{'Measure':{'Expression':{'SourceRef':{'Entity':entity}},'Property':measure}},'queryRef':f'{entity}.{measure}'}]}}},'objects':{'categoryLabels':[{'properties':{'show':lit('false')}}]},'visualContainerObjects':({'title':[{'properties':{'text':lit("\""+title+"\""),'show':lit('true')}}]} if title else {}),'drillFilterOtherVisuals':True}}
def column(name,x,y,w,h,entity,category,value,aggregate=False,title=''):
    if aggregate:
        yfield={'Aggregation':{'Expression':{'Column':{'Expression':{'SourceRef':{'Entity':entity}},'Property':value}},'Function':0}}
        yref=f'Sum({entity}.{value})'
    else:
        yfield={'Measure':{'Expression':{'SourceRef':{'Entity':entity}},'Property':value}}
        yref=f'{entity}.{value}'
    query={'queryState':{'Category':{'projections':[{'field':{'Column':{'Expression':{'SourceRef':{'Entity':entity}},'Property':category}},'queryRef':f'{entity}.{category}','active':True}]},'Y':{'projections':[{'field':yfield,'queryRef':yref}]}},'sortDefinition':{'sort':[{'field':yfield,'direction':'Descending'}]}}
    v={'$schema':'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json','name':name,'position':{'x':x,'y':y,'z':3,'height':h,'width':w,'tabOrder':3},'visual':{'visualType':'columnChart','query':query,'drillFilterOtherVisuals':True}}
    if title: v['visual']['visualContainerObjects']={'title':[{'properties':{'text':lit("'"+title+"'"),'show':lit('true')}}]}
    return v
def bar(name,x,y,w,h,entity,category,value,aggregate=False,title='',sort_category=False):
    v=column(name,x,y,w,h,entity,category,value,aggregate,title)
    v['visual']['visualType']='barChart'
    if sort_category:
        v['visual']['query']['sortDefinition']={'sort':[{'field':{'Column':{'Expression':{'SourceRef':{'Entity':entity}},'Property':category}},'direction':'Ascending'}]}
    return v

def funnel(name,x,y,w,h):
    field={'Measure':{'Expression':{'SourceRef':{'Entity':'FunnelOverall'}},'Property':'漏斗用户数'}}
    return {'$schema':'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json','name':name,'position':{'x':x,'y':y,'z':4,'height':h,'width':w,'tabOrder':4},'visual':{'visualType':'funnel','query':{'queryState':{'Category':{'projections':[{'field':{'Column':{'Expression':{'SourceRef':{'Entity':'FunnelOverall'}},'Property':'stage'}},'queryRef':'FunnelOverall.stage','active':True}]},'Y':{'projections':[{'field':field,'queryRef':'FunnelOverall.漏斗用户数'}]}},'sortDefinition':{'sort':[{'field':field,'direction':'Descending'}]}},'drillFilterOtherVisuals':True}}
def slicer(name,x,y,w,h,entity,column):
    f={'Column':{'Expression':{'SourceRef':{'Entity':entity}},'Property':column}}
    return {
      '$schema':'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json',
      'name':name,
      'position':{'x':x,'y':y,'z':2,'height':h,'width':w,'tabOrder':2},
      'visual':{
        'visualType':'slicer',
        'query':{'queryState':{'Values':{'projections':[{'field':f,'queryRef':f'{entity}.{column}','active':True}]}}},
        'drillFilterOtherVisuals':True
      }
    }
def page(page_id, display, visuals):
    real_id = sid(page_id)
    for v in visuals:
        v['name'] = sid(v['name'])
    return {'$schema':'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/1.4.0/schema.json','name':real_id,'displayName':display,'displayOption':'FitToPage','height':720,'width':1280,'pageBinding':{'name':sid(page_id+'-binding'),'type':'Default','parameters':[],'acceptsFilterContext':'None'},'visuals':visuals}

pages={}
pages['p1'] = page('p1','经营总览',[
 text_visual('p1t',30,15,900,45,'淘宝用户行为全链路经营看板｜经营总览',24),
 text_visual('p1n',30,92,1200,24,'口径：2017-11-25 至 12-03｜100,095,182 条行为｜无价格字段，不计算 GMV。',10,'#687381'),
 text_visual('p1l1',40,55,280,32,'总行为数',14,'#17324d'),text_visual('p1l2',340,55,280,32,'活跃用户',14,'#17324d'),text_visual('p1l3',640,55,280,32,'购买用户',14,'#17324d'),text_visual('p1l4',940,55,280,32,'购买用户率',14,'#17324d'),
 card('p1c1',40,120,280,90,'OverallKPI','行为总量'),card('p1c2',340,120,280,90,'OverallKPI','活跃用户'),card('p1c3',640,120,280,90,'OverallKPI','购买用户'),card('p1c4',940,120,280,90,'OverallKPI','购买用户率'),
 column('p1v1',50,250,560,360,'DailyMetrics','event_date','active_users',True,'逐日活跃用户'),column('p1v2',650,250,560,360,'DailyMetrics','event_date','buy_actions',True,'逐日购买行为')])
pages['p2'] = page('p2','转化漏斗',[
 text_visual('p2t',30,15,1000,45,'转化漏斗：最大流失在收藏/加购→购买',24),
 text_visual('p2n',30,60,1200,30,'严格包含式口径：下一层用户必须同时具备上一层行为。',10,'#687381'),
 funnel('p2f',60,120,560,500),bar('p2c',660,120,560,500,'TopCategory','category_label','pv_to_buy',True,'高转化匿名类目ID（浏览用户≥5,000）')])
pages['p3'] = page('p3','用户分层',[
 text_visual('p3t',30,15,1100,45,'用户价值分层：高价值复购用户贡献 41.73% 购买行为',24),
 bar('p3u',60,140,550,460,'RfmSegments','segment','users',True,'各分层用户数',True),bar('p3b',670,140,550,460,'RfmSegments','segment','buy_action_share',True,'各分层购买行为占比',True)])
pages['p4'] = page('p4','品类与时段',[
 text_visual('p4t',30,15,1100,45,'时段分析：晚间购买率小幅高于白天，周末低于工作日',24),
 column('p4h',60,140,550,460,'HourlyMetrics','event_hour','buy_actions',True,'24小时购买行为'),column('p4w',670,140,550,460,'TimeSegment','day_type','buyer_rate',True,'周末 vs 工作日购买用户率')])

page_order=[p['name'] for p in pages.values()]
(REPORT/'definition'/'pages'/'pages.json').write_text(json.dumps({'$schema':'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json','pageOrder':page_order,'activePageName':page_order[0]},indent=2),encoding='utf-8')
for p in pages.values():
    pid=p['name']; d=REPORT/'definition'/'pages'/pid;(d/'visuals').mkdir(parents=True,exist_ok=True)
    # page.json 不应包含 visuals 数组，避免 PBIR 校验报错。
    pj={k:v for k,v in p.items() if k!='visuals'}
    (d/'page.json').write_text(json.dumps(pj,ensure_ascii=False,indent=2),encoding='utf-8')
    for v in p['visuals']:
        vd=d/'visuals'/v['name'];vd.mkdir(parents=True,exist_ok=True)
        (vd/'visual.json').write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')

PBIP.write_text(json.dumps({'version':'1.0','artifacts':[{'report':{'path':'TaobaoDashboard.Report'}}],'settings':{'enableAutoRecovery':True}},indent=2),encoding='utf-8')
print(PBIP)
