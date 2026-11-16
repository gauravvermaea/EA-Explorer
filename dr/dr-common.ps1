# dr-common.ps1: what eax-dr.ps1 and eax-drill.ps1 share (R5.6-B2), dot-sourced from the same folder. Each script sets
# $Install (the installation's folder), $Lines and $Results (the log and the steps) before it uses these.

$Ps = (Get-Process -Id $PID).Path

function Say([string]$Text, [string]$Color = "Gray") {
    Write-Host $Text -ForegroundColor $Color
    $Lines.Add("$(Get-Date -Format 'HH:mm:ss') $Text")
}

function Step([string]$Name, [scriptblock]$Body) {
    Say "`n> $Name" "Cyan"
    $t0 = Get-Date
    try {
        $detail = & $Body
        $s = [int]((Get-Date) - $t0).TotalSeconds
        $Results.Add([pscustomobject]@{ step = $Name; ok = $true; seconds = $s; detail = "$detail" })
        Say "  ok   $Name ($s s)$(if ($detail) { ': ' + $detail })" "Green"
    } catch {
        $s = [int]((Get-Date) - $t0).TotalSeconds
        $Results.Add([pscustomobject]@{ step = $Name; ok = $false; seconds = $s; detail = "$($_.Exception.Message)" })
        Say "  FAIL $Name : $($_.Exception.Message)" "Red"
        throw
    }
}

function Eax([string[]]$EaxArgs) {
    # one eax command in the install folder, waited for; its lines shown and kept; the last JSON line returned
    Push-Location $Install
    try {
        $out = & $Ps -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Install "eax.ps1") @EaxArgs 2>&1 | ForEach-Object {
            $l = "$_"; Write-Host "    $l"; $Lines.Add("    $l"); $l }
        $code = $LASTEXITCODE
    } finally { Pop-Location }
    $json = $null
    foreach ($l in @($out)) { if ("$l".TrimStart().StartsWith("{")) { try { $json = "$l" | ConvertFrom-Json } catch { } } }
    if ($code -ne 0) {
        $why = if ($json -and $json.error) { $json.error } else { "exit $code" }
        throw ".\eax $($EaxArgs -join ' ') failed: $why"
    }
    return $json
}

function Sha([string]$Path) { (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLower() }

function Test-BackupWhole([string]$Folder) {
    # every file SHA256SUMS lists, as it says (sha256sum's format: "<hash>  <path>")
    $sums = Join-Path $Folder "SHA256SUMS"
    if (-not (Test-Path $sums)) { throw "$Folder has no SHA256SUMS: not a whole infrastructure backup" }
    $n = 0
    foreach ($line in Get-Content $sums) {
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
    $have = (Select-String -Path $toml -Pattern '^version\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
    if ($have -ne $Ver) { throw "the code is of version $have, not $Ver" }
    $n = 0
    foreach ($line in Get-Content $sums) {
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
