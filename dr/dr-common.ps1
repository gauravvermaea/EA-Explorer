# dr-common.ps1: what eax-dr.ps1 and eax-drill.ps1 share (R5.6-B2), dot-sourced from the same folder. Each script sets
# $Install (the installation's folder), $Lines and $Results (the log and the steps) before it uses these.

$Ps = (Get-Process -Id $PID).Path

function Say([string]$Text, [string]$Color = "Gray") {
    Write-Host $Text -ForegroundColor $Color
    $Lines.Add("$(Get-Date -Format 'HH:mm:ss') $Text")
}

# Step's own names start with "step": a block runs inside Step and sees its variables, so a block's $name was Step's
# $Name, the step's title (the owner's drill, 17 Nov 2026, 09:02: "Cannot find path ...\infrastructure\the backup, the
# env file and the code copied into the temp folder and checked").
function Step([string]$StepTitle, [scriptblock]$StepBody) {
    Say "`n> $StepTitle" "Cyan"
    $stepStart = Get-Date
    try {
        $stepDetail = & $StepBody
        $stepSecs = [int]((Get-Date) - $stepStart).TotalSeconds
        $Results.Add([pscustomobject]@{ step = $StepTitle; ok = $true; seconds = $stepSecs; detail = "$stepDetail" })
        Say "  ok   $StepTitle ($stepSecs s)$(if ($stepDetail) { ': ' + $stepDetail })" "Green"
    } catch {
        $stepSecs = [int]((Get-Date) - $stepStart).TotalSeconds
        $Results.Add([pscustomobject]@{ step = $StepTitle; ok = $false; seconds = $stepSecs; detail = "$($_.Exception.Message)" })
        Say "  FAIL $StepTitle : $($_.Exception.Message)" "Red"
        throw
    }
}

# A program's own messages on its error stream are not failures: Windows PowerShell 5.1 turns each such line into an
# error, and with $ErrorActionPreference = "Stop" the first one ended the step (the owner's drill, 17 Nov 2026, 08:17:
# "FAIL a test project, models and content of every kind : the test's record: self-test run 14", a progress line the
# test writes to its error stream). Only the program's exit code says whether it failed.
function Invoke-Native([scriptblock]$Block) {
    $ErrorActionPreference = "Continue"          # this function's own: the scripts keep "Stop"
    $global:NativeExit = 0
    & $Block 2>&1 | ForEach-Object { if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { "$_" } }
    $global:NativeExit = $LASTEXITCODE      # read here, where the program ran (11:13: a failed step read as 0 outside)
}

function Eax([string[]]$EaxArgs) {
    # one eax command in the install folder, waited for; its lines shown and kept; the last JSON line returned
    Push-Location $Install
    try {
        $eaxPs1 = Join-Path $Install "eax.ps1"
        $out = Invoke-Native { & $Ps -NoProfile -ExecutionPolicy Bypass -File $eaxPs1 @EaxArgs } | ForEach-Object {
            $l = "$_"; Write-Host "    $l"; $Lines.Add("    $l"); $l }
        $code = $global:NativeExit
    } finally { Pop-Location }
    $json = $null
    foreach ($l in @($out)) { if ("$l".TrimStart().StartsWith("{")) { try { $json = "$l" | ConvertFrom-Json } catch { } } }
    # a step's own answer saying it failed counts too, whatever the exit code came back as (the owner's drill, 11:13:
    # {"error": "14 container(s) left"} was taken as done)
    if ($code -ne 0 -or ($json -and $json.error)) {
        $why = if ($json -and $json.error) { $json.error } else { "exit $code" }
        throw ".\eax $($EaxArgs -join ' ') failed: $why"
    }
    return $json
}

# Every text file is read as UTF-8 (Windows PowerShell 5.1 reads ANSI otherwise): the owner's drill, 17 Nov 2026, 11:45,
# failed on "TOGAF® Template - Architecture Definition.docx", whose name CODE.sha256 holds in UTF-8.
function Sha([string]$Path) { (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLower() }

function Test-BackupWhole([string]$Folder) {
    # every file SHA256SUMS lists, as it says (sha256sum's format: "<hash>  <path>")
    $sums = Join-Path $Folder "SHA256SUMS"
    if (-not (Test-Path $sums)) { throw "$Folder has no SHA256SUMS: not a whole infrastructure backup" }
    $n = 0
    foreach ($line in Get-Content -Encoding UTF8 $sums) {
        if ($line -notmatch '^([0-9a-fA-F]{64})\s+\*?(.+)$') { continue }
        $rel = $Matches[2] -replace '^\./', ''
        $p = Join-Path $Folder ($rel -replace '/', '\')
        if (-not (Test-Path -LiteralPath $p)) { throw "$rel is missing from $Folder" }
        if ((Sha $p) -ne $Matches[1].ToLower()) { throw "$rel in $Folder does not match its checksum" }
        $n++
    }
    if ($n -eq 0) { throw "SHA256SUMS in $Folder lists no file" }
    return $n
}

# a copy of EA Explorer's code (eax drill code, a pack's code\): every file CODE.sha256 lists, as it says, and
# services\api\version.toml of that version; returns how many files
function Test-CodeWhole([string]$Folder, [string]$Ver) {
    $sums = Join-Path $Folder "CODE.sha256"
    if (-not (Test-Path -LiteralPath $sums)) { throw "$Folder has no CODE.sha256: not a copy of EA Explorer's code (eax drill code makes one)" }
    $toml = Join-Path $Folder "services\api\version.toml"
    if (-not (Test-Path -LiteralPath $toml)) { throw "$Folder has no services\api\version.toml: not EA Explorer's code" }
    $have = (Select-String -Encoding UTF8 -Path $toml -Pattern '^version\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
    if ($have -ne $Ver) { throw "the code is of version $have, not $Ver" }
    $n = 0
    foreach ($line in Get-Content -Encoding UTF8 $sums) {
        if ($line -notmatch '^([0-9a-f]{64})  (.+)$') { continue }
        $p = Join-Path $Folder ($Matches[2] -replace '/', '\')
        if (-not (Test-Path -LiteralPath $p) -or (Sha $p) -ne $Matches[1]) { throw "$($Matches[2]) in the code is missing or does not match its checksum" }
        $n++
    }
    $n
}

function Get-Release([string]$RepoUrl, [string]$Ver) {
    if ($RepoUrl -notmatch 'github\.com[/:]([^/]+)/([^/.]+?)(\.git)?/?$') { throw "$RepoUrl is not a github.com repository" }
    $o, $r = $Matches[1], $Matches[2]
    $api = if ($env:EAX_GITHUB_API) { $env:EAX_GITHUB_API } else { "https://api.github.com" }
    try { $rel = Invoke-RestMethod -Headers @{ Accept = "application/vnd.github+json" } "$api/repos/$o/$r/releases/tags/v$Ver" }
    catch { throw "v$Ver is not a published release of $RepoUrl (or GitHub cannot be reached): publish it first ($($_.Exception.Message))" }
    if ($rel.draft) { throw "v$Ver of $RepoUrl is still a draft: publish it first" }
    return @{ owner = $o; repo = $r }
}
