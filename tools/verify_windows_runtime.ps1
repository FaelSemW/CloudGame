param([string]$ClientDir = "$PSScriptRoot\..\build\native-client")
$ErrorActionPreference = 'Stop'
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$instances = @(& $vswhere -all -products '*' -format json | ConvertFrom-Json)
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect Visual Studio installations' }
$releaseInstances = @($instances | Where-Object { !$_.isPrerelease -and $_.isComplete })
if (!$releaseInstances.Count) { throw 'No complete release Visual Studio toolchain found' }
$libraries = @(Get-ChildItem -LiteralPath $ClientDir -File | Where-Object {
    $_.Name -match '^(msvcp\d+.*|vcruntime\d+.*|concrt\d+|vccorlib\d+)\.dll$'
})
if (!$libraries.Count) { throw 'Expected Microsoft runtime libraries are missing' }
$records = foreach ($library in $libraries) {
    $digest = (Get-FileHash -LiteralPath $library.FullName -Algorithm SHA256).Hash
    $match = $null
    foreach ($instance in $releaseInstances) {
        $redist = Join-Path $instance.installationPath 'VC\Redist'
        if (!(Test-Path -LiteralPath $redist)) { continue }
        foreach ($candidate in Get-ChildItem -LiteralPath $redist -Filter $library.Name -File -Recurse) {
            if ($candidate.FullName -match 'debug_nonredist') { continue }
            if ((Get-FileHash -LiteralPath $candidate.FullName -Algorithm SHA256).Hash -eq $digest) {
                $match = [ordered]@{
                    file = $library.Name; sha256 = $digest.ToLowerInvariant()
                    version = $library.VersionInfo.FileVersion
                    toolchain = $instance.installationVersion
                    source = $candidate.FullName.Substring($instance.installationPath.Length + 1)
                    preview = $false
                }
                break
            }
        }
        if ($match) { break }
    }
    if (!$match) { throw "Runtime does not match an unmodified release VC/Redist file: $($library.Name)" }
    $match
}
$output = "$PSScriptRoot\..\build\windows-smoke"
New-Item -ItemType Directory -Force -Path $output | Out-Null
@($records) | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath "$output\runtime-provenance.json" -Encoding utf8
Write-Host "Verified $($libraries.Count) Microsoft runtime DLLs against release VC/Redist."
