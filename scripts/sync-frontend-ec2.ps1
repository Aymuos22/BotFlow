# Build the Vite app on the frontend EC2 (needs Node: installed on first use via this script's SSH).
# Pushes web/ source, runs npm ci + vite build, copies dist to nginx root, updates nginx config from web/deploy.
#
# Usage (repo root, PowerShell):
#   .\scripts\sync-frontend-ec2.ps1
#   .\scripts\sync-frontend-ec2.ps1 -FrontendHost 52.65.65.205 -KeyPath .\secrets\sec-key.pem
param(
  [string] $FrontendHost = "54.166.208.198",
  [string] $User = "ubuntu",
  [string] $KeyPath = "",
  [string] $NginxWebRoot = "/var/www/wa-dashboard"
)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Web = Join-Path $Root "web"
if (-not $KeyPath) {
  $candidates = @(
    (Join-Path $Root "secrets\sec-key.pem"),
    (Join-Path $Web "secrets\sec-key.pem"),
    (Join-Path $Root "secret-key.pem")
  )
  $KeyPath = ($candidates | Where-Object { Test-Path $_ } | Select-Object -First 1)
  if (-not $KeyPath) { throw "Missing SSH key. Use secrets\sec-key.pem, web\secrets\sec-key.pem, or secret-key.pem, or pass -KeyPath." }
}
if (-not (Test-Path $Web)) { throw "Missing web: $Web" }

$tarball = Join-Path $env:TEMP "wa-dashboard-src.tgz"
if (Test-Path $tarball) { Remove-Item $tarball -Force }
Push-Location $Web
try {
  tar -czf $tarball --exclude=node_modules --exclude=dist --exclude=.vite --exclude=*.tgz .
  if ($LASTEXITCODE -ne 0) { throw "tar failed" }
} finally { Pop-Location }

$ssh = @("-i", $KeyPath, "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=accept-new")
Write-Host "Uploading $FrontendHost (source + .env) …"
& scp @ssh $tarball "${User}@${FrontendHost}:/tmp/wa-dashboard-src.tgz"
& scp @ssh (Join-Path $Web ".env") "${User}@${FrontendHost}:wa-dashboard.env"
Remove-Item $tarball -Force -ErrorAction SilentlyContinue

$remote = @"
set -euo pipefail
chmod 600 ~/wa-dashboard.env
rm -rf ~/build-wa-dashboard
mkdir -p ~/build-wa-dashboard
tar -xzf /tmp/wa-dashboard-src.tgz -C ~/build-wa-dashboard
cd ~/build-wa-dashboard
npm ci
npm run build
sudo rm -rf $NginxWebRoot/*
sudo cp -a dist/. $NginxWebRoot/
sudo chmod -R a+rX $NginxWebRoot
sudo cp -f deploy/wa-dashboard.nginx.conf /etc/nginx/sites-available/wa-dashboard
sudo nginx -t
sudo systemctl reload nginx 2>/dev/null || sudo systemctl start nginx
echo "Frontend deployed to $NginxWebRoot"
"@
# PowerShell here-strings use CRLF; bash treats CR as part of the first token and fails (set: pipefail^M).
$remote = $remote -replace "`r`n", "`n" -replace "`r", ""

& ssh @ssh "${User}@${FrontendHost}" $remote
if ($LASTEXITCODE -ne 0) { throw "Remote build failed (exit $LASTEXITCODE)" }
Write-Host "Done. Open http://$FrontendHost/"
