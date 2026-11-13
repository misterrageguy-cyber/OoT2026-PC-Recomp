# Developer side: builds dist\Ocarina-Reborn-Alpha-Setup.exe from the CURRENT working tree.
#   powershell -ExecutionPolicy Bypass -File tools\alpha\build_alpha.ps1 -Server https://<your server>:8443
# Needs this machine's du-h\work (Python venv, llvm-mingw, runtime-deps, translator) and Inno Setup 6 (ISCC.exe).
# The tester PC needs none of it: the installer carries python\, llvm\, deps\ and the tools.
param(
    [string]$Server = "",   # empty: offline activation (PC-ID -> license.dat from server.py issue-license)
    [string]$Work = "C:\OcarinaBuild\dependencies",
    [string]$Iscc = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    [string]$Engine = ""   # the engine folder under build\alpha (hookshot-<Engine>); empty: v2.1.0
)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path "$PSScriptRoot\..\..").Path
$Alpha = "$Root\tools\alpha"
$Stage = "$Root\build\alpha\stage"
$Dist = "$Root\dist"
$Py = "$Work\venv\Scripts\python.exe"
$Llvm = (Get-ChildItem "$Work\toolchain" -Directory -Filter 'llvm-mingw-*-ucrt-x86_64' | Select-Object -First 1).FullName

# 1. source tree and commit
$Commit = (git -C $Root rev-parse --short HEAD)
if ((git -C $Root status --porcelain).Length -gt 0) { $Commit = "$Commit+local" }
if (-not (Test-Path "$Alpha\licensing-server\keys\public.hex")) { throw 'run licensing-server\server.py init-keys first' }

# 2. OcarinaReborn.exe (icon and version info)
# (one version for the exe, the installer and the launcher: tools\alpha\VERSION, raised by one for each release)
$Ver = (Get-Content "$Alpha\VERSION" -Raw).Trim()
if ($Ver -notmatch '^(\d+)\.(\d+)\.(\d+)(?:-(\d+))?$') { throw 'VERSION must be X.Y.Z or X.Y.Z-N' }
$Revision = if ($Matches[4]) { $Matches[4] } else { '0' }
$VerComma = @($Matches[1], $Matches[2], $Matches[3], $Revision) -join ','
$FileVersion = $VerComma.Replace(',', '.')
Push-Location "$Alpha\exe"
(Get-Content ocarina_reborn.rc -Raw).Replace('VER_COMMA', $VerComma).Replace('VER_TEXT', "`"$Ver`"") |
    Set-Content -Encoding ascii versioned.rc
& "$Llvm\bin\llvm-windres.exe" versioned.rc -O coff -o rc.o
if ($LASTEXITCODE) { throw 'Launcher resource compilation failed' }
& "$Llvm\bin\clang.exe" -O2 -municode -mwindows -static ocarina_reborn.c rc.o -o OcarinaReborn.exe
if ($LASTEXITCODE) { throw 'Launcher compilation failed' }
Remove-Item rc.o, versioned.rc
Pop-Location
# the launcher window's frame (ocr_chrome.dll: its window procedure in C, see launcher\chrome.c)
& "$Llvm\bin\clang.exe" -O2 -shared -D_WIN32_WINNT=0x0A00 "$Alpha\launcher\chrome.c" -o "$Alpha\launcher\ocr_chrome.dll" -lcomctl32 -lshell32 -luser32
if ($LASTEXITCODE) { throw 'ocr_chrome.dll failed' }

# Hookshot's build tools, pinned: a copy of the Hookshot Builder's current tools kept under build\alpha, so a later update
# of the builder (which deletes its old version) does not change what the installer carries
# (Ocarina Reborn's engine: v2.1.0's source with the pinned toolchain, build\alpha\hookshot-v2.1.0; stage_alpha.py, hud_v21.py and
# engine_v21.py put Ocarina Reborn's look, name and additions on it. -Engine v2.0.12 builds the earlier one)
# (2026-11-13: v2.2.0-rc.1, its source (git tag) with v2.1.0's pinned toolchain beside it: llvm-mingw, python, cpm, wgpu-native)
$HsVersion = if ($Engine) { $Engine } else { 'v2.2.0-rc.1' }
$HookshotTools = "$Root\build\alpha\hookshot-$HsVersion\tools"
if (-not (Test-Path "$HookshotTools\nx2\make_game.py")) {
    throw "the engine $HsVersion is not in build\alpha\hookshot-$HsVersion"
}
if ($false) {
    New-Item -ItemType Directory -Force (Split-Path $HookshotTools) | Out-Null
    robocopy "$env:LOCALAPPDATA\HookshotBuilder\versions\$HsVersion\HookshotBuilder\tools" $HookshotTools /E /XD emsdk __pycache__ /NFL /NDL /NJH /NJS | Out-Null
    Copy-Item "$env:LOCALAPPDATA\HookshotBuilder\versions\$HsVersion\HookshotBuilder\LICENSE" (Split-Path $HookshotTools)
}

# 3. install folder (python, launcher, Hookshot's tools; no game data, no private key)
& $Py "$Alpha\stage_alpha.py" --work $Work --out $Stage --hookshot $HookshotTools "--server=$Server" --commit $Commit
if ($LASTEXITCODE) { throw 'staging failed' }

# 4. installer
New-Item -ItemType Directory -Force $Dist | Out-Null
& $Iscc "/DStage=$Stage" "/DOut=$Dist" "/DAppVersion=$Ver" "/DAppFileVersion=$FileVersion" "$Alpha\installer.iss"
if ($LASTEXITCODE) { throw 'Inno Setup failed' }

# 5. checksum, build info, README
$Setup = "$Dist\Ocarina-Reborn-Alpha-Setup.exe"
$Hash = (Get-FileHash $Setup -Algorithm SHA256).Hash.ToLower()
"$Hash  Ocarina-Reborn-Alpha-Setup.exe" | Out-File -Encoding ascii "$Setup.sha256"
Copy-Item "$Stage\build-info.json" "$Dist\build-info.json"
Copy-Item "$Alpha\Tester-README.txt" "$Dist\Tester-README.txt"
Write-Host "Done: $Setup  ($([math]::Round((Get-Item $Setup).Length / 1MB)) MB)  sha256 $Hash"
