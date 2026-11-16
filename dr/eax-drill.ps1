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
  22:44: the code goes with the backup, as in a DR pack, so no GitHub is needed.

  Asks nothing. One step after another, stopping at the first that fails:
    1. checks, nothing touched: the installation is there and running; the DR folder is new or empty and apart from
       it; Docker has nothing named eaexplorer-dr yet
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
  The DR copy is left running at the same address. The report (<temp>/drill-<time>/report.md) gives the recovery time
  and the two commands to go back to the installation: eax down in the DR folder, eax up in the installation.

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
$DrProject = "eaexplorer-dr"

function Inside([string]$Path, [string]$Folder) { $Path.StartsWith($Folder + "\", [StringComparison]::OrdinalIgnoreCase) -or $Path -ieq $Folder }

$Started = Get-Date
$Lines = New-Object System.Collections.Generic.List[string]
$Results = New-Object System.Collections.Generic.List[object]
. (Join-Path $Here "dr-common.ps1")    # Say, Step, Eax, Sha, Test-BackupWhole, Test-CodeWhole
$Run = Join-Path $Temp ("drill-" + $Started.ToUniversalTime().ToString("yyyyMMddTHHmmssZ"))
$State = Join-Path $Run "content.json"      # the test content's ids and its test accounts' tokens: removed at the end
$exit = 1
$info = $null
$name = ""
$copy = ""
$shutDown = $false
$quietWhere = ""          # the folder whose background is paused, so it is never left paused
$contentWhere = ""        # the folder that still holds the test content
try {
    New-Item -ItemType Directory -Force $Run | Out-Null
    Say "EA Explorer restore drill: $Install backed up and shut down; a copy built from its own code in $Dr and restored. Nothing is asked." "Yellow"
    Step "checks (nothing touched yet)" {
        if (-not (Test-Path (Join-Path $Install "eax.ps1")) -or -not (Test-Path (Join-Path $Install "work\eaexplorer.env"))) {
            throw "$Install is not an EA Explorer installation (no eax.ps1 or work\eaexplorer.env)" }
        foreach ($p in @($Dr, $Temp)) {
            if ((Inside $p $Install) -or (Inside $Install $p)) { throw "$p must be a folder of its own, outside $Install" } }
        if ((Inside $Dr $Temp) -or (Inside $Temp $Dr)) { throw "the DR folder and the temp folder must be apart" }
        if ((Test-Path $Dr) -and (Get-ChildItem -Force $Dr | Select-Object -First 1)) { throw "$Dr is not empty: the DR copy always goes into a new folder" }
        & docker info --format "{{.ServerVersion}}" *> $null
        if ($LASTEXITCODE -ne 0) { throw "Docker does not answer: start Docker Desktop" }
        $script:info = Eax @("drill", "info")
        Eax @("drill", "running") | Out-Null
        $other = @(& docker ps -aq --filter "label=com.docker.compose.project=$DrProject")
        if ($other.Count -gt 0) { throw "a DR copy from an earlier drill is still in Docker ($DrProject): in its folder run .\eax cleanup --all" }
        "running, version $($info.version)" }
    Step "the smoke test, before" { Eax @("test", "smoke") | Out-Null; "passed" }
    Step "a test project, models and content of every kind" {
        $c = Eax @("drill", "content", $State); $script:contentWhere = $Install; "$($c.made) kinds made and read back" }
    Step "the maintenance page on and the background paused" { Eax @("drill", "quiet", "on") | Out-Null; $script:quietWhere = $Install }
    Step "the background finished what it was doing" { $w = Eax @("drill", "idle"); "waited $($w.waited) s" }
    Step "the fingerprint before (every table and file)" {
        $f = Eax @("drill", "fingerprint", (Join-Path $Run "before.json")); "$($f.tables) tables, $($f.files) files" }
    Step "a full infrastructure backup" {
        $b = Eax @("drill", "backup"); $script:name = $b.name
        "$($b.name), $([math]::Round($b.bytes / 1GB, 2)) GB in $($b.seconds) s" }
    Step "the test content removed from the installation" {
        Eax @("drill", "content-remove", $State) | Out-Null; $script:contentWhere = ""; "removed" }
    Step "the background back and the maintenance page off" { Eax @("drill", "quiet", "off") | Out-Null; $script:quietWhere = "" }
    $t0 = Get-Date
    Step "the installation shut down (containers removed; data and images kept)" {
        Eax @("drill", "shutdown") | Out-Null; $script:shutDown = $true; "stopped" }
    Step "the backup, the env file and the code copied into the temp folder and checked" {
        $src = Join-Path $info.backups $name
        $script:copy = Join-Path $Run "backup\$name"
        New-Item -ItemType Directory -Force (Split-Path $copy) | Out-Null
        Copy-Item -LiteralPath $src $copy -Recurse -Force
        Copy-Item -LiteralPath $info.config (Join-Path $Run "eaexplorer.env") -Force
        if ((Sha $info.config) -ne (Sha (Join-Path $Run "eaexplorer.env"))) { throw "the env file's copy does not match" }
        $n = Test-BackupWhole $copy
        Eax @("drill", "code", (Join-Path $Run "code")) | Out-Null
        $c = Test-CodeWhole (Join-Path $Run "code") $info.version
        "$n backup files, the env file and $c code files, each matching its checksum" }
    Step "eax-dr: v$($info.version) from the copied code (no GitHub) into $Dr, built and restored ($DrProject)" {
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
        "$($c.tables) tables and $($c.files) files the same$(if (@($c.not_compared).Count) { "; $(@($c.not_compared).Count) the installation writes by itself not compared" })" }
    Step "the test content found in the DR copy as it was made" { $c = Eax @("drill", "content-check", $State); "$($c.kinds) kinds, the same" }
    Step "the background back and the maintenance page off" { Eax @("drill", "quiet", "off") | Out-Null; $script:quietWhere = "" }
    Step "the smoke test, after" { Eax @("test", "smoke") | Out-Null; "passed" }
    Step "the test content removed from the DR copy" { Eax @("drill", "content-remove", $State) | Out-Null; $script:contentWhere = ""; "removed" }
    $exit = 0
} catch {
    $exit = 1
} finally {
    foreach ($w in @($quietWhere) | Where-Object { $_ }) {
        $Install = $w; try { Eax @("drill", "quiet", "off") | Out-Null } catch { } }
    if (Test-Path $State) { Remove-Item -Force $State }          # the test accounts' tokens never stay on disk
    $ok = $exit -eq 0
    $mins = [int]((Get-Date) - $Started).TotalMinutes
    if ($ok -and $copy -and (Test-Path $copy)) { Remove-Item -Recurse -Force (Split-Path $copy) }
    if ($ok -and (Test-Path (Join-Path $Run "code"))) { Remove-Item -Recurse -Force (Join-Path $Run "code") }
    $md = @("# EA Explorer restore drill, $($Started.ToString('yyyy-MM-dd HH:mm'))", "",
            "**$(if ($ok) { 'Passed' } else { 'Failed' })** in $mins minutes. Installation ``$($info.root)``, DR copy ``$Dr``, version $($info.version), backup ``$name``.", "")
    if ($script:Recovery) { $md += "Recovery time (from shutting the installation down to the DR copy restored and up): $($script:Recovery) minutes.", "" }
    $md += "| | Step | Seconds | Detail |", "| --- | --- | --- | --- |"
    foreach ($r in $Results) { $md += "| $(if ($r.ok) { 'ok' } else { 'FAILED' }) | $($r.step) | $($r.seconds) | $(($r.detail -replace '\|', '/')) |" }
    if ($contentWhere) { $md += "", "The test content (self_test_...) is still in $contentWhere; the next self-test run removes it." }
    if ($shutDown) {
        $back = @("", "## Back to the installation", "", "    cd `"$Dr`"; .\eax down", "    cd `"$($info.root)`"; .\eax up", "",
                  "Or keep the DR copy: it runs at the same address, under the Docker name $DrProject.")
        if (-not $ok -and $copy) { $back += "", "The backup is kept in ``$copy``." }
        $md += $back
        Say "`nBack to the installation:  cd `"$Dr`"; .\eax down   then   cd `"$($info.root)`"; .\eax up" "Yellow"
    }
    Set-Content -Encoding UTF8 (Join-Path $Run "report.md") $md
    Set-Content -Encoding UTF8 (Join-Path $Run "drill.log") $Lines
    Say ("`nEA Explorer restore drill " + $(if ($ok) { "PASSED" } else { "FAILED" }) + " in $mins minutes. Report: $Run\report.md") $(if ($ok) { "Green" } else { "Red" })
}
exit $exit
