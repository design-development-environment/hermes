$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$log = Join-Path $root 'bootstrap.log'
try {
    Start-Transcript -Path $log -Append | Out-Null
    $python = $null
    $candidates = @()
    if (Get-Command py.exe -ErrorAction SilentlyContinue) {
        $candidate = & py.exe -3.12 -c 'import sys; print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0) { $candidates += $candidate }
    }
    foreach ($key in @('HKCU:\Software\Python\PythonCore\3.12\InstallPath','HKLM:\Software\Python\PythonCore\3.12\InstallPath')) {
        if (Test-Path $key) { $candidates += Join-Path (Get-Item $key).GetValue('') 'python.exe' }
    }
    $candidates += "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
    $candidates += "$env:LOCALAPPDATA\Programs\HermesPython312\python.exe"
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            & $candidate -c 'import sys,struct,tkinter,venv; assert sys.version_info[:2]==(3,12) and struct.calcsize(chr(80))==8'
            if ($LASTEXITCODE -eq 0) { $python = $candidate; break }
        }
    }
    if (!$python) {
        $installer = Join-Path $root 'bootstrap\python-3.12.10-amd64.exe'
        $signature = Get-AuthenticodeSignature $installer
        if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Python Software Foundation') {
            throw 'Python installer signature could not be verified.'
        }
        $destination = "$env:LOCALAPPDATA\Programs\HermesPython312"
        # An existing directory or registration must never become Hermes-owned.
        $freshPython = !(Test-Path $destination)
        foreach ($key in @('HKCU:\Software\Python\PythonCore\3.12\InstallPath','HKLM:\Software\Python\PythonCore\3.12\InstallPath')) {
            if (Test-Path $key) { $freshPython = $false }
        }
        $process = Start-Process -FilePath $installer -ArgumentList @('/quiet','InstallAllUsers=0','Include_launcher=0','Include_test=0','PrependPath=0','AssociateFiles=0',"TargetDir=`"$destination`"") -Wait -PassThru
        if ($process.ExitCode -notin @(0,3010)) { throw "Python setup failed: $($process.ExitCode)" }
        $python = Join-Path $destination 'python.exe'
        if ($freshPython -and (Test-Path $python)) {
            New-Item -ItemType Directory -Force "$root\install-state" | Out-Null
            @{
                owned = $true
                path = $python
                sha256 = (Get-FileHash $python -Algorithm SHA256).Hash
                dllSha256 = (Get-FileHash "$destination\python312.dll" -Algorithm SHA256).Hash
                installerSha256 = (Get-FileHash $installer -Algorithm SHA256).Hash
            } | ConvertTo-Json | Set-Content -Encoding UTF8 "$root\install-state\python.json"
        }
    }
    if (!(Test-Path "$root\runtime\Scripts\python.exe")) {
        & $python -m venv "$root\runtime"
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the private Hermes environment.' }
    }
    $runtime = "$root\runtime\Scripts\python.exe"
    & $runtime -m pip install --no-cache-dir --no-index --find-links "$root\bootstrap" Pillow==12.0.0
    if ($LASTEXITCODE -ne 0) { throw 'Could not install the setup graphics library.' }
    if (Test-Path "$root\runtime\Scripts\open-webui.exe") {
        & $runtime "$root\source\windows_runtime.py" upgrade
        if ($LASTEXITCODE -ne 0) { throw 'Could not upgrade the existing Hermes runtime.' }
        Stop-Transcript | Out-Null
        exit 0
    }
    Start-Process -FilePath "$root\runtime\Scripts\pythonw.exe" -ArgumentList @("`"$root\source\windows_setup.py`"") -WorkingDirectory "$root\source"
    Stop-Transcript | Out-Null
    exit 0
} catch {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show("Setup could not finish: $($_.Exception.Message)`n`nDetails: $log",'Hermes setup') | Out-Null
    exit 1
}
