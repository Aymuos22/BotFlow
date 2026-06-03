# Sync this repo to EC2 and rebuild the API container (replaces a GitHub Actions deploy).
# Usage (from repo root, PowerShell):
#   .\scripts\sync-to-ec2.ps1
# Optional: -BackendHost 1.2.3.4 -KeyPath .\secrets\sec-key.pem
param(
  [string] $BackendHost = "44.212.38.114",
  [string] $User = "ubuntu",
  [string] $KeyPath = "",
  [string] $RemotePath = "/opt/chatbot-engine"
)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $KeyPath) {
  $candidates = @(
    (Join-Path $Root "secrets\sec-key.pem"),
    (Join-Path $Root "secret-key.pem")
  )
  $KeyPath = ($candidates | Where-Object { Test-Path $_ } | Select-Object -First 1)
  if (-not $KeyPath) { throw "Missing SSH key. Place secrets\sec-key.pem or secret-key.pem under repo root, or pass -KeyPath." }
}

# Prefer a drive with headroom: C: often runs out of space during large tgz writes.
$tarball = Join-Path $env:TEMP "chatbot-engine-sync.tgz"
$d = Get-PSDrive -Name "D" -ErrorAction SilentlyContinue
if ($d -and $d.Free -gt 500MB) {
  $tarball = "D:\chatbot-engine-sync.tgz"
}
$e = Get-PSDrive -Name "E" -ErrorAction SilentlyContinue
if ($e -and $e.Free -gt 500MB -and -not ($d -and $d.Free -gt 500MB)) {
  $tarball = "E:\chatbot-engine-sync.tgz"
}
if (Test-Path $tarball) { Remove-Item $tarball -Force }
Write-Host "Staging bundle at $tarball"

Push-Location $Root
try {
  tar -czf $tarball `
    --exclude=node_modules `
    --exclude=web/node_modules `
    --exclude=.git `
    --exclude=__pycache__ `
    --exclude=.pytest_cache `
    --exclude=secrets `
    --exclude=.env `
    --exclude=web/.env `
    --exclude=.coverage `
    --exclude=web/dist `
    --exclude=*.pyc `
    .
  if ($LASTEXITCODE -ne 0) { throw "tar failed" }
} finally {
  Pop-Location
}

$ssh = @(
  "-i", $KeyPath, "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=accept-new"
)
Write-Host "Uploading bundle..."
& scp @ssh $tarball "${User}@${BackendHost}:/tmp/chatbot-engine-sync.tgz"
& scp @ssh (Join-Path $Root "scripts\remote-extract-and-rebuild.sh") "${User}@${BackendHost}:/tmp/remote-extract-and-rebuild.sh"
Write-Host "Extract + Docker rebuild on server..."
# Normalize CRLF if the shell script was saved from Windows
$remote = "sed -i 's/\r$//' /tmp/remote-extract-and-rebuild.sh && bash /tmp/remote-extract-and-rebuild.sh"
& ssh @ssh "${User}@${BackendHost}" $remote
Write-Host "Done."
Remove-Item $tarball -Force -ErrorAction SilentlyContinue
