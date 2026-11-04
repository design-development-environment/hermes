param(
    [ValidateSet(0,1)][int]$DeleteData=0,
    [ValidateSet(0,1)][int]$RemovePython=0,
    [ValidateSet(0,1)][int]$RemoveGit=0,
    [ValidateSet(0,1)][int]$RemoveNode=0,
    [ValidateSet(0,1)][int]$RemoveCode=0,
    [ValidateSet(0,1)][int]$RemoveTailscale=0
)
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$privateRoot=Join-Path $env:LOCALAPPDATA 'Hermes'
$log=Join-Path $env:LOCALAPPDATA 'Hermes-uninstall.log'
function Remove-HermesTree([string]$Path) {
    if (!(Test-Path -LiteralPath $Path)) { return }
    # Never follow user-created junctions or symlinks during cleanup.
    $item=Get-Item -LiteralPath $Path -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Refusing linked folder: $Path" }
    foreach ($child in Get-ChildItem -LiteralPath $Path -Force) {
        if ($child.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Refusing linked entry: $($child.FullName)" }
        if ($child.PSIsContainer) { Remove-HermesTree $child.FullName }
        else { Remove-Item -LiteralPath $child.FullName -Force }
    }
    Remove-Item -LiteralPath $Path -Force
}
try {
    Start-Transcript -Path $log -Append | Out-Null
    New-Item -ItemType Directory -Force "$privateRoot\config" | Out-Null
    Set-Content -LiteralPath "$privateRoot\config\stop" -Value 'stop'
    $runtimePrefix=[IO.Path]::GetFullPath("$root\runtime\")
    function Get-HermesProcesses {
        @(Get-CimInstance Win32_Process | Where-Object {
            $_.ExecutablePath -and $_.ExecutablePath.StartsWith($runtimePrefix,[StringComparison]::OrdinalIgnoreCase)
        })
    }
    $deadline=(Get-Date).AddSeconds(20)
    while ((Get-HermesProcesses).Count -gt 0 -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 500 }
    foreach ($process in Get-HermesProcesses) { Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop }
    Start-Sleep -Milliseconds 500
    if ((Get-HermesProcesses).Count) { throw 'Hermes is still running. Close it and retry uninstall.' }

    $selected=@()
    if ($RemoveGit) { $selected+='Git.Git' }
    if ($RemoveNode) { $selected+='OpenJS.NodeJS.LTS' }
    if ($RemoveCode) { $selected+='Microsoft.VisualStudioCode' }
    if ($RemoveTailscale) { $selected+='Tailscale.Tailscale' }
    if ($selected.Count) {
        $python="$root\runtime\Scripts\python.exe"
        if (!(Test-Path $python)) { throw 'Runtime missing. Reinstall Hermes to restore dependency tracking, or uncheck dependency removal.' }
        & $python "$root\source\windows_dependencies.py" remove @selected
        if ($LASTEXITCODE -ne 0) { throw 'Dependency removal did not finish. See the log; retry or uncheck that dependency.' }
    }

    # Save this before removing the venv; Python cannot uninstall while it is running.
    $removeBase=$false
    $receiptPath="$root\install-state\python.json"
    if ($RemovePython -and (Test-Path $receiptPath)) {
        $receipt=Get-Content -Raw $receiptPath | ConvertFrom-Json
        $expected="$env:LOCALAPPDATA\Programs\HermesPython312\python.exe"
        $installer="$root\bootstrap\python-3.12.10-amd64.exe"
        $dll="$env:LOCALAPPDATA\Programs\HermesPython312\python312.dll"
        if ($receipt.owned -eq $true -and $receipt.path -eq $expected -and (Test-Path $expected) -and (Test-Path $installer) -and (Test-Path $dll)) {
            $signature=Get-AuthenticodeSignature $installer
            $removeBase=((Get-FileHash $expected -Algorithm SHA256).Hash -eq $receipt.sha256) -and
                ((Get-FileHash $dll -Algorithm SHA256).Hash -eq $receipt.dllSha256) -and
                ((Get-FileHash $installer -Algorithm SHA256).Hash -eq $receipt.installerSha256) -and
                ($signature.Status -eq 'Valid') -and ($signature.SignerCertificate.Subject -match 'Python Software Foundation')
        }
        if (!$removeBase) { Write-Output 'Python ownership/version changed or could not be verified; Python was kept.' }
    }
    Remove-HermesTree "$root\runtime"
    if ($removeBase) {
        $p=Start-Process -FilePath $installer -ArgumentList @('/uninstall','/quiet','InstallAllUsers=0') -Wait -PassThru
        if ($p.ExitCode -notin @(0,3010)) { throw "Python removal failed ($($p.ExitCode)). Retry without Python removal or uninstall it in Windows Settings." }
        if (Test-Path $expected) { throw 'Python remains installed; removal could not be confirmed.' }
        Write-Output 'Hermes-installed Python removed.'
    }
    if ($DeleteData) {
        Remove-HermesTree $privateRoot
        Write-Output 'Hermes conversations, keys, settings, caches and backups deleted. Documents outside the Hermes data folder were kept.'
    } else { Write-Output 'Hermes conversations, keys, settings and backups kept.' }
    foreach ($folder in @('source','bootstrap')) { Remove-HermesTree (Join-Path $root $folder) }
    # Retain an ownership audit in the uninstall log before deleting install metadata.
    if (Test-Path "$root\install-state") { Get-ChildItem "$root\install-state" -Filter '*.json' | ForEach-Object { Write-Output $_.Name; Get-Content $_.FullName } }
    Remove-HermesTree "$root\install-state"
    Write-Output 'Hermes cleanup completed. Software without verified ownership was preserved.'
    Stop-Transcript | Out-Null
    exit 0
} catch {
    Write-Output "Uninstall incomplete: $($_.Exception.Message)"
    try { Stop-Transcript | Out-Null } catch {}
    exit 1
}
