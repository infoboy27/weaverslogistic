# Off-box copy of the nightly backups (Windows scheduled task "Weavers Backup Pull").
# Pulls the newest db-*.dump and files-*.tgz from the server and keeps the last 30 days locally.
param(
    [string]$Dest = "C:\jfmcs\backups\weaverslogistic",
    [string]$Server = "ubuntu@163.245.207.38",
    [int]$Port = 1600
)
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force $Dest | Out-Null
$log = Join-Path $Dest "pull.log"
try {
    $latest = ssh -p $Port -o BatchMode=yes $Server "ls -1t /home/ubuntu/backups/weaverslogistic/db-*.dump /home/ubuntu/backups/weaverslogistic/files-*.tgz | head -2"
    if (-not $latest) { throw "no hay respaldos en el servidor" }
    foreach ($remote in $latest) {
        $name = Split-Path $remote -Leaf
        if (-not (Test-Path (Join-Path $Dest $name))) {
            scp -q -P $Port -o BatchMode=yes "${Server}:$remote" (Join-Path $Dest $name)
            if ($LASTEXITCODE -ne 0) { throw "scp falló: $name" }
        }
    }
    Get-ChildItem $Dest -File | Where-Object { $_.Name -match '^(db|files)-' -and $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
        Remove-Item -Force
    "$(Get-Date -Format s) OK $($latest -join ', ')" | Add-Content $log
} catch {
    "$(Get-Date -Format s) ERROR $_" | Add-Content $log
    exit 1
}
