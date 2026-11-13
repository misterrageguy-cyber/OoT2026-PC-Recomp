# Build the launcher and installer from this source checkout. Game data is never used here.
param(
    [string]$Runtime = "$env:LOCALAPPDATA\Programs\Ocarina Reborn",
    [string]$Out = "",
    [string]$Iscc = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    [switch]$StageOnly
)
$ErrorActionPreference = 'Stop'
$SourceRoot = (Resolve-Path -LiteralPath "$PSScriptRoot\..").Path
if (-not $Out) { $Out = Join-Path $SourceRoot 'build\source-stage' }
$Python = Join-Path $Runtime 'python\python.exe'
$CompilerBin = Join-Path $Runtime 'engine\llvm-mingw\bin'
$Version = (Get-Content -LiteralPath "$SourceRoot\tools\alpha\VERSION" -Raw).Trim()
& $Python "$PSScriptRoot\stage_source.py" --runtime $Runtime --out $Out
if ($LASTEXITCODE) { throw 'Source staging failed' }
$Stage = (Resolve-Path -LiteralPath $Out).Path
$Native = Join-Path $SourceRoot 'tools\alpha\exe'
$Object = Join-Path $Stage 'launcher-resource.o'
$Resource = Join-Path $Stage 'launcher-version.rc'
$VersionComma = (@($Version -split '\.') + @('0')) -join ','
$Text = (Get-Content -LiteralPath "$Native\ocarina_reborn.rc" -Raw).Replace('VER_COMMA', $VersionComma).Replace('VER_TEXT', "`"$Version`"")
$Text = $Text.Replace('../OcarinaReborn.ico', (Join-Path $SourceRoot 'tools/alpha/OcarinaReborn.ico').Replace('\', '/'))
Set-Content -LiteralPath $Resource -Encoding ascii -Value $Text
Push-Location $Native
try {
    & "$CompilerBin\llvm-windres.exe" $Resource -O coff -o $Object
    if ($LASTEXITCODE) { throw 'Launcher resource compilation failed' }
    & "$CompilerBin\clang.exe" -O2 -municode -mwindows -static ocarina_reborn.c $Object -o "$Stage\OcarinaReborn.exe"
    if ($LASTEXITCODE) { throw 'Launcher compilation failed' }
} finally { Pop-Location }
Remove-Item -LiteralPath $Resource, $Object
& "$CompilerBin\clang.exe" -O2 -shared -D_WIN32_WINNT=0x0A00 "$SourceRoot\tools\alpha\launcher\chrome.c" -o "$Stage\launcher\ocr_chrome.dll" -lcomctl32 -lshell32 -luser32
if ($LASTEXITCODE) { throw 'Launcher window compilation failed' }
if ($StageOnly) { Write-Host "Ready: $Stage"; exit 0 }
if (-not (Test-Path -LiteralPath $Iscc)) { throw 'Install Inno Setup 6 or pass -Iscc with the compiler path.' }
$Dist = Join-Path $SourceRoot 'build\dist'
New-Item -ItemType Directory -Path $Dist -Force | Out-Null
& $Iscc "/DStage=$Stage" "/DOut=$Dist" "/DAppVersion=$Version" "$SourceRoot\tools\alpha\installer.iss"
if ($LASTEXITCODE) { throw 'Installer compilation failed' }
Get-FileHash -LiteralPath "$Dist\Ocarina-Reborn-Alpha-Setup.exe" -Algorithm SHA256
