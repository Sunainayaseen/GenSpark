# Usage: .\scripts\update-production-api-url.ps1 -ApiUrl "https://your-new-api.up.railway.app"
param(
    [Parameter(Mandatory = $true)]
    [string]$ApiUrl
)

$ApiUrl = $ApiUrl.Trim().TrimEnd('/')
$root = Split-Path $PSScriptRoot -Parent

$files = @(
    @{ Path = 'my-react-app\vercel.json'; Pattern = 'https://genspark-production\.up\.railway\.app'; Replace = $ApiUrl },
    @{ Path = 'my-react-app\.env.production'; Pattern = 'VITE_API_BASE=.*'; Replace = "VITE_API_BASE=$ApiUrl" },
    @{ Path = 'my-react-app\src\config\deployUrls.js'; Pattern = "export const LIVE_API_URL = .*"; Replace = "export const LIVE_API_URL = '$ApiUrl';" }
)

foreach ($f in $files) {
    $full = Join-Path $root $f.Path
    if (-not (Test-Path $full)) { Write-Warning "Skip missing $full"; continue }
    $text = Get-Content $full -Raw -Encoding UTF8
    if ($f.Path -like '*vercel.json*') {
        $text = $text -replace 'https://genspark-production\.up\.railway\.app', $ApiUrl
    } elseif ($f.Path -like '*.env.production*') {
        $text = $text -replace 'VITE_API_BASE=.*', "VITE_API_BASE=$ApiUrl"
    } else {
        $text = $text -replace "export const LIVE_API_URL = '[^']*';", "export const LIVE_API_URL = '$ApiUrl';"
    }
    Set-Content -Path $full -Value $text -Encoding UTF8 -NoNewline
    Write-Host "Updated $f.Path"
}

Write-Host "`nDone. Test: curl $ApiUrl/api/health"
Write-Host "Then git commit + push and redeploy Vercel."
