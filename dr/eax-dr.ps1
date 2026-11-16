<#
.SYNOPSIS
  eax-dr: builds a whole EA Explorer environment from an infrastructure backup (disaster recovery). R5.6-B2.

.DESCRIPTION
  The owner, 16 Nov 2026, 20:27: "build me another command which builds an enviornment from a backup. We give it 1. a
  backup folder 2. an install folder 3. a version 4. It downloads the code from github 5. Builds the entire
  enviornment. Like a DR script, call it eax-dr"; 20:28: "This eax-dr and drill should also need a copy of the env file".

  Run it on the machine that is to hold EA Explorer, with Docker running; it needs nothing of an old installation and
  asks nothing. One step after another, stopping at the first that fails and saying why:
    1. checks, nothing touched yet: the backup is whole (its manifest says good, every file matches SHA256SUMS), the env
       file is readable, the install folder is new or empty, Docker answers, the version is published on the
       repository's GitHub Releases page (never the main branch)
    2. the code of that release from GitHub, into the install folder (git, or the release's zip when git is missing)
    3. the env file put in place as work/eaexplorer.env, the work folders made, the backup copied into
       work/backups/infrastructure
    4. EA Explorer built and started (eax up --wait-all)
    5. the maintenance page on and the background paused, then the full restore of the backup (every database, the
       documents, the certificate, the reports' home, the import and export folders, persist/ and the config), and
       EA Explorer started again
    6. the background back and the maintenance page off, then the smoke test
  A report and the whole log go to <install>/work/dr/dr-<time>/.

  With -Pack (a folder eax dr-pack made, R5.6-B2, owner 22:12): the backup, the version and the env file come from the
  pack; every file of the pack is checked against PACK.sha256 first; after the restore the fingerprint of every table
  and file is compared with the pack's fingerprint.json, so it is proven that everything came back.

.EXAMPLE
  .\eax-dr.ps1 -Pack D:\ea-dr-pack-2026-11-16 -Install C:\EA-Explorer

.EXAMPLE
  .\eax-dr.ps1 -Backup D:\safe\20261116T152253Z-nightly -Install C:\EA-Explorer -Version 5.6.0 -Env D:\safe\eaexplorer.env
  -Project <name>: its own Docker name (containers and volumes), to keep it apart from an installation on the same machine
#>
param(
    [string]$Pack = "",                # a DR pack (eax dr-pack): the backup, version and env file from it, checked
    [string]$Backup = "",
    [Parameter(Mandatory = $true)][string]$Install,
    [string]$Version = "",
    [Alias("Env")][string]$EnvFile = "",
    [string]$Repo = "",
    [string]$Project = "eaexplorer",   # its Docker name: another one keeps a copy apart from an installation on this machine
    [switch]$KeepQuiet,          # eax-drill: the background stays paused after the restore, for its own comparison
    [switch]$NoSmoke             # eax-drill: it runs the smoke test itself
)
$ErrorActionPreference = "Stop"
$Fingerprint = ""
$EnvGiven = [bool]$EnvFile      # an env file given beside a pack (a new machine's name): the pack's own is not checked
if ($Pack) {
    $Pack = [IO.Path]::GetFullPath($Pack).TrimEnd('\', '/')
    $inPack = @(Get-ChildItem -Directory (Join-Path $Pack "backup") -ErrorAction SilentlyContinue)
    if ($inPack.Count -ne 1) { Write-Host "$Pack is not a DR pack (it needs one backup in backup\)" -ForegroundColor Red; exit 2 }
    if (-not $Backup) { $Backup = $inPack[0].FullName }
    if (-not $EnvFile) { $EnvFile = Join-Path $Pack "eaexplorer.env" }
    if (-not $Version -and (Test-Path (Join-Path $Pack "VERSION.txt"))) { $Version = (Get-Content (Join-Path $Pack "VERSION.txt") -TotalCount 1).Trim() }
    if (Test-Path (Join-Path $Pack "fingerprint.json")) { $Fingerprint = Join-Path $Pack "fingerprint.json" }
}
if (-not $Backup -or -not $Version -or -not $EnvFile) {
    Write-Host "Give -Pack <DR pack>, or -Backup, -Version and -Env." -ForegroundColor Red; exit 2 }
$Backup = [IO.Path]::GetFullPath($Backup).TrimEnd('\', '/')
$Install = [IO.Path]::GetFullPath($Install).TrimEnd('\', '/')
$EnvFile = [IO.Path]::GetFullPath($EnvFile)
$Version = $Version.TrimStart("v")
$Started = Get-Date
$Lines = New-Object System.Collections.Generic.List[string]
$Results = New-Object System.Collections.Generic.List[object]

. (Join-Path $PSScriptRoot "dr-common.ps1")    # Say, Step, Eax, Sha, Test-BackupWhole, Get-Release

$exit = 1
try {
    Say "EA Explorer DR: builds $Install from the backup $Backup, version $Version. Nothing is asked." "Yellow"
    $manifest = $null
    $vals = @{}
    $gh = $null
    if ($Pack) {
        Step "the DR pack is whole (every file against PACK.sha256)" {
            $sums = Join-Path $Pack "PACK.sha256"
            if (-not (Test-Path $sums)) { throw "$Pack has no PACK.sha256: make the pack with eax dr-pack" }
            $n = 0
            foreach ($line in Get-Content $sums) {
                if ($line -notmatch '^([0-9a-f]{64})  (.+)$') { continue }
                if ($EnvGiven -and $Matches[2] -eq "eaexplorer.env") { continue }
                $p = Join-Path $Pack ($Matches[2] -replace '/', '\')
                if (-not (Test-Path -LiteralPath $p)) { throw "$($Matches[2]) is missing from the pack" }
                if ((Sha $p) -ne $Matches[1]) { throw "$($Matches[2]) in the pack does not match its checksum" }
                $n++
            }
            "$n files, each matching its checksum" }
    }
    Step "checks (nothing touched yet)" {
        if (-not (Test-Path -LiteralPath (Join-Path $Backup "manifest.json"))) { throw "$Backup is not an infrastructure backup (no manifest.json)" }
        $script:manifest = Get-Content -Raw (Join-Path $Backup "manifest.json") | ConvertFrom-Json
        if ($manifest.status -and $manifest.status -ne "ok") { throw "the backup's manifest says $($manifest.status): $($manifest.error)" }
        $n = Test-BackupWhole $Backup
        if ($manifest.version -and [version]($manifest.version -replace '-.*$', '') -gt [version]($Version -replace '-.*$', '')) {
            throw "the backup is of version $($manifest.version), newer than ${Version}: restore it with $($manifest.version) or newer"
        }
        if (-not (Test-Path -LiteralPath $EnvFile)) { throw "the env file $EnvFile is not there" }
        foreach ($l in Get-Content $EnvFile) { if ($l -match '^\s*([A-Z0-9_]+)\s*=\s*(.*)$') { $script:vals[$Matches[1]] = $Matches[2].Trim("'`"") } }
        if (-not $vals["EAX_DEPLOYMENT"] -and -not $vals["EAX_HOSTNAME"]) { throw "$EnvFile does not read as EA Explorer's env file (no EAX_DEPLOYMENT, no EAX_HOSTNAME)" }
        if ((Test-Path $Install) -and (Get-ChildItem -Force $Install | Select-Object -First 1)) { throw "$Install is not empty: give a new or empty folder" }
        if ($Backup.StartsWith($Install + "\", [StringComparison]::OrdinalIgnoreCase)) { throw "the backup may not be inside the install folder" }
        & docker info --format "{{.ServerVersion}}" *> $null
        if ($LASTEXITCODE -ne 0) { throw "Docker does not answer: start Docker Desktop" }
        if ($Project -notmatch '^[a-z0-9][a-z0-9_-]*$') { throw "-Project is lower-case letters, digits, - and _" }
        $mine = @(& docker ps -aq --filter "label=com.docker.compose.project=$Project")
        if ($mine.Count -gt 0) { throw "Docker already has $($mine.Count) container(s) named $Project (another installation): give another -Project" }
        if (-not $script:Repo) { $script:Repo = if ($vals["EAX_UPDATE_GIT_URL"]) { $vals["EAX_UPDATE_GIT_URL"] } else { "https://github.com/gauravvermaea/EA-Explorer" } }
        $script:gh = Get-Release $Repo $Version
        "backup $(Split-Path $Backup -Leaf) whole ($n files, version $($manifest.version)); v$Version published on $Repo"
    }
    $name = Split-Path $Backup -Leaf
    Step "the code of v$Version from GitHub" {
        New-Item -ItemType Directory -Force (Split-Path $Install) | Out-Null
        if (Get-Command git -ErrorAction SilentlyContinue) {
            & git -c advice.detachedHead=false clone --quiet --depth 1 --branch "v$Version" $Repo $Install 2>&1 | ForEach-Object { Say "    $_" }
            if ($LASTEXITCODE -ne 0) { throw "git clone of v$Version failed" }
        } else {
            $zip = Join-Path ([IO.Path]::GetTempPath()) "eax-v$Version.zip"
            Invoke-WebRequest -UseBasicParsing "https://github.com/$($gh.owner)/$($gh.repo)/archive/refs/tags/v$Version.zip" -OutFile $zip
            $tmp = Join-Path ([IO.Path]::GetTempPath()) "eax-v$Version"
            if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
            Expand-Archive $zip $tmp
            $top = Get-ChildItem $tmp | Select-Object -First 1
            New-Item -ItemType Directory -Force $Install | Out-Null
            Get-ChildItem -Force $top.FullName | Move-Item -Destination $Install
            Remove-Item -Recurse -Force $tmp, $zip
        }
        $have = (Select-String -Path (Join-Path $Install "services\api\version.toml") -Pattern '^version\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
        if ($have -ne $Version) { throw "the code says version $have, not $Version" }
        "version $have"
    }
    Step "the env file, the work folders and the backup in place" {
        foreach ($d in "work/logs", "work/backups/infrastructure", "work/proxy", "work/data/imports", "work/data/exports", "work/data/tls") {
            New-Item -ItemType Directory -Force (Join-Path $Install $d) | Out-Null
        }
        Copy-Item -LiteralPath $EnvFile (Join-Path $Install "work\eaexplorer.env") -Force
        if ($Project -ne "eaexplorer") { Set-Content -Encoding ASCII (Join-Path $Install "work\compose-project") $Project }
        $dest = Join-Path $Install "work\backups\infrastructure\$name"
        Copy-Item -LiteralPath $Backup $dest -Recurse -Force
        $n = Test-BackupWhole $dest
        "the env file as work\eaexplorer.env; the backup copied whole ($n files)"
    }
    Step "EA Explorer built and started" { Eax @("up", "--wait-all") | Out-Null; "every container up" }
    $t1 = Get-Date
    Step "the maintenance page on and the background paused" { Eax @("drill", "quiet", "on") | Out-Null }
    Step "the full restore of $name" { $r = Eax @("drill", "restore", $name); "took $($r.seconds) s; EA Explorer answers" }
    Step "EA Explorer started again" { Eax @("up", "--wait-all") | Out-Null; "every container up" }
    if ($Fingerprint) {
        Step "every table and file compared with the pack's fingerprint" {
            $after = Join-Path $Install "work\dr\fingerprint-after.json"
            New-Item -ItemType Directory -Force (Split-Path $after) | Out-Null
            Eax @("drill", "fingerprint", $after) | Out-Null
            $c = Eax @("drill", "compare", $Fingerprint, $after)
            "$($c.tables) tables and $($c.files) files the same as when the pack was made$(if (@($c.not_compared).Count) { "; $(@($c.not_compared).Count) the installation writes by itself not compared" })" }
    }
    $script:Recovery = [int]((Get-Date) - $t1).TotalMinutes
    if (-not $KeepQuiet) { Step "the background back and the maintenance page off" { Eax @("drill", "quiet", "off") | Out-Null } }
    if (-not $NoSmoke) { Step "the smoke test" { Eax @("test", "smoke") | Out-Null; "passed" } }
    $exit = 0
} catch {
    $exit = 1
} finally {
    $mins = [int]((Get-Date) - $Started).TotalMinutes
    $ok = $exit -eq 0
    Say ("`nEA Explorer DR " + $(if ($ok) { "DONE" } else { "FAILED" }) + " in $mins minutes.") $(if ($ok) { "Green" } else { "Red" })
    $folder = if (Test-Path (Join-Path $Install "work")) { Join-Path $Install ("work\dr\dr-" + $Started.ToUniversalTime().ToString("yyyyMMddTHHmmssZ")) } else { Join-Path ([IO.Path]::GetTempPath()) ("eax-dr-" + $Started.ToUniversalTime().ToString("yyyyMMddTHHmmssZ")) }
    New-Item -ItemType Directory -Force $folder | Out-Null
    $md = @("# EA Explorer DR, $($Started.ToString('yyyy-MM-dd HH:mm'))", "",
            "**$(if ($ok) { 'Done' } else { 'Failed' })** in $mins minutes. Backup ``$Backup``, install ``$Install``, version $Version.", "")
    if ($script:Recovery) { $md += "Recovery time (from the restore's start to EA Explorer up again): $($script:Recovery) minutes.", "" }
    $md += "| | Step | Seconds | Detail |", "| --- | --- | --- | --- |"
    foreach ($r in $Results) { $md += "| $(if ($r.ok) { 'ok' } else { 'FAILED' }) | $($r.step) | $($r.seconds) | $(($r.detail -replace '\|', '/'))  |" }
    Set-Content -Encoding UTF8 (Join-Path $folder "report.md") $md
    Set-Content -Encoding UTF8 (Join-Path $folder "dr.log") $Lines
    Say "Report: $folder\report.md"
}
exit $exit
