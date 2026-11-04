# Builds the static libraries the Visual Studio project links from
# lib\windows64, for x64 with the static C runtime (/MT), from pinned sources:
#   OpenSSL  -> libssl.lib, libcrypto.lib
#   libetpan (upstream build-windows project) -> libetpan.lib, headers in include\windows\libetpan
# libetpan is built without Cyrus SASL (no maintained Windows build of it):
# LOGIN, PLAIN and XOAUTH2 work; CRAM-MD5, DIGEST-MD5, NTLM, GSSAPI... don't.
# It is built without zlib too, which only IMAP COMPRESS uses.
#
# usage: scripts\build-windows-deps.ps1 [output-dir]   (default: lib\windows64)
# WORK (default build\deps-win) holds the sources and builds; a rerun reuses them.
# Needs: git, Visual Studio 2022 (C++ workload), Strawberry Perl (or another
# native Windows perl; the MSYS perl that comes with Git can't build OpenSSL).

param([string]$Out = "")

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not $Out) { $Out = Join-Path $Root "lib\windows64" }
$Work = if ($env:WORK) { $env:WORK } else { Join-Path $Root "build\deps-win" }

$OPENSSL_TAG  = "openssl-3.5.9"                               # 3.5 LTS, 2026-09-29
$LIBETPAN_SHA = "e02145e4fb755eae44b3acfdc8067b05bf7904ef"   # libetpan 1.10.1

function Invoke-Native {
  param([string]$Exe, [string[]]$Arguments)
  & $Exe @Arguments
  if ($LASTEXITCODE -ne 0) { throw "$Exe $($Arguments -join ' ') failed ($LASTEXITCODE)" }
}

# fetch <repo url> <ref> <dir>; skips only a completed checkout
function Get-Source {
  param([string]$Url, [string]$Ref, [string]$Dir)
  if (Test-Path (Join-Path $Dir ".git")) {
    & git -C $Dir rev-parse -q --verify HEAD *> $null
    if ($LASTEXITCODE -eq 0) { return }
  }
  New-Item -ItemType Directory -Force -Path $Dir | Out-Null
  Invoke-Native git @("-C", $Dir, "init", "-q")
  for ($i = 1; $i -le 3; $i++) {
    & git -C $Dir fetch -q --depth 1 $Url $Ref
    if ($LASTEXITCODE -eq 0) { break }
    if ($i -eq 3) { throw "fetch $Url failed" }
    Write-Host "fetch $Url failed, retrying"; Start-Sleep -Seconds 10
  }
  Invoke-Native git @("-C", $Dir, "checkout", "-q", "FETCH_HEAD")
}

# the x64 compiler environment (cl, nmake, lib), unless already set up
if (-not (Get-Command cl.exe -ErrorAction SilentlyContinue)) {
  $vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
  $vs = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
  if (-not $vs) { throw "Visual Studio with the C++ tools not found" }
  $here = Get-Location
  & (Join-Path $vs "Common7\Tools\Launch-VsDevShell.ps1") -Arch amd64 -HostArch amd64 -SkipAutomaticLocation | Out-Null
  Set-Location $here
}

$Perl = "C:\Strawberry\perl\bin\perl.exe"
if (-not (Test-Path $Perl)) { $Perl = (Get-Command perl.exe).Source }

$SrcOpenssl = Join-Path $Work "openssl"
$Libetpan   = Join-Path $Work "libetpan"
$Prefix     = Join-Path $Work "openssl-install"
Get-Source "https://github.com/openssl/openssl.git" "refs/tags/$OPENSSL_TAG" $SrcOpenssl
Get-Source "https://github.com/dinhvh/libetpan.git" $LIBETPAN_SHA $Libetpan

# OpenSSL: static (no-shared also selects the static runtime /MT), no assembler
# (no NASM needed; SMTP doesn't need the speed), no config file read from disk
if (-not (Test-Path (Join-Path $Prefix "lib\libcrypto.lib"))) {
  Push-Location $SrcOpenssl
  try {
    Invoke-Native $Perl @("Configure", "VC-WIN64A", "no-shared", "no-asm", "no-tests", "no-docs", "no-apps",
      "--prefix=$Prefix", "--openssldir=$Prefix\ssl")
    Invoke-Native nmake @("/nologo")
    Invoke-Native nmake @("/nologo", "install_sw")
  } finally { Pop-Location }
}

# libetpan: the upstream project builds a DLL against prebuilt third-party
# binaries; turn it into a static library with the static runtime, without SASL or zlib
$BuildWin = Join-Path $Libetpan "build-windows"
$Vcxproj  = Join-Path $BuildWin "libetpan\libetpan.vcxproj"
$Config   = Join-Path $BuildWin "libetpan-config.h"

$p = Get-Content -Raw $Vcxproj
$p = $p -replace '<ConfigurationType>DynamicLibrary</ConfigurationType>', '<ConfigurationType>StaticLibrary</ConfigurationType>'
$p = $p -replace '<RuntimeLibrary>MultiThreadedDLL</RuntimeLibrary>', '<RuntimeLibrary>MultiThreaded</RuntimeLibrary>'
$p = $p -replace 'HAVE_ZLIB;', ''
$p = $p -replace 'USE_SASL;', ''
$p = $p -replace 'LIBETPAN_DLL;', ''
Set-Content -NoNewline -Path $Vcxproj -Value $p

# without LIBETPAN_DLL the header declares everything __declspec(dllimport)
$c = Get-Content -Raw $Config
$c = $c -replace 'define LIBETPAN_EXPORT __declspec\(dllimport\)', 'define LIBETPAN_EXPORT'
Set-Content -NoNewline -Path $Config -Value $c

$ThirdParty = Join-Path $Libetpan "third-party"
New-Item -ItemType Directory -Force -Path (Join-Path $ThirdParty "include") | Out-Null
Copy-Item -Recurse -Force (Join-Path $Prefix "include\openssl") (Join-Path $ThirdParty "include")

Invoke-Native msbuild @($Vcxproj, "/p:Configuration=Release", "/p:Platform=x64",
  "/p:PlatformToolset=v143", "/p:WindowsTargetPlatformVersion=10.0", "/m", "/v:minimal")

$Lib = Get-ChildItem -Recurse -Path $BuildWin -Filter "libetpan.lib" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $Lib) { throw "libetpan.lib not found under $BuildWin" }

New-Item -ItemType Directory -Force -Path $Out | Out-Null
Copy-Item -Force $Lib.FullName (Join-Path $Out "libetpan.lib")
foreach ($name in @("libssl.lib", "libcrypto.lib")) {
  Copy-Item -Force (Join-Path $Prefix "lib\$name") (Join-Path $Out $name)
}

# headers (libetpan-config.h is generated per platform, so mac and windows differ)
$Headers = Join-Path $Root "include\windows"
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $Headers "libetpan")
New-Item -ItemType Directory -Force -Path $Headers | Out-Null
Copy-Item -Recurse -Force (Join-Path $BuildWin "include\libetpan") (Join-Path $Headers "libetpan")
if (Select-String -Quiet -Path (Join-Path $Headers "libetpan\libetpan-config.h") -Pattern 'dllimport') {
  throw "include\windows\libetpan\libetpan-config.h still declares dllimport"
}

Get-ChildItem $Out
