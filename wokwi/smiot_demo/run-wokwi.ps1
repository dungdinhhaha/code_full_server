param(
    [string]$TokenFile
)

$ErrorActionPreference = 'Stop'

$projectDir = $PSScriptRoot
$cli = Join-Path $HOME '.wokwi\bin\wokwi-cli.exe'
$firmware = Join-Path $projectDir 'build\smiot_demo.ino.bin'

if (-not (Test-Path -LiteralPath $cli)) {
    throw "Wokwi CLI not found at $cli. Install it from https://docs.wokwi.com/wokwi-ci/cli-installation"
}

if (-not (Test-Path -LiteralPath $firmware)) {
    & (Join-Path $projectDir 'build-firmware.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'ESP32 firmware compilation failed.' }
}

$tokenPointer = $null
$tokenContent = $null
if ($TokenFile) {
    $tokenContent = Get-Content -LiteralPath $TokenFile -Raw
    if ($tokenContent -notmatch '(?im)^\s*(?:\$env:)?WOKWI_CLI_TOKEN\s*=\s*(.+?)\s*$') {
        throw 'Token file must contain a WOKWI_CLI_TOKEN assignment.'
    }
    $token = $Matches[1].Trim().Trim('"').Trim("'")
    if ($token -notmatch '^wok_[A-Za-z0-9_-]{40}$') {
        throw 'Token in file does not match the expected Wokwi CI token format.'
    }
}
else {
    $secureToken = Read-Host 'Enter your Wokwi CI token (input is hidden)' -AsSecureString
    $tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
    $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPointer)
}

$previousToken = $env:WOKWI_CLI_TOKEN
$exitCode = 1

try {
    $env:WOKWI_CLI_TOKEN = $token
    & $cli $projectDir --timeout 0
    $exitCode = $LASTEXITCODE
}
finally {
    if ($null -eq $previousToken) {
        Remove-Item Env:WOKWI_CLI_TOKEN -ErrorAction SilentlyContinue
    }
    else {
        $env:WOKWI_CLI_TOKEN = $previousToken
    }
    if ($null -ne $tokenPointer) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPointer)
    }
    $token = $null
    $tokenContent = $null
}

exit $exitCode
