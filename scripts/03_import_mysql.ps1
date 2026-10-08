$ErrorActionPreference = 'Stop'
if (-not $env:MYSQL_PWD) { throw '请先在当前 PowerShell 会话设置 MYSQL_PWD，不要把密码写进脚本。' }
$Mysql = 'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$SqlRoot = $Root -replace '\\','/'
$Tsv = 'D:\datasets\UserBehavior\prepared\clean_events_mysql.tsv'

& $Mysql --host=127.0.0.1 --port=3306 --user=root --local-infile=1 -e "SET GLOBAL local_infile=1; SOURCE $SqlRoot/sql/01_create_schema.sql; TRUNCATE TABLE taobao_userbehavior.fact_user_behavior;"
if ($LASTEXITCODE -ne 0) { throw '建库建表失败' }

& $Mysql --host=127.0.0.1 --port=3306 --user=root --local-infile=1 -e @"
USE taobao_userbehavior;
LOAD DATA LOCAL INFILE '$($Tsv -replace '\\','/')'
INTO TABLE fact_user_behavior
FIELDS TERMINATED BY '\t'
LINES TERMINATED BY '\n'
(user_id, item_id, category_id, behavior_code, event_ts);
SELECT COUNT(*) AS loaded_rows FROM fact_user_behavior;
"@
if ($LASTEXITCODE -ne 0) { throw 'LOAD DATA 失败' }

# 默认只建一个时间索引；磁盘够大再手动执行 02b_optional_indexes_if_capacity.sql。
& $Mysql --host=127.0.0.1 --port=3306 --user=root -e "SOURCE $SqlRoot/sql/02_add_indexes.sql; SHOW INDEX FROM taobao_userbehavior.fact_user_behavior;"
