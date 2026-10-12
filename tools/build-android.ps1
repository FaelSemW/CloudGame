param([ValidateSet('assembleNonRootDebug', 'assembleNonRootRelease')][string]$Task = 'assembleNonRootDebug')
$ErrorActionPreference = 'Stop'
$workspace = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$jdk = Get-ChildItem -LiteralPath (Join-Path $workspace '.toolchains') -Directory -Filter 'jdk-*' | Select-Object -First 1
if (-not $jdk) { throw 'JDK local ausente em .toolchains.' }
if (-not (Test-Path -LiteralPath (Join-Path $workspace '.toolchains/android-sdk/ndk/29.0.14206865/source.properties'))) { throw 'Instale o Android SDK/NDK antes de compilar.' }
$mappedDrive = $null
try {
    $buildRoot = $workspace
    if ($workspace.Contains(' ')) {
        foreach ($letter in @('Z','Y','X','W','V')) {
            if (-not (Test-Path "$($letter):\") -and -not (Get-PSDrive -Name $letter -ErrorAction SilentlyContinue)) {
                & subst "$($letter):" $workspace
                if ($LASTEXITCODE -ne 0) { throw 'Não foi possível criar um alias temporário sem espaços.' }
                $mappedDrive = "$($letter):"
                $buildRoot = "$($letter):\"
                break
            }
        }
        if (-not $mappedDrive) { throw 'Nenhuma letra livre para o alias temporário exigido pelo NDK.' }
    }
    $env:JAVA_HOME = Join-Path $buildRoot ".toolchains/$($jdk.Name)"
    $env:ANDROID_HOME = Join-Path $buildRoot '.toolchains/android-sdk'
    $env:GRADLE_USER_HOME = Join-Path $buildRoot '.toolchains/gradle'
    $project = Join-Path $buildRoot 'third_party/moonlight-android'
    & (Join-Path $project 'gradlew.bat') -p $project $Task --no-daemon --max-workers=2 '-Dorg.gradle.jvmargs=-Xmx1536m' --console=plain
    if ($LASTEXITCODE -ne 0) { throw 'A compilação Android falhou; consulte a saída acima.' }
} finally {
    if ($mappedDrive) { & subst $mappedDrive /d }
}
