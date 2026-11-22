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

  Asks nothing. Simple on purpose (the owner, 18 Nov 2026, 07:12: "this will be used in critical failure so things need
  to work"; "Key items, check is only a warning, unless the actual migration fails dont fail test. If we can login into
  the new instance we are good"). The drill FAILS only when the restore cannot be done or nobody can sign in afterwards:
  the checks before anything is touched, the backup, its copy, shutting the installation down, eax-dr (build and
  restore) and the sign-in. Everything else is a WARNING and the drill carries on: the maintenance page, the background,
  the key items counted before and after (models, elements, relationships, commits, projects, documents, people), the
  rest of the DR copy starting, and the smoke test (only with -Smoke). No test content is made.
    1. checks: the installation is there; the DR and temp folders are apart from it and hold nothing but an earlier
       drill's leftovers; then the last drill's DR copy (left running for you to test) removed from Docker with its
       folder, and the folders made; the installation started if the last drill left it stopped; free disk checked
    2. the maintenance page on, the background paused and finished (warnings); the key items counted (a warning)
    3. a full backup, copied straight out of EA Explorer into the temp folder with the env file and the code, and
       checked against their checksums (while EA Explorer still runs, so no folder setting can send it astray)
    4. the background back, the maintenance page off (warnings); the installation shut down (containers removed; data
       volumes and images kept)
    5. eax-dr (this folder): that code into the DR folder (no GitHub), under its own Docker name (eaexplorer-dr, its own
       volumes), the env file and the backup put in place, built, restored
    6. in the DR copy: a real sign-in (Keycloak signs its admin in and counts EA Explorer's people; the API answers);
       then the key items compared with before, the background back, the rest up (warnings)
  Then the DR copy is LEFT RUNNING for you to test, and the installation stays stopped (they share the ports): the
  owner, 18 Nov 2026, 07:46: "Leave the drill running and install stopped. I will manually remove it or delete it and
  start back install as I see fit". Back: `.\eax stop` in the DR folder, `.\eax up` in the installation. The next
  drill removes the DR copy at its start. With -ThenBack (R9.10, eax test full) the DR copy is stopped (kept) and the
  installation started again instead; -SmokeAfter runs the smoke test on the DR copy only. When it fails before eax-dr starts, the installation is started again. The
  drill's backup is kept (pinned). The temp folder is deleted; the report and the logs stay in the installation:
  work\tests\drill-<time>\report.md, with the recovery time.

.EXAMPLE
  .\dr\eax-drill.ps1 -Install C:\Users\gaura\Github\EA-Enterpise -Dr C:\EA-DR\drill1 -Temp C:\EA-DR\temp
#>
param(
    [Parameter(Mandatory = $true)][string]$Install,
    [Parameter(Mandatory = $true)][string]$Dr,
    [Parameter(Mandatory = $true)][string]$Temp,
    [switch]$Smoke,     # the full smoke test before and after too (its findings are warnings): about ten minutes more
    [switch]$SmokeAfter,  # the smoke test on the DR copy only (R9.10: eax test full)
    [switch]$ThenBack     # afterwards the DR copy stopped (kept) and the installation started again (R9.10)
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

# the smoke test, only with -Smoke (owner, 18 Nov 2026, 06:39): what it finds is a warning
function Smoke {
    try { Eax @("test", "smoke") | Out-Null; return "passed" }
    catch {
        $r = Eax @("drill", "smoke-result")
        return "$(@($r.warnings).Count) finding(s), as warnings: the restore is judged on the sign-in"
    }
}

$Started = Get-Date
$Diag = $null
$Lines = New-Object System.Collections.Generic.List[string]
$Results = New-Object System.Collections.Generic.List[object]
. (Join-Path $Here "dr-common.ps1")    # Say, Step, Eax, Sha, Test-BackupWhole, Test-CodeWhole
$Stamp = "drill-" + $Started.ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$Run = Join-Path $Temp $Stamp
$exit = 1
$info = $null
$BackupName = ""
$copy = ""
$shutDown = $false
$drStarted = $false       # eax-dr began building the DR copy (it may be half built)
$back = $false            # -ThenBack: the installation running again
$quietWhere = ""          # the folder whose background is paused, so it is never left paused
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
        "version $($info.version)" }
    # the last drill's DR copy is left running for the owner to test (18 Nov 2026, 07:46: "I want the dr site to be there
    # for me to test as I see fit"; "you can start at the start of the test to remove any historic data"): removed here
    Step "an earlier drill's DR copy and leftovers removed and the folders made" {
        # its background start finished first, or its log locks the folder (the owner's drill, 17 Nov 2026, 21:10)
        if (Test-Path -LiteralPath $Dr) { if (-not (Wait-LaterStart $Dr 20)) { Warn "the earlier DR copy's background start was still running after 20 minutes; removed anyway" } }
        $r = Eax @("drill", "remove-copy", $DrProject)
        if (Test-Path -LiteralPath $Dr) { Remove-Item -Recurse -Force -LiteralPath $Dr }
        Get-ChildItem -Force -LiteralPath $Temp | Where-Object { $_.Name -ne $Stamp } | Remove-Item -Recurse -Force
        New-Item -ItemType Directory -Force $Dr | Out-Null
        "$($r.containers) container(s), $($r.volumes) volume(s) of an earlier DR copy removed" }
    Step "the installation running (started when the last drill left it stopped)" {
        $said = "running"
        try { Eax @("drill", "running") | Out-Null }
        catch { Eax @("up", "--wait-all") | Out-Null; Eax @("drill", "running") | Out-Null; $said = "started" }
        # the pre-flight (19:05): too little disk fails now, in seconds, not half an hour in; a container still starting or
        # the background busy is a warning
        $pf = Eax @("drill", "preflight", $Temp, $Dr)
        "$said; a backup of about $($pf.backup_gb) GB fits" }
    if ($Smoke) { SoftStep "the smoke test, before (asked for: findings are warnings)" { Smoke } }
    SoftStep "the maintenance page on and the background paused" { $script:quietWhere = $Install; Eax @("drill", "quiet", "on") | Out-Null }
    SoftStep "the background finished what it was doing" { $w = Eax @("drill", "idle"); "waited $($w.waited) s" }
    SoftStep "the key items counted" {
        $f = Eax @("drill", "fingerprint", (Join-Path $Run "before.json")); "$($f.tables) tables, $($f.files) files" }
    Step "a full infrastructure backup" {
        $b = Eax @("drill", "backup"); $script:BackupName = $b.name
        "$($b.name), $([math]::Round($b.bytes / 1GB, 2)) GB in $($b.seconds) s" }
    Step "the backup, the env file and the code copied out into the temp folder and checked" {
        $script:copy = Join-Path $Run "backup\$BackupName"
        $t = Eax @("drill", "take", $BackupName, $copy)
        Copy-Item -LiteralPath $info.config (Join-Path $Run "eaexplorer.env") -Force
        if ((Sha $info.config) -ne (Sha (Join-Path $Run "eaexplorer.env"))) { throw "the env file's copy does not match" }
        $n = Test-BackupWhole $copy
        Eax @("drill", "code", (Join-Path $Run "code")) | Out-Null
        $c = Test-CodeWhole (Join-Path $Run "code") $info.version
        "$n backup files ($($t.how)), the env file and $c code files, each matching its checksum" }
    SoftStep "the background back and the maintenance page off" { Eax @("drill", "quiet", "off") | Out-Null; $script:quietWhere = "" }
    $t0 = Get-Date
    Step "the installation shut down (containers removed; data and images kept)" {
        Eax @("drill", "shutdown") | Out-Null; $script:shutDown = $true; "stopped" }
    Step "eax-dr: v$($info.version) from the copied code (no GitHub) into $Dr, built and restored ($DrProject)" {
        $script:drStarted = $true
        & (Get-Process -Id $PID).Path -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Here "eax-dr.ps1") `
            -Backup $copy -Install $Dr -Code (Join-Path $Run "code") -Env (Join-Path $Run "eaexplorer.env") -Project $DrProject -KeepQuiet -NoSmoke
        if ($LASTEXITCODE -ne 0) { throw "eax-dr failed (its report is in $Dr\work\dr)" }
        $script:quietWhere = $Dr
        "done" }
    $Install = $Dr                     # from here on, eax runs in the DR copy
    Step "a real sign-in to the DR copy" { $s = Eax @("drill", "signin"); "signed in; $($s.people) people in $($s.realm); the API answers" }
    $script:Recovery = [int]((Get-Date) - $t0).TotalMinutes
    SoftStep "the key items compared with before" {
        if (-not (Test-Path (Join-Path $Run "before.json"))) { throw "not counted before the backup" }
        Eax @("drill", "fingerprint", (Join-Path $Run "after.json")) | Out-Null
        $c = Eax @("drill", "compare", (Join-Path $Run "before.json"), (Join-Path $Run "after.json"))
        "$($c.keys_said)" }
    SoftStep "the background back and the maintenance page off" { Eax @("drill", "quiet", "off") | Out-Null; $script:quietWhere = "" }
    SoftStep "the rest of the DR copy up (Reports, Documents, Diagrams)" { Eax @("up", "--wait-all") | Out-Null; "every container up" }
    if ($Smoke -or $SmokeAfter) { SoftStep "the smoke test, after (asked for: findings are warnings)" { Smoke } }
    # -ThenBack (R9.10, eax test full): the DR copy stopped and kept; the installation started again and signed in to
    if ($ThenBack) {
        Step "the DR copy stopped (kept)" { Eax @("stop") | Out-Null; "stopped; kept in $Dr" }
        $Install = $Original           # from here on, eax runs in the installation again
        Step "the installation started again and a real sign-in" {
            Eax @("up", "--wait-all") | Out-Null; $script:back = $true
            $s = Eax @("drill", "signin"); "running again; signed in; $($s.people) people" }
    }
    $exit = 0
} catch {
    $exit = 1
    # the failure explains itself (19:05): every container's state and the last lines of each one's log, where it failed
    try { $script:Diag = Eax @("drill", "diagnose", (Join-Path $Run "diagnostics")) } catch { }
} finally {
    $notes = New-Object System.Collections.Generic.List[string]
    foreach ($w in @($quietWhere) | Where-Object { $_ }) {
        $Install = $w; try { Eax @("drill", "quiet", "off") | Out-Null } catch { } }
    $ok = $exit -eq 0
    $Install = $Original
    # the DR copy left as it is, running, for the owner to test; the installation left stopped (they share the ports)
    # (the owner, 18 Nov 2026, 07:46: "Leave the drill running and install stopped. I will manually remove it or delete it
    # and start back install as I see fit"); the next drill removes it at its start
    if ($drStarted -and $ThenBack) {
        # -ThenBack (R9.10): the DR copy stopped and kept, the installation running again; tried here too when the drill
        # failed before it got there
        $drReports = Join-Path $Dr "work\dr"
        if (Test-Path $drReports) { Copy-Item -Recurse -Force $drReports (Join-Path $Run "eax-dr") }
        if (-not $back) {
            Say "`n> back to the installation (the DR copy stopped and kept)" "Cyan"
            $Install = $Dr; try { Eax @("stop") | Out-Null } catch { }
            $Install = $Original
            try { Eax @("up", "--wait-all") | Out-Null; $back = $true }
            catch { $notes.Add("The installation could not be started again: in $Dr run ``.\eax stop``, then in $Original run ``.\eax up``.") }
        }
        if ($back) {
            $notes.Add("The DR copy is stopped and kept in $Dr ($DrProject): to look at it, in $Original run ``.\eax stop``, then in $Dr run ``.\eax up``.")
            $notes.Add("Your installation is running again.")
        }
        $notes.Add("To remove the DR copy: in $Original run ``.\eax drill remove-copy $DrProject`` and delete $Dr; the next drill does both at its start.")
    } elseif ($drStarted) {
        $drReports = Join-Path $Dr "work\dr"
        if (Test-Path $drReports) { Copy-Item -Recurse -Force $drReports (Join-Path $Run "eax-dr") }
        $notes.Add("The DR copy is left running in $Dr ($DrProject), at the address your installation uses; your installation is stopped (they share the ports).")
        $notes.Add("Back to your installation: in $Dr run ``.\eax stop``, then in $Original run ``.\eax up``.")
        $notes.Add("To remove the DR copy: in $Original run ``.\eax drill remove-copy $DrProject`` and delete $Dr; the next drill does both at its start.")
    } elseif ((Test-Path -LiteralPath $Dr) -and -not (Get-ChildItem -Force -LiteralPath $Dr | Select-Object -First 1)) {
        Remove-Item -Force -LiteralPath $Dr }
    if ($shutDown -and -not $drStarted) {
        Say "`n> the installation started again" "Cyan"
        try { Eax @("up", "--wait-all") | Out-Null; $notes.Add("The installation started again.") }
        catch { $notes.Add("The installation could not be started again: $($_.Exception.Message). In $Original run ``.\eax up``.") }
        # the maintenance page never left on in the installation (a warning step may not have switched it off)
        try { Eax @("drill", "quiet", "off") | Out-Null } catch { $notes.Add("The maintenance page may still be on: in $Original run ``.\eax drill quiet off``.") }
    }
    if ($BackupName) {
        $notes.Add("The drill's backup $BackupName is kept (pinned) in the installation's backups: once the installation runs again, ``.\eax drill delete-backup $BackupName`` when done.")
    }
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
