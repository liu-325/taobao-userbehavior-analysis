param(
    [string]$DataDir = 'D:\datasets\UserBehavior'
)
$ErrorActionPreference = 'Stop'
$Url = 'https://www.kaggle.com/api/v1/datasets/download/marwa80/userbehavior'
$Zip = Join-Path $DataDir 'UserBehavior.csv.zip'
New-Item -ItemType Directory -Force $DataDir | Out-Null
if (-not (Test-Path $Zip)) {
    curl.exe -L --fail --retry 3 --output $Zip $Url
}
# 公开镜像和天池官方描述的是同一份 100m 行为日志；下完先做大小/哈希记录，避免下到半个文件还以为成功了。
$Hash = (Get-FileHash $Zip -Algorithm SHA256).Hash
"$Hash  $Zip" | Set-Content (Join-Path $DataDir 'UserBehavior.csv.zip.sha256')
if (-not (Test-Path (Join-Path $DataDir 'UserBehavior.csv'))) {
    tar.exe -xf $Zip -C $DataDir
}
Get-Item (Join-Path $DataDir 'UserBehavior.csv') | Select-Object FullName,Length,LastWriteTime
