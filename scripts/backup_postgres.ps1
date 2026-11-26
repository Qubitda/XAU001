# Daily Postgres logical backup for Tara Gold (Windows / local ops).
# Example Task Scheduler:
#   powershell -File C:\XAU001\scripts\backup_postgres.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$BackupDir = if ($env:BACKUP_DIR) { $env:BACKUP_DIR } else { Join-Path $Root "backups\postgres" }
$RetentionDays = if ($env:BACKUP_RETENTION_DAYS) { [int]$env:BACKUP_RETENTION_DAYS } else { 14 }
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

$envFile = Join-Path $Root ".env"
if (Test-Path $envFile) {
  Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    $idx = $line.IndexOf("=")
    if ($idx -lt 1) { return }
    $key = $line.Substring(0, $idx).Trim()
    $val = $line.Substring($idx + 1).Trim().Trim('"').Trim("'")
    Set-Item -Path "Env:$key" -Value $val
  }
}

$db = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "taragold" }
$user = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "taragold" }
$host = if ($env:POSTGRES_HOST) { $env:POSTGRES_HOST } else { "localhost" }
$port = if ($env:POSTGRES_PORT) { $env:POSTGRES_PORT } else { "5432" }
if (-not $env:POSTGRES_PASSWORD) { throw "POSTGRES_PASSWORD is required" }

$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$out = Join-Path $BackupDir "taragold_$stamp.dump"
$env:PGPASSWORD = $env:POSTGRES_PASSWORD
& pg_dump --host=$host --port=$port --username=$user --format=custom --file=$out $db
Write-Host "Wrote $out"

Get-ChildItem $BackupDir -Filter "taragold_*.dump" |
  Where-Object { $_.LastWriteTimeUtc -lt (Get-Date).ToUniversalTime().AddDays(-$RetentionDays) } |
  Remove-Item -Force
Write-Host "Retention applied (${RetentionDays}d)"
