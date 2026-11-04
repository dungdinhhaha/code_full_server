$ErrorActionPreference = 'Stop'

$projectDir = $PSScriptRoot
$arduinoCli = Join-Path $env:LOCALAPPDATA 'Programs\arduino-cli\arduino-cli.exe'
if (!(Test-Path -LiteralPath $arduinoCli)) {
    throw "Arduino CLI not found at $arduinoCli"
}

# Arduino CLI requires the primary .ino filename to match its containing
# folder. Keep sketch.ino as the Wokwi web editor entry point, and compile a
# fresh copy named smiot_demo.ino from the same source.
$compileDir = Join-Path $env:TEMP 'smiot_wokwi_cli_build\smiot_demo'
$firmwareDir = Join-Path $projectDir 'build'
New-Item -ItemType Directory -Force -Path $compileDir, $firmwareDir | Out-Null
Copy-Item -LiteralPath (Join-Path $projectDir 'sketch.ino') -Destination (Join-Path $compileDir 'smiot_demo.ino') -Force

& $arduinoCli compile `
    --fqbn esp32:esp32:esp32 `
    --output-dir $firmwareDir `
    --export-binaries `
    $compileDir
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$required = @('smiot_demo.ino.bin', 'smiot_demo.ino.elf')
foreach ($file in $required) {
    if (!(Test-Path -LiteralPath (Join-Path $firmwareDir $file))) {
        throw "Expected firmware output was not created: $file"
    }
}

Write-Output "Firmware compiled for Wokwi CLI: $firmwareDir"
