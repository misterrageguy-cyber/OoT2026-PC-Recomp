# Start the existing launcher with audio diagnostics for this run only.
param(
    [ValidateSet('configured', '60')][string]$FrameRate = 'configured',
    [string]$Runtime = "$env:LOCALAPPDATA\Programs\Ocarina Reborn"
)
$ErrorActionPreference = 'Stop'
$LauncherPath = Join-Path $Runtime 'OcarinaReborn.exe'
if (-not (Test-Path -LiteralPath $LauncherPath -PathType Leaf)) {
    throw 'Launcher not found. Pass -Runtime with the installation folder.'
}
if (Get-Process -Name 'OcarinaReborn', 'ocarina_reborn' -ErrorAction SilentlyContinue) {
    throw 'Close the launcher and game before starting this diagnostic run.'
}
$DiagnosticStart = New-Object System.Diagnostics.ProcessStartInfo
$DiagnosticStart.FileName = $LauncherPath
$DiagnosticStart.WorkingDirectory = $Runtime
$DiagnosticStart.UseShellExecute = $false
$DiagnosticStart.EnvironmentVariables['HOS_AUDIO_TRACE'] = '1'
$DiagnosticStart.EnvironmentVariables['HOS_FPS_LOG'] = '1'
# Do not record audio, raw buffers, or change the saved frame-rate setting.
$DiagnosticStart.EnvironmentVariables.Remove('HOS_AUDIO_DUMP')
$DiagnosticStart.EnvironmentVariables.Remove('HOS_AUDIO_WB_DUMP')
if ($FrameRate -eq '60') {
    $DiagnosticStart.EnvironmentVariables['HOS_FPS_MAX'] = '60'
} else {
    $DiagnosticStart.EnvironmentVariables.Remove('HOS_FPS_MAX')
}
$DiagnosticProcess = [System.Diagnostics.Process]::Start($DiagnosticStart)
Write-Host 'Start the game from this launcher and repeat the reported encounter.'
Write-Host 'After the problem occurs, quit the game and create a debug package in the launcher.'
Write-Host 'Note the boss, any melody played, and whether music continues after leaving the room.'
Write-Host "Diagnostic frame rate: $FrameRate. Closing this launcher ends the diagnostic environment."
