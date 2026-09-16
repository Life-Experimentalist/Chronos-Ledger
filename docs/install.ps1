# Copyright 2026 Chronos Ledger Contributors
# SPDX-License-Identifier: Apache-2.0
#
# Install the chronos CLI on Windows.
#
#   irm https://chronos.vkrishna04.me/install.ps1 | iex
#   & ([scriptblock]::Create((irm https://chronos.vkrishna04.me/install.ps1))) -Version 0.13.0
#
# Puts chronos.exe in %LOCALAPPDATA%\chronos\bin (or $env:CHRONOS_INSTALL_DIR\bin),
# checks it against the release's .sha256 file, adds the directory to your user
# PATH and records that in install.json, so `chronos self uninstall` removes
# exactly that entry.
#
# It never touches a chronos installed any other way (Scoop, a copied file). If
# it finds one, it says where.

param(
    [string]$Version = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Repo = "https://github.com/Life-Experimentalist/Chronos-Ledger"

function Fail([string]$Message) {
    Write-Host "install.ps1: $Message" -ForegroundColor Red
    throw $Message
}

$arch = switch ($env:PROCESSOR_ARCHITECTURE) {
    "AMD64" { "x64" }
    "ARM64" { "arm64" }
    default { Fail "no chronos binary for $($env:PROCESSOR_ARCHITECTURE)" }
}

if (-not $Version) {
    # The redirect releases/latest answers with names the tag, and costs none of
    # the unauthenticated API rate limit.
    $request = [Net.HttpWebRequest]::Create("$Repo/releases/latest")
    $request.AllowAutoRedirect = $false
    $request.UserAgent = "chronos-install"
    try {
        $response = $request.GetResponse()
        $location = $response.Headers["Location"]
        $response.Close()
    } catch {
        Fail "could not reach GitHub to find the latest release"
    }
    if (-not $location -or $location -notmatch "/releases/tag/([^/]+)$") {
        Fail "could not find the latest release on GitHub"
    }
    $Version = $Matches[1]
}
$Version = $Version.TrimStart("v")

$Root = if ($env:CHRONOS_INSTALL_DIR) { $env:CHRONOS_INSTALL_DIR } else { Join-Path $env:LOCALAPPDATA "chronos" }
$BinDir = Join-Path $Root "bin"
$Target = Join-Path $BinDir "chronos.exe"

if (-not $Force -and (Test-Path $Target)) {
    $current = (& $Target --version 2>$null) -replace "^chronos\s+", ""
    if ($current -eq $Version) {
        Write-Host "chronos $Version is already installed at $Target. Pass -Force to reinstall."
        return
    }
}

$Asset = "chronos-v$Version-windows-$arch.exe"
$Url = "$Repo/releases/download/v$Version/$Asset"
$Tmp = Join-Path ([IO.Path]::GetTempPath()) ("chronos-" + [Guid]::NewGuid())
New-Item -ItemType Directory -Path $Tmp | Out-Null
try {
    try {
        $sum = (Invoke-WebRequest -UseBasicParsing "$Url.sha256").Content
        if ($sum -is [byte[]]) { $sum = [Text.Encoding]::ASCII.GetString($sum) }
    } catch {
        Fail "release v$Version has no $Asset. Binaries upload a few minutes after a release is published, so try again shortly. Releases before 0.13.0 have no CLI."
    }
    $expected = ($sum.Trim() -split "\s+")[0].ToLowerInvariant()
    if ($expected -notmatch "^[0-9a-f]{64}$") { Fail "the checksum file for $Asset is not a SHA-256 digest" }

    Write-Host "Downloading $Asset"
    $download = Join-Path $Tmp "chronos.exe"
    Invoke-WebRequest -UseBasicParsing $Url -OutFile $download
    $actual = (Get-FileHash -Algorithm SHA256 $download).Hash.ToLowerInvariant()
    if ($actual -ne $expected) {
        Fail "checksum mismatch for $Asset (expected $expected, got $actual). Nothing was installed."
    }
    # Downloaded files carry the Mark of the Web, which makes SmartScreen stop
    # every run. The checksum above is what establishes trust here.
    Unblock-File $download

    New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
    if (Test-Path $Target) {
        # A running chronos.exe cannot be overwritten but can be renamed. The
        # CLI deletes the .old file the next time it starts.
        $aside = "$Target.old"
        Remove-Item -Force $aside -ErrorAction SilentlyContinue
        Move-Item -Force $Target $aside
    }
    Move-Item -Force $download $Target
} finally {
    Remove-Item -Recurse -Force $Tmp -ErrorAction SilentlyContinue
}

# PATH: the user variable in the registry, read raw so %VARIABLES% in it survive.
$envKey = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey("Environment", $true)
$userPath = [string]$envKey.GetValue("Path", "", [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
$machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$norm = { param($p) $p.TrimEnd("\").ToLowerInvariant() }
$inUser = @($userPath -split ";" | Where-Object { (& $norm $_) -eq (& $norm $BinDir) }).Count -gt 0
$inMachine = @($machinePath -split ";" | Where-Object { (& $norm $_) -eq (& $norm $BinDir) }).Count -gt 0

$pathEntry = $null
if ($inUser) {
    $pathEntry = [ordered]@{ kind = "user-path"; entry = $BinDir }
} elseif (-not $inMachine) {
    $newPath = if ($userPath) { $userPath.TrimEnd(";") + ";" + $BinDir } else { $BinDir }
    $envKey.SetValue("Path", $newPath, [Microsoft.Win32.RegistryValueKind]::ExpandString)
    $env:Path = "$env:Path;$BinDir"
    $pathEntry = [ordered]@{ kind = "user-path"; entry = $BinDir }
    Write-Host "Added $BinDir to your user PATH. Open a new terminal to use chronos everywhere."
}
$envKey.Close()

$receipt = [ordered]@{
    schema       = 1
    version      = $Version
    channel      = "installer"
    installed_at = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    path_entry   = $pathEntry
}
# UTF-8 without a BOM: serde_json rejects a BOM.
[IO.File]::WriteAllText((Join-Path $Root "install.json"), ($receipt | ConvertTo-Json -Depth 3), (New-Object Text.UTF8Encoding $false))

Write-Host "Installed chronos $Version to $Target"

# Other copies are reported, never removed: each belongs to whatever installed it.
$targetFull = (Resolve-Path $Target).Path
foreach ($copy in Get-Command chronos.exe -All -CommandType Application -ErrorAction SilentlyContinue) {
    if ($copy.Source -ne $targetFull) {
        Write-Warning "another chronos is on PATH at $($copy.Source). Remove it with the tool that installed it (scoop uninstall chronos, or delete it if you copied it there)."
    }
}
