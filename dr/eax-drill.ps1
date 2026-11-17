<#
.SYNOPSIS
  eax-drill: the restore drill, automated - an installation backed up and shut down, a copy built with eax-dr in a new
  folder from the installation's own code (no GitHub) and restored there, then tested. R5.6-B2.

.DESCRIPTION
  The owner's design (16 Nov 2026, 21:40): "ea drill takes an install location as an input and a dr location as an
  input and a temp location as an input; check if that install is running or not; if its not running stop; if its
  running create a temp project model etc as needed; make backup ...; then shut down this install; then copy all the
  files to the temp location - backups, env etc; then at dr location download the install from github; setup the
  files; restore; test. This can run from within the current folder but ensure it doesnt override the current running
  folder. Always needs a new folder"; the containers removed, the images kept (21:40); 21:52: "DR gets its own volumes";
  22:44: the code goes with the backup, as in a DR pack, so no GitHub is needed; 17 Nov, 09:03: "For testing auto
  remove and create destination folders. Expect them to be cleaned and deleted".

  Asks nothing. One step after another, stopping at the first that fails:
    Each problem is a failure (the drill stops) or a warning (noted, the drill carries on, the report lists it first):
    too little disk, the installation down, the backup, its checksums, the restore or the data after it are failures; a
    kind of test content not made (then not checked after the restore), a smoke test only slow, a container still
    starting or the background busy are warnings. A failure leaves diagnostics\ beside the report (every container's
    state and its log's last lines). The owner, 17 Nov 2026, 19:05.
    1. checks, nothing touched: the installation is there and running; the DR and temp folders are apart from it and
       hold nothing but an earlier drill's leftovers (a DR copy, drill-* folders); the pre-flight (free disk for the
       backup, its copy and the DR copy; containers and the background); then those leftovers are removed (the
       earlier DR copy from Docker too) and the folders made
    2. the smoke test; a test project, models and content of every kind (as the backup and restore test makes them)
    3. the maintenance page on, the background paused, the fingerprint of every table and file; a full backup
    4. the test content removed from the installation again, the background back, the maintenance page off; the
       installation shut down (its containers removed; its data volumes and images kept)
    5. the backup, the env file and the installation's code (eax drill code) copied into the temp folder and checked
       against their checksums, as a DR pack holds them
    6. eax-dr (this folder): that code into the DR folder (no GitHub), under its own Docker name (eaexplorer-dr, its own
       volumes), the env file and the backup put in place, built, restored
    7. in the DR copy: the fingerprint compared with before (every table and file), the test content found as it was
       made, the background back, the smoke test, the test content removed
  Then, passed or failed, everything is put back: the DR copy removed from Docker (its containers and data) and its
  folder deleted, the temp folder deleted, the installation started again, the drill's backup deleted (kept when it
  failed). The report and the logs stay in the installation: work\tests\drill-<time>\report.md, with the recovery time.

.EXAMPLE
  .\dr\eax-drill.ps1 -Install C:\Users\gaura\Github\EA-Enterpise -Dr C:\EA-DR\drill1 -Temp C:\EA-DR\temp
#>
param(
    [Parameter(Mandatory = $true)][string]$Install,
    [Parameter(Mandatory = $true)][string]$Dr,
    [Parameter(Mandatory = $true)][string]$Temp
)
$ErrorActionPreference = "Stop"
$Install = [IO.Path]::GetFullPath($Install).TrimEnd('\', '/')
$Dr = [IO.Path]::GetFullPath($Dr).TrimEnd('\', '/')
$Temp = [IO.Path]::GetFullPath($Temp).TrimEnd('\', '/')
$Here = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\', '/')
$Original = $Install
$DrProject = "eaexplorer-dr"

function Inside([string]$Path, [string]$Folder) { $Path.StartsWith($Folder + "\", [StringComparison]::OrdinalIgnoreCase) -or $Path -ieq $Folder }

# what the drill may delete by itself: nothing, or only what a drill leaves (a DR copy under its Docker name; drill-*
# and eax-dr-* folders) - never a folder of anything else, however it was given
function Disposable-Dr([string]$Folder) {
    if (-not (Test-Path -LiteralPath $Folder)) { return $true }
    if (-not (Get-ChildItem -Force -LiteralPath $Folder | Select-Object -First 1)) { return $true }
    $cp = Join-Path $Folder "work\compose-project"
    return (Test-Path -LiteralPath $cp) -and ((Get-Content -Encoding UTF8 -LiteralPath $cp -TotalCount 1).Trim() -eq $DrProject)
}
function Disposable-Temp([string]$Folder) {
    if (-not (Test-Path -LiteralPath $Folder)) { return $true }
    foreach ($i in Get-ChildItem -Force -LiteralPath $Folder) {
        if (-not $i.PSIsContainer -or $i.Name -notmatch '^(drill|eax-dr)-\d{8}T\d{6}Z') { return $false } }
    return $true
}

# the smoke test: passed; or failed only on timing (a warning, the drill carries on); or found a fault (a failure)
function Smoke {
    try { Eax @("test", "smoke") | Out-Null; return "passed" }
    catch {
        $why = $_.Exception.Message
        $r = Eax @("drill", "smoke-result")       # fails the step itself when a check found a fault
        return "passed, but $(@($r.warnings).Count) check(s) only slow ($why)"
    }
}

$Started = Get-Date
$Diag = $null
$Lines = New-Object System.Collections.Generic.List[string]
$Results = New-Object System.Collections.Generic.List[object]
. (Join-Path $Here "dr-common.ps1")    # Say, Step, Eax, Sha, Test-BackupWhole, Test-CodeWhole
$Stamp = "drill-" + $Started.ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$Run = Join-Path $Temp $Stamp
$State = Join-Path $Run "content.json"      # the test content's ids and its test accounts' tokens: removed at the end
$exit = 1
$info = $null
$BackupName = ""
$copy = ""
$shutDown = $false
$drStarted = $false       # eax-dr began building the DR copy (it may be half built)
$quietWhere = ""          # the folder whose background is paused, so it is never left paused
$contentWhere = ""        # the folder that still holds the test content
if (-not (Disposable-Temp $Temp)) {
    Write-Host "$Temp holds files other than an earlier drill's: give a new folder (the drill deletes it afterwards)" -ForegroundColor Red
    exit 2 }
$tempMade = $true
try {
    New-Item -ItemType Directory -Force $Run | Out-Null
    Say "EA Explorer restore drill: $Install backed up and shut down; a copy built from its own code in $Dr and restored. Nothing is asked." "Yellow"
    Step "checks (nothing touched yet)" {
        if (-not (Test-Path (Join-Path $Install "eax.ps1")) -or -not (Test-Path (Join-Path $Install "work\eaexplorer.env"))) {
            throw "$Install is not an EA Explorer installation (no eax.ps1 or work\eaexplorer.env)" }
        foreach ($p in @($Dr, $Temp)) {
            if ((Inside $p $Install) -or (Inside $Install $p)) { throw "$p must be a folder of its own, outside $Install" } }
        if ((Inside $Dr $Temp) -or (Inside $Temp $Dr)) { throw "the DR folder and the temp folder must be apart" }
        if (-not (Disposable-Dr $Dr)) { throw "$Dr holds something other than an earlier drill's DR copy: give a new folder (the drill deletes it afterwards)" }
        Invoke-Native { & docker info --format "{{.ServerVersion}}" } | Out-Null
        if ($global:NativeExit -ne 0) { throw "Docker does not answer: start Docker Desktop" }
        $script:info = Eax @("drill", "info")
        if (@($info.shared).Count) { throw ("the config file puts data in this machine's own folders (" + (@($info.shared) -join ", ") +
            "): a DR copy on this machine would use the same folders and its restore would write over the installation's data. Rehearse on another machine with a DR pack instead") }
        Eax @("drill", "running") | Out-Null
        # the pre-flight (19:05): too little disk fails now, in seconds, not half an hour in; a container still starting or
        # the background busy is a warning
        $pf = Eax @("drill", "preflight", $Temp, $Dr)
        "running, version $($info.version); a backup of about $($pf.backup_gb) GB fits" }
    Step "an earlier drill's leftovers removed and the folders made" {
        $r = Eax @("drill", "remove-copy", $DrProject)
        if (Test-Path -LiteralPath $Dr) { Remove-Item -Recurse -Force -LiteralPath $Dr }
        Get-ChildItem -Force -LiteralPath $Temp | Where-Object { $_.Name -ne $Stamp } | Remove-Item -Recurse -Force
        New-Item -ItemType Directory -Force $Dr | Out-Null
        "$($r.containers) container(s), $($r.volumes) volume(s) of an earlier DR copy removed" }
    Step "the smoke test, before" { Smoke }
    Step "a test project, models and content of every kind" {
        $script:contentWhere = $Install     # set first: a step that fails half way may have made some of it
        $c = Eax @("drill", "content", $State); "$($c.made) kinds made and read back" }   # a kind not made: a warning
    Step "the maintenance page on and the background paused" { Eax @("drill", "quiet", "on") | Out-Null; $script:quietWhere = $Install }
    Step "the background finished what it was doing" { $w = Eax @("drill", "idle"); "waited $($w.waited) s" }
    Step "the fingerprint before (every table and file)" {
        $f = Eax @("drill", "fingerprint", (Join-Path $Run "before.json")); "$($f.tables) tables, $($f.files) files" }
    Step "a full infrastructure backup" {
        $b = Eax @("drill", "backup"); $script:BackupName = $b.name
        "$($b.name), $([math]::Round($b.bytes / 1GB, 2)) GB in $($b.seconds) s" }
    Step "the test content removed from the installation" {
        Eax @("drill", "content-remove", $State) | Out-Null; $script:contentWhere = ""; "removed" }
    Step "the background back and the maintenance page off" { Eax @("drill", "quiet", "off") | Out-Null; $script:quietWhere = "" }
    $t0 = Get-Date
    Step "the installation shut down (containers removed; data and images kept)" {
        Eax @("drill", "shutdown") | Out-Null; $script:shutDown = $true; "stopped" }
    Step "the backup, the env file and the code copied into the temp folder and checked" {
        $src = Join-Path $info.backups $BackupName
        $script:copy = Join-Path $Run "backup\$BackupName"
        New-Item -ItemType Directory -Force (Split-Path $copy) | Out-Null
        Copy-Item -LiteralPath $src $copy -Recurse -Force
        Copy-Item -LiteralPath $info.config (Join-Path $Run "eaexplorer.env") -Force
        if ((Sha $info.config) -ne (Sha (Join-Path $Run "eaexplorer.env"))) { throw "the env file's copy does not match" }
        $n = Test-BackupWhole $copy
        Eax @("drill", "code", (Join-Path $Run "code")) | Out-Null
        $c = Test-CodeWhole (Join-Path $Run "code") $info.version
        "$n backup files, the env file and $c code files, each matching its checksum" }
    Step "eax-dr: v$($info.version) from the copied code (no GitHub) into $Dr, built and restored ($DrProject)" {
        $script:drStarted = $true
        & (Get-Process -Id $PID).Path -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Here "eax-dr.ps1") `
            -Backup $copy -Install $Dr -Code (Join-Path $Run "code") -Env (Join-Path $Run "eaexplorer.env") -Project $DrProject -KeepQuiet -NoSmoke
        if ($LASTEXITCODE -ne 0) { throw "eax-dr failed (its report is in $Dr\work\dr)" }
        $script:quietWhere = $Dr; $script:contentWhere = $Dr
        "done" }
    $script:Recovery = [int]((Get-Date) - $t0).TotalMinutes
    $Install = $Dr                     # from here on, eax runs in the DR copy
    Step "the fingerprint after, compared with before (every table and file)" {
        Eax @("drill", "fingerprint", (Join-Path $Run "after.json")) | Out-Null
        $c = Eax @("drill", "compare", (Join-Path $Run "before.json"), (Join-Path $Run "after.json"))
        "$($c.tables) tables and $($c.files) files the same$(if (@($c.not_compared).Count) { "; $(@($c.not_compared).Count) the installation writes by itself not compared" })$(if (@($c.allowed).Count) { "; $(@($c.allowed).Count) rewritten by the installation itself (allowed, in the log)" })" }
    Step "the test content found in the DR copy as it was made" { $c = Eax @("drill", "content-check", $State); "$($c.kinds) kinds, the same" }
    Step "the background back and the maintenance page off" { Eax @("drill", "quiet", "off") | Out-Null; $script:quietWhere = "" }
    Step "the rest of the DR copy up (Reports, Documents, Diagrams)" { Eax @("up", "--wait-all") | Out-Null; "every container up" }
    Step "the smoke test, after" { Smoke }
    Step "the test content removed from the DR copy" { Eax @("drill", "content-remove", $State) | Out-Null; $script:contentWhere = ""; "removed" }
    $exit = 0
} catch {
    $exit = 1
    # the failure explains itself (19:05): every container's state and the last lines of each one's log, where it failed
    try { $script:Diag = Eax @("drill", "diagnose", (Join-Path $Run "diagnostics")) } catch { }
} finally {
    $notes = New-Object System.Collections.Generic.List[string]
    foreach ($w in @($quietWhere) | Where-Object { $_ }) {
        $Install = $w; try { Eax @("drill", "quiet", "off") | Out-Null } catch { } }
    # the test content removed wherever EA Explorer still runs with it, before its state (and tokens) goes
    if ($contentWhere -and (Test-Path $State) -and -not ($shutDown -and $contentWhere -ieq $Original)) {
        $Install = $contentWhere
        try { Eax @("drill", "content-remove", $State) | Out-Null; $contentWhere = "" } catch { } }
    if (Test-Path $State) { Remove-Item -Force $State }          # the test accounts' tokens never stay on disk
    $ok = $exit -eq 0
    $Install = $Original
    # put everything back (09:03): the DR copy out of Docker and its folder gone, the installation started again
    if ($drStarted) {
        $drReports = Join-Path $Dr "work\dr"
        if (Test-Path $drReports) { Copy-Item -Recurse -Force $drReports (Join-Path $Run "eax-dr") }
        if (-not (Wait-LaterStart $Dr 20)) { $notes.Add("The DR copy's background start was still running after 20 minutes; removed anyway.") }
        try { $r = Eax @("drill", "remove-copy", $DrProject); $notes.Add("The DR copy removed from Docker: $($r.containers) container(s), $($r.volumes) volume(s).") }
        catch { $notes.Add("The DR copy could not be removed from Docker: $($_.Exception.Message). Run ``.\eax drill remove-copy $DrProject`` in the installation.") }
        try { Remove-Item -Recurse -Force -LiteralPath $Dr; $notes.Add("The DR folder $Dr deleted.") }
        catch { $notes.Add("The DR folder $Dr could not be deleted: $($_.Exception.Message)") }
    } elseif ((Test-Path -LiteralPath $Dr) -and -not (Get-ChildItem -Force -LiteralPath $Dr | Select-Object -First 1)) {
        Remove-Item -Force -LiteralPath $Dr }
    if ($shutDown) {
        Say "`n> the installation started again" "Cyan"
        try { Eax @("up", "--wait-all") | Out-Null; $notes.Add("The installation started again.") }
        catch { $notes.Add("The installation could not be started again: $($_.Exception.Message). In $Original run ``.\eax up``.") }
    }
    if ($BackupName) {
        if ($ok) {
            try { Eax @("drill", "delete-backup", $BackupName) | Out-Null; $notes.Add("The drill's backup $BackupName deleted.") }
            catch { $notes.Add("The drill's backup $BackupName could not be deleted: ``.\eax drill delete-backup $BackupName``.") }
        } else { $notes.Add("The drill's backup $BackupName is kept (pinned) in the installation's backups: ``.\eax drill delete-backup $BackupName`` when done.") }
    }
    if ($contentWhere) { $notes.Add("The test content (self_test_...) may still be in $contentWhere; the next self-test run there removes it.") }
    $mins = [int]((Get-Date) - $Started).TotalMinutes
    $md = @("# EA Explorer restore drill, $($Started.ToString('yyyy-MM-dd HH:mm'))", "",
            "**$(if (-not $ok) { 'Failed' } elseif ($AllWarnings.Count) { "Passed with $($AllWarnings.Count) warning(s)" } else { 'Passed' })** in $mins minutes. Installation ``$Original``, DR copy ``$Dr`` ($DrProject), version $($info.version), backup ``$BackupName``.", "")
    if ($script:Recovery) { $md += "Recovery time (from shutting the installation down to the DR copy restored and sign-in working): $($script:Recovery) minutes.", "" }
    $md += "| | Step | Seconds | Detail |", "| --- | --- | --- | --- |"
    foreach ($r in $Results) { $md += "| $(if (-not $r.ok) { 'FAILED' } elseif ($r.warn) { 'warn' } else { 'ok' }) | $($r.step) | $($r.seconds) | $(($r.detail -replace '\|', '/')) |" }
    if ($AllWarnings.Count) {
        $md += "", "## Warnings (the drill carried on)", ""
        foreach ($w in $AllWarnings) { $md += "- $w" } }
    if ($Diag) {
        $md += "", "## Diagnostics", "", "Every container's state and the last lines of each one's log: ``diagnostics\containers.txt`` and ``diagnostics\logs\`` beside this report.", ""
        if (@($Diag.not_well).Count) { foreach ($b in @($Diag.not_well)) { $md += "- not well: $b" } }
        else { $md += "- every container was running" } }
    $md += "", "## Afterwards", ""
    foreach ($n in $notes) { $md += "- $n" }
    # the report and the logs kept in the installation; the temp folder deleted
    $keep = Join-Path $Original "work\tests\$Stamp"
    $report = Join-Path $Run "report.md"
    if ($tempMade -and (Test-Path $Run)) {
        Set-Content -Encoding UTF8 $report $md
        Set-Content -Encoding UTF8 (Join-Path $Run "drill.log") $Lines
        try {
            New-Item -ItemType Directory -Force $keep | Out-Null
            foreach ($f in @("report.md", "drill.log", "eax-dr", "diagnostics")) {
                if (Test-Path (Join-Path $Run $f)) { Copy-Item -Recurse -Force (Join-Path $Run $f) $keep } }
            $report = Join-Path $keep "report.md"
            Remove-Item -Recurse -Force -LiteralPath $Run
            if (-not (Get-ChildItem -Force -LiteralPath $Temp | Select-Object -First 1)) { Remove-Item -Force -LiteralPath $Temp }
        } catch { Say "The report could not be moved into the installation: $($_.Exception.Message)" "Yellow" }
    }
    foreach ($n in $notes) { Say $n "Yellow" }
    foreach ($w in $AllWarnings) { Say "warning: $w" "Yellow" }
    $verdict = if (-not $ok) { "FAILED" } elseif ($AllWarnings.Count) { "PASSED with $($AllWarnings.Count) warning(s)" } else { "PASSED" }
    Say ("`nEA Explorer restore drill $verdict in $mins minutes. Report: $report") $(if (-not $ok) { "Red" } elseif ($AllWarnings.Count) { "Yellow" } else { "Green" })
}
exit $exit
