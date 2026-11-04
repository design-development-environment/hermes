$ErrorActionPreference='Stop'
$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile("$PSScriptRoot/uninstall.ps1",[ref]$tokens,[ref]$errors)
if ($errors.Count) { throw 'Uninstall script did not parse' }
$function=$ast.Find({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Remove-HermesTree'},$true)
# Load only the deletion helper; never execute the Windows uninstall entry point.
Invoke-Expression $function.Extent.Text
$temporary=Join-Path ([IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString())
try {
    New-Item -ItemType Directory "$temporary/owned/nested" -Force | Out-Null
    Set-Content "$temporary/owned/nested/file.txt" 'test'
    Remove-HermesTree "$temporary/owned"
    if (Test-Path "$temporary/owned") { throw 'Owned folder remained' }
    New-Item -ItemType Directory "$temporary/outside","$temporary/owned" -Force | Out-Null
    Set-Content "$temporary/outside/keep.txt" 'preserve'
    New-Item -ItemType SymbolicLink -Path "$temporary/owned/link" -Target "$temporary/outside" | Out-Null
    $refused=$false
    try { Remove-HermesTree "$temporary/owned" } catch { $refused=$true }
    if (!$refused -or !(Test-Path "$temporary/outside/keep.txt")) { throw 'Linked folder protection failed' }
    Write-Output 'Cleanup tests passed: owned tree removal and linked-folder refusal.'
} finally {
    if (Test-Path "$temporary/owned/link") { Remove-Item -LiteralPath "$temporary/owned/link" -Force }
    Remove-Item -LiteralPath $temporary -Force -Recurse
}
