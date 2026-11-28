<#
EA Explorer helper for Windows (PowerShell 5.1 or 7). Linux and macOS: use eax.sh.
Run  .\eax help  for every command.

The script is not signed. Either use the launcher, which bypasses the execution policy for this run only:
    .\eax up
or call PowerShell with the bypass yourself:
    powershell -NoProfile -ExecutionPolicy Bypass -File .\eax.ps1 up

Everything local lives in the work folder, which is never committed: the config file
(work\eaexplorer.env), the logs (work\logs) and laptop data (work\data: backups, imports, exports, tls).
#>
# No param() block on purpose: options such as --all, --yes and --scratch must reach the script as
# plain text, and an advanced-script parameter block would reject them as unknown parameters.
# --no-color anywhere: plain text (R2.10). Colour only in a console: never with NO_COLOR or CI set, never redirected.
$AllArgs = @($args | ForEach-Object { [string]$_ })
$script:NoColor = ($AllArgs -contains "--no-color") -or [bool]$env:NO_COLOR -or [bool]$env:EAX_NO_COLOR -or [bool]$env:CI -or
                  [Console]::IsOutputRedirected
$AllArgs = @($AllArgs | Where-Object { $_ -ne "--no-color" })
if ($script:NoColor) {
    # every Write-Host in this script, without its colours
    function Write-Host {
        param([Parameter(Position = 0, ValueFromRemainingArguments = $true)][object[]]$Object, [object]$ForegroundColor,
              [object]$BackgroundColor, [switch]$NoNewline, [object]$Separator = " ")
        Microsoft.PowerShell.Utility\Write-Host -Object (@($Object) -join [string]$Separator) -NoNewline:$NoNewline
    }
}
# no command in a console: the full screen (R3.1; it falls back to the numbered menu, R2.29); redirected or in a
# script: the help, as before
$Command = if ($AllArgs.Count -gt 0) { $AllArgs[0] } elseif ([Console]::IsInputRedirected) { "help" } else { "screen" }
$AskedFor = $Command          # as typed, for <command> --help
if ($Command -eq "run") { $Command = "up" }   # run: the everyday start, the same as up
if ($Command -eq "stop") { $Command = "down" }   # stop: the same as down (the data is kept)
$Rest = @($AllArgs | Select-Object -Skip 1)
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
$WorkDir = Join-Path $PSScriptRoot "work"
$EnvFile = "work/eaexplorer.env"
# work/compose-project: this installation's own Docker name (R5.6-B2: a DR copy beside the original keeps its own
# containers and volumes); not in the config file, so a restore never changes it
if (Test-Path "work/compose-project") { $env:COMPOSE_PROJECT_NAME = (Get-Content "work/compose-project" -TotalCount 1).Trim() }
$LogDir = Join-Path $WorkDir "logs"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$RestArgs = @($Rest | Where-Object { $_ })   # extra arguments, without empty entries
# --wait-all (up, run, debug and the clean-* commands): start everything and wait until all of it is up, the sample data
# loaded too; without it the core starts first and the rest in the background (D255)
$WaitAll = $RestArgs -contains "--wait-all"
$RestArgs = @($RestArgs | Where-Object { $_ -ne "--wait-all" })
$script:Log = $null          # StreamWriter for this run's log
$script:LogPath = $null
$Utf8 = New-Object System.Text.UTF8Encoding $false

# ------------------------------------------------------------------ logging
function Open-Writer([string]$Path) {
    $w = New-Object System.IO.StreamWriter($Path, $true, $Utf8)
    $w.AutoFlush = $true
    return $w
}

function Start-Log([string]$Name) {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    # keep two weeks of logs
    Get-ChildItem -Path $LogDir -Filter "*.log" -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-14) } | Remove-Item -Force -ErrorAction SilentlyContinue
    $script:LogPath = Join-Path $LogDir "eax-$Stamp-$Name.log"
    $script:Log = Open-Writer $script:LogPath
    $script:Log.WriteLine("=== eax $Name $($Rest -join ' ')   $(Get-Date -Format o)")
    $script:Log.WriteLine("=== folder $PSScriptRoot   PowerShell $($PSVersionTable.PSVersion)   $([Environment]::OSVersion.VersionString)")
    Write-Host "Log: $script:LogPath" -ForegroundColor DarkGray
}

function Stop-Log {
    if ($script:Log) { $script:Log.WriteLine("=== end $(Get-Date -Format o)"); $script:Log.Dispose(); $script:Log = $null }
}

function Write-Log([string]$Text = "", [string]$Color = "") {
    if ($Color) { Write-Host $Text -ForegroundColor $Color } else { Write-Host $Text }
    if ($script:Log) { $script:Log.WriteLine($Text) }
}

# Masks passwords, secrets and keys before config or container output reaches a log
function Hide-Secrets([string]$Line) {
    $Line = $Line -replace '((?:PASSWORD|SECRET|_KEY|URLENC)[A-Z_]*\s*[:=]\s*).*$', '$1****'
    $Line = $Line -replace '(redis://:)[^@]+@', '$1****@'
    $Line = $Line -replace '("PASSWORD"\s*:\s*")[^"]*"', '$1****"'
    return $Line
}

# Runs a program for its output alone: its error stream thrown away, never an error here. With $ErrorActionPreference
# "Stop", Windows PowerShell 5.1 turns a program's message on its error stream into an error even with 2>$null, so
# "git rev-parse" outside a git checkout ("fatal: not a git repository") stopped eax up (the owner's DR drill, 17 Nov
# 2026, 12:28: a DR copy has no .git). The exit code is in $global:QuietExit.
function Invoke-Quiet([string]$Exe, [string[]]$Arguments) {
    $ErrorActionPreference = "Continue"
    $global:QuietExit = 0
    & $Exe @Arguments 2>$null
    $global:QuietExit = $LASTEXITCODE
}

# Runs a program; every output line goes to the console (unless -Quiet) and to the log.
function Invoke-Logged([string]$Exe, [string[]]$Arguments, [switch]$Quiet, [switch]$Mask) {
    if ($script:Log) { $script:Log.WriteLine(""); $script:Log.WriteLine("> $Exe $($Arguments -join ' ')") }
    $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    $n = 0
    try {
        & $Exe @Arguments 2>&1 | ForEach-Object {
            $line = if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { "$_" }
            if ($Mask) { $line = Hide-Secrets $line }
            if (-not $Quiet) {
                $c = if ($script:StatusColours -and $n++ -gt 0) { Get-StateColour $line } else { "" }
                if ($c) { Write-Host $line -ForegroundColor $c } else { Write-Host $line }
            }
            if ($script:Log) { $script:Log.WriteLine($line) }
        }
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $old }
    if ($script:Log) { $script:Log.WriteLine("< exit $code") }
    return $code
}

# the colour of one `docker compose ps` line (R2.10; the same rule as eaxcli/core.py state_colour): red when down or
# failing, yellow while starting, grey for a finished set-up step, green when up
function Get-StateColour([string]$Line) {
    $low = $Line.ToLowerInvariant()
    if (($low.Contains("setup") -or $low.Contains("reports-init")) -and $low.Contains("exited (0")) { return "DarkGray" }
    foreach ($w in @("unhealthy", "dead", "restarting", "oomkilled")) { if ($low.Contains($w)) { return "Red" } }
    if ($low.Contains("exited (0")) { return "DarkGray" }
    if ($low.Contains("exited")) { return "Red" }
    foreach ($w in @("health: starting", "starting", "created", "paused", "removing")) { if ($low.Contains($w)) { return "Yellow" } }
    if ($low.Contains("up ") -or $low.Contains("running") -or $low.Contains("(healthy)")) { return "Green" }
    return ""
}

# did you mean (R2.29): the same rule as eaxcli/help.py suggest() and unknown()
function Get-Distance([string]$A, [string]$B) {
    $prev = 0..$B.Length
    for ($i = 1; $i -le $A.Length; $i++) {
        $cur = @($i)
        for ($j = 1; $j -le $B.Length; $j++) {
            $cost = if ($A[$i - 1] -ceq $B[$j - 1]) { 0 } else { 1 }
            $cur += [Math]::Min([Math]::Min($prev[$j] + 1, $cur[$j - 1] + 1), $prev[$j - 1] + $cost)
        }
        $prev = $cur
    }
    return $prev[$B.Length]
}
function Get-UnknownCommand([string]$Word) {
    $low = $Word.ToLowerInvariant()
    $names = New-Object 'System.Collections.Generic.SortedSet[string]' ([StringComparer]::Ordinal)
    foreach ($l in [System.IO.File]::ReadAllLines((Join-Path $PSScriptRoot "eaxcli\help.txt"))) {
        if ($l.StartsWith("### ")) { foreach ($nm in ($l.Substring(4).Split(" ")[0].Split("|"))) { [void]$names.Add($nm) } }
    }
    $most = if ($low.Length -le 3) { 1 } else { 2 }
    $scored = @()
    foreach ($nm in $names) {
        $sc = if ($low.Length -ge 2 -and $nm.StartsWith($low, [StringComparison]::Ordinal)) { 0 } else { Get-Distance $low $nm }
        if ($sc -le $most) { $scored += "$sc $nm" }
    }
    $sorted = [string[]]$scored; [Array]::Sort($sorted, [StringComparer]::Ordinal)
    $near = @($sorted | Select-Object -First 3 | ForEach-Object { $_.Substring($_.IndexOf(" ") + 1) })
    $hint = if ($near.Count -gt 0) { " Did you mean: $($near -join ', ')?" } else { "" }
    return "unknown command '$Word'.$hint Run .\eax help, or .\eax menu to pick one."
}

# ------------------------------------------------------------------ settings and compose
function Get-Setting([string]$Name, [string]$Default = "") {
    if (-not (Test-Path $EnvFile)) { return $Default }
    $line = Get-Content $EnvFile | Where-Object { $_ -match "^$Name=" } | Select-Object -First 1
    if (-not $line) { return $Default }
    $v = ($line -split "=", 2)[1].Trim()
    # strip surrounding single or double quotes
    if ($v.Length -ge 2 -and (($v.StartsWith("'") -and $v.EndsWith("'")) -or ($v.StartsWith('"') -and $v.EndsWith('"')))) { $v = $v.Substring(1, $v.Length - 2) }
    if ($v -eq "") { return $Default } else { return $v }
}

# the services' own config (R6-F1, D745): work/config.env, the config file without its passwords and keys (each value the
# server template holds as change-me), is what the containers read as their settings; the passwords and keys reach
# them as files of their own (Docker secrets: docker-compose.yml's secrets, from this command's --env-file), never as
# environment variables. Written before every compose command, so it never falls behind the config file.
function Write-ServiceEnv {
    if (-not (Test-Path $EnvFile)) { return }
    $keys = @{}
    foreach ($l in Get-Content -Encoding UTF8 "deploy/templates/eaexplorer.server.env") { if ($l -match '^([A-Z0-9_]+)=change-me') { $keys[$Matches[1]] = 1 } }
    foreach ($k in @("EAX_SMTP_PASSWORD", "EAX_MCP_DEV_TOKEN", "EAX_REMOTE_SECRET_KEY", "EAX_REPLICATION_PASSWORD", "EAX_TEST_USER_PASSWORD", "EAX_ARCHIVE_DB_URL", "EAX_CHANGELOG_DB_URL", "EAX_FARM_DB_URL", "EAX_FILES_DB_URL", "EAX_LIBRARY_MODELS_DB_URL", "EAX_OPERATIONS_DB_URL", "EAX_PERSONAL_DB_URL", "EAX_PROJECTS_DB_URL", "EAX_TESTS_DB_URL")) { $keys[$k] = 1 }
    $kept = New-Object System.Collections.Generic.List[string]
    $kept.Add("# Written by eax from eaexplorer.env without its passwords and keys (R6-F1). Do not edit; change eaexplorer.env.")
    foreach ($l in Get-Content -Encoding UTF8 $EnvFile) {
        if ($l -match '^([A-Z0-9_]+)=' -and $keys.ContainsKey($Matches[1])) { continue }
        $kept.Add($l)
    }
    [System.IO.File]::WriteAllText((Join-Path $PSScriptRoot "work/config.env"), (($kept -join "`n") + "`n"), $Utf8)
}

# where the data lives (R5.4, D687): with one base folder (EAX_DATA_ROOT), each folder is made and checked and its
# value put in this session's environment before containers are made (eaxpy folders env); docker compose takes them
function Use-DataFolders {
    if ($env:EAX_FOLDERS_RESOLVED) { return }
    if (-not (Test-Path $EnvFile)) { return }
    if (-not $env:EAX_DATA_ROOT -and -not (Select-String -Path $EnvFile -Pattern "^EAX_DATA_ROOT=.+" -Quiet)) { return }
    $lines = & (Join-Path $PSScriptRoot "eaxpy.ps1") folders env
    if ($LASTEXITCODE -ne 0) { throw "A data folder cannot be used (above): nothing was started. .\eax folders shows them." }
    foreach ($line in @($lines)) {
        $i = "$line".IndexOf("=")
        if ($i -gt 0 -and "$line" -match "^EAX_[A-Z_]+=") { [Environment]::SetEnvironmentVariable("$line".Substring(0, $i), "$line".Substring($i + 1)) }
    }
    $env:EAX_FOLDERS_RESOLVED = "1"
}

# the build shown with the release (R2.47): EAX_BUILD as CI sets it, else the count of commits, so it goes up by one
# with every commit (D882), one more when files differ from the last commit; "dev" outside git; the commit and its
# time, so the API container is made again only when they change
function Get-BuildId {
    if ($env:EAX_BUILD) { return $env:EAX_BUILD }
    $c = "$(Invoke-Quiet git @("rev-list", "--count", "HEAD"))".Trim()
    if ($global:QuietExit -ne 0 -or $c -notmatch '^[0-9]+$') { return "dev" }
    $n = [int]$c
    $changed = (Invoke-Quiet git @("status", "--porcelain", "--untracked-files=no"))
    if ($changed) { $n = $n + 1 }
    return "$n"
}
function Get-Release {
    $m = Select-String -Path "services/api/version.toml" -Pattern '^version\s*=\s*"(.*)"' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($m) { return $m.Matches[0].Groups[1].Value } else { return "?" }
}

function Get-ComposeArgs([string[]]$Arguments) {
    if (-not (Test-Path $EnvFile)) { throw "No $EnvFile yet: run .\eax init first." }
    $env:EAX_BUILD = Get-BuildId
    if (-not $env:EAX_COMMIT) { $env:EAX_COMMIT = "$(Invoke-Quiet git @("rev-parse", "HEAD"))".Trim() }
    if (-not $env:EAX_BUILT_AT) { $env:EAX_BUILT_AT = "$(Invoke-Quiet git @("log", "-1", "--format=%cI"))".Trim() }
    Write-ServiceEnv
    if ($Arguments.Count -gt 0 -and @("up", "run", "create") -contains $Arguments[0]) { Use-DataFolders }
    $kind = Get-Setting "EAX_DEPLOYMENT" "laptop"
    # plain progress and no colour codes, so the log reads cleanly
    # scale-out extra files (phase 36.3, D521): EAX_COMPOSE_EXTRA=standby,shared-storage... (deploy/compose/scale)
    $extra = @()
    foreach ($x in ((Get-Setting "EAX_COMPOSE_EXTRA" "") -split "[,\s]+" | Where-Object { $_ })) {
        $f = "deploy/compose/scale/docker-compose.$x.yml"
        if (-not (Test-Path $f)) { throw "EAX_COMPOSE_EXTRA names $x, but there is no $f." }
        $extra += @("-f", $f)
    }
    # certificate mode (R6-C1, D743): the services sign in to the database with EA Explorer's own certificates
    if ((Get-Setting "EAX_AUTH_MODE" "password") -eq "certificate") { $extra += @("-f", "deploy/compose/auth/docker-compose.certificate.yml") }
    return @("compose", "--ansi", "never", "--progress", "plain", "--env-file", $EnvFile,
             "-f", "docker-compose.yml", "-f", "deploy/compose/docker-compose.$kind.yml") + $extra + $Arguments
}

function Invoke-Compose([string[]]$Arguments, [switch]$NoThrow, [switch]$Quiet) {
    $code = Invoke-Logged "docker" (Get-ComposeArgs $Arguments) -Quiet:$Quiet
    if ($code -ne 0 -and -not $NoThrow) {
        Write-Log "docker compose failed (exit $code). Collecting diagnostics..." "Red"
        Save-Diagnostics
        throw "docker compose failed (exit $code). Full log with diagnostics: $script:LogPath"
    }
    return $code
}

# Versions, containers, images, every container's recent log and the (masked) config, into the log
function Save-Diagnostics {
    Write-Log ""
    Write-Log "==================== DIAGNOSTICS $(Get-Date -Format o) ===================="
    Invoke-Logged "docker" @("version") -Quiet | Out-Null
    Invoke-Logged "docker" @("compose", "version") -Quiet | Out-Null
    Invoke-Logged "docker" @("info", "--format", "CPUs {{.NCPU}}  Memory {{.MemTotal}}  Storage {{.Driver}}  OS {{.OperatingSystem}}") -Quiet | Out-Null
    Invoke-Logged "docker" @("system", "df") -Quiet | Out-Null
    if (Test-Path $EnvFile) {
        if ($script:Log) {
            $script:Log.WriteLine(""); $script:Log.WriteLine("> settings in $EnvFile (images, site, deployment)")
            Get-Content $EnvFile | Where-Object { $_ -match "^EAX_(IMAGE_|DEPLOYMENT|HOSTNAME|HTTPS?_PORT|VERSION)|^COMPOSE_" } | ForEach-Object { $script:Log.WriteLine($_) }
        }
        Invoke-Logged "docker" (Get-ComposeArgs @("ps", "-a")) -Quiet | Out-Null
        Invoke-Logged "docker" (Get-ComposeArgs @("images")) -Quiet | Out-Null
        $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        $services = Invoke-Quiet docker @(Get-ComposeArgs @("config", "--services"))
        $ErrorActionPreference = $old
        foreach ($s in $services) {
            if ($s) { Invoke-Logged "docker" (Get-ComposeArgs @("logs", "--no-color", "--timestamps", "--tail", "300", $s)) -Quiet -Mask | Out-Null }
        }
        Invoke-Logged "docker" (Get-ComposeArgs @("config")) -Quiet -Mask | Out-Null
    } else {
        Write-Log "No ${EnvFile}: run .\eax init first."
    }
    Write-Log "==================== END DIAGNOSTICS ===================="
    Write-Log "Diagnostics saved in $script:LogPath" "Yellow"
}

# ------------------------------------------------------------------ optional services (D191)
# name: setting, compose services in start order (mcp and change_log run inside the api container)
$Services = [ordered]@{
    "reports"    = @("EAX_SERVICE_REPORTS", @("reports-init", "reports"))
    "documents"  = @("EAX_SERVICE_DOCUMENTS", @("dms-broker", "dms"))
    "drawio"     = @("EAX_SERVICE_DRAWIO", @("drawio"))
    "mcp"        = @("EAX_SERVICE_MCP", @("api"))
    "change_log" = @("EAX_SERVICE_CHANGE_LOG", @("api"))
    "backups"    = @("EAX_SERVICE_BACKUPS", @("backup"))
    "library"    = @("EAX_SERVICE_LIBRARY", @("library"))
    "views"      = @("EAX_SERVICE_VIEWS", @("views"))
}
function Test-ServiceOn([string]$Name) {
    $default = if ($Name -eq "mcp") { Get-Setting "EAX_MCP_ENABLED" "on" } else { "on" }
    $v = (Get-Setting $Services[$Name][0] $default).ToLower()
    return -not ($v -in @("off", "false", "0", "no", "disabled"))
}
# work\services.env: the switches only (no secrets), read by the api container
function Write-ServicesFile {
    $lines = @("# Written by EA Explorer from eaexplorer.env: the service switches only (D191). Do not edit; change eaexplorer.env.")
    foreach ($n in $Services.Keys) { $lines += "$($Services[$n][0])=$(if (Test-ServiceOn $n) { 'on' } else { 'off' })" }
    [System.IO.File]::WriteAllText((Join-Path $WorkDir "services.env"), (($lines -join "`n") + "`n"), $Utf8)
}
# compose services of the switched-off optional services (not the api, which stays on)
function Get-OffContainers {
    $off = @()
    foreach ($n in $Services.Keys) { if (-not (Test-ServiceOn $n) -and $Services[$n][1][0] -ne "api") { $off += $Services[$n][1] } }
    return $off
}
# up (all services): starts everything but the switched-off services; those are created, not started, so the
# console can switch them on later
# how many API and job servers (copies of the api container) run (D249): 1 to 16, 1 when not set
function Get-ApiServers {
    $n = 1
    if (-not [int]::TryParse((Get-Setting "EAX_API_SERVERS" "1"), [ref]$n)) { $n = 1 }
    return [Math]::Max(1, [Math]::Min(16, $n))
}
# The start-up in two tiers (D255): the core first (database, set-up, proxy, screens, sign-in, the API with the database
# upgrade and the built-in models), so people can sign in in a minute or two; everything else after it, in the
# background (Reports, Documents, draw.io, backups, the operations helper), while the API loads the sample data and
# measures data quality. The screens show each part red, amber or green (down, starting, up).
$CoreServices = @("db", "setup", "proxy", "web", "keycloak", "api")
function Get-Tiers {
    $off = @(Get-OffContainers)
    $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    $all = @(Invoke-Quiet docker @(Get-ComposeArgs @("config", "--services")) | Where-Object { $_ })
    $ErrorActionPreference = $old
    $on = @($all | Where-Object { $_ -notin $off })
    return @{ First = @($on | Where-Object { $_ -in $CoreServices }); Later = @($on | Where-Object { $_ -notin $CoreServices }); Off = $off }
}
# one look at the containers failed because Windows could not start docker.exe (out of memory: "The paging file is too
# small"); said once per minute, with what helps, and the wait goes on (R5.41)
$script:DockerMissAt = [datetime]::MinValue
function Write-DockerMiss($err) {
    if (((Get-Date) - $script:DockerMissAt).TotalSeconds -lt 60) { return }
    $script:DockerMissAt = Get-Date
    Write-Log "  Windows could not start docker just now ($($err.Exception.Message.Split([Environment]::NewLine)[0])); trying again." "Yellow"
    Write-Log "  If this keeps happening the laptop is short of memory: close other programs, or let Windows grow its paging file (System > About > Advanced system settings > Performance > Virtual memory)." "Yellow"
}
# waits until the API (every copy) and Keycloak say healthy; shows each change; false when one stopped or it took too long
function Wait-Core([int]$Minutes = 15) {
    $until = (Get-Date).AddMinutes($Minutes)
    $last = ""
    while ((Get-Date) -lt $until) {
        $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        # R5.41: Windows could not start docker.exe for one look ("The paging file is too small", 16 Nov 2026): that
        # look is skipped and the wait goes on, instead of stopping the whole clean-restart
        try { $rows = @(Invoke-Quiet docker @(Get-ComposeArgs @("ps", "-a", "--format", "{{.Name}}|{{.State}}|{{.Health}}", "api", "keycloak")) | Where-Object { $_ -match "\|" }) }
        catch { $rows = @(); Write-DockerMiss $_ }
        $ErrorActionPreference = $old
        $now = ($rows | ForEach-Object { $p = $_ -split "\|"; "$($p[0]): $(if ($p[2]) { $p[2] } else { $p[1] })" }) -join ", "
        if ($now -and $now -ne $last) { Write-Log "  $now"; $last = $now }
        if ($rows.Count -ge 2 -and -not ($rows | Where-Object { ($_ -split "\|")[2] -ne "healthy" })) { return $true }
        if ($rows | Where-Object { ($_ -split "\|")[1] -in @("exited", "dead") }) {
            Write-Log "A core container stopped; see .\eax logs api (or keycloak)." "Red"
            return $false
        }
        Start-Sleep -Seconds 5
    }
    Write-Log "The API or sign-in was not ready after $Minutes minutes; see .\eax logs api (or keycloak)." "Yellow"
    return $false
}
# --wait-all: waits until every part is up (the API's start-up status, D255): Reports, Documents, Diagrams, the sample data
function Wait-All([int]$Minutes = 30) {
    $until = (Get-Date).AddMinutes($Minutes)
    $t0 = Get-Date
    $last = ""
    $py = "import json,urllib.request as u; d=json.load(u.urlopen('http://localhost:8000/api/startup',timeout=20)); print(d['overall']+'|'+', '.join(p['key']+': '+p['status'] for p in d['parts']))"
    Write-Log "Waiting for everything: Reports, Documents, Diagrams and the sample data (up to $Minutes minutes)..."
    while ((Get-Date) -lt $until) {
        $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        try { $now = @(Invoke-Quiet docker @(Get-ComposeArgs @("exec", "-T", "api", "python", "-c", $py)) | Where-Object { $_ -match "\|" }) | Select-Object -Last 1 }
        catch { $now = $null; Write-DockerMiss $_ }
        $ErrorActionPreference = $old
        if ($now -and $now -ne $last) { Write-Log "  $(($now -split '\|', 2)[1])"; $last = $now }
        if ($now -like "up|*") { Write-Log "Everything is up after $([int]((Get-Date) - $t0).TotalSeconds) s." "Green"; return }
        if ($now -like "down|*" -and $now -notmatch "starting") {
            Write-Log "Started, but not everything is up (see above): .\eax logs <service>." "Yellow"; return
        }
        Start-Sleep -Seconds 10
    }
    Write-Log "Not everything was up after $Minutes minutes (see above); EA Explorer is usable, the rest may still come." "Yellow"
}
# the second tier, in a hidden PowerShell of its own with its own log, so this window is free at once
function Start-Later {
    $p = @{ FilePath = (Get-Process -Id $PID).Path; WorkingDirectory = $PSScriptRoot
            ArgumentList = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`"", "start-later") }
    if (-not ($IsLinux -or $IsMacOS)) { $p.WindowStyle = "Hidden" }   # Windows only; elsewhere it has no window anyway
    Start-Process @p | Out-Null
    Write-Log "Reports, documents, draw.io, backups and the operations helper start now in the background (log: work\logs\eax-*-start-later.log)."
}
function Invoke-Up([string[]]$Names, [switch]$NoThrow) {
    Write-ServicesFile
    $scale = @("--scale", "api=$(Get-ApiServers)")
    if ($Names.Count -gt 0) {
        if ($Names -contains "api") { return (Invoke-Compose (@("up", "-d", "--build") + $scale + $Names) -NoThrow:$NoThrow) }
        return (Invoke-Compose (@("up", "-d", "--build") + $Names) -NoThrow:$NoThrow)
    }
    if ((Get-Setting "EAX_IMAGES_FROM" "") -eq "registry") {   # made from the deploy repository: our images pulled (D973)
        $pullArgs = @("images", "pull"); if ($env:EAX_BUILD_PULL -ne "1") { $pullArgs += "--missing" }
        & (Join-Path $PSScriptRoot "eaxpy.ps1") @pullArgs
        if ($LASTEXITCODE -ne 0) { if ($NoThrow) { return 1 }; throw "Not every image could be pulled (see above)." }
    } elseif ($env:EAX_BUILD_PULL -eq "1") {   # a clean rebuild: fresh base images, with their fixes (R3.12, D673)
        Write-Log "Fetching the current base images and building on them (a clean rebuild)..." "Cyan"
        Invoke-Compose @("pull", "--ignore-buildable", "--quiet") -NoThrow | Out-Null
        # --no-cache too (D951): an unchanged base image kept the Debian fixes' layer built before, without newer fixes
        $code = Invoke-Compose @("build", "--pull", "--no-cache") -NoThrow:$NoThrow
        if ($code -ne 0) { return $code }
    }
    $t = Get-Tiers
    if ($t.Off.Count -gt 0) { Write-Log "Switched off (D191): $($t.Off -join ', '): created, not started." }
    Write-Log "Starting the core first (D255): $($t.First -join ', ')" "Cyan"
    $code = Invoke-Compose (@("up", "-d", "--build") + $scale + $t.First) -NoThrow:$NoThrow
    if ($code -ne 0) { return $code }
    Write-Log "Waiting for the API and sign-in to be ready (the database upgrade and the built-in models come first)..."
    $started = Get-Date
    $ready = Wait-Core
    if ($WaitAll) {          # --wait-all: the rest now, in this window, and wait until everything is up
        Invoke-Later
        Wait-All
        return 0
    }
    Start-Later
    Write-Log "(To wait for everything instead: .\eax up --wait-all.)"
    if ($ready) {
        Write-Log "EA Explorer is ready after $([int]((Get-Date) - $started).TotalSeconds) s: you can sign in." "Green"
        Write-Log "Still starting in the background: Reports, Documents, Diagrams and the sample data; the screens show each in red, amber or green (down, starting, up)." "Green"
        $hint = Join-Path $WorkDir ".check-hint-shown"
        if (-not (Test-Path $hint)) {   # the first start: how to check it (D582)
            Write-Log "Check your installation: System admin > Self-test > Smoke test > Start (it prepares what it needs);"
            Write-Log "  or .\eax test (smoke) or .\eax test full."
            Write-Log "  Results: Self-test > History and the report. Steps: docs\deployment.md, 'Check your installation'."
            New-Item -ItemType File -Path $hint -Force -ErrorAction SilentlyContinue | Out-Null
        }
    }
    return 0
}
# Containers that are not part of running EA Explorer (owner, 19 Nov 2026, 05:45: "ensure sonar and other non essential
# containers do not come up during regular operations"): SonarQube and its scanner (eax test sonar), k6 (the load test),
# the platform's always-on test runner (only for a managed platform, profile "platform") and a test run that has finished.
# A container of a profile that is not switched on is left alone by compose's own down and, with a restart policy,
# comes back whenever Docker starts; so up and down remove them (their data volumes kept). A running test is never stopped.
$ExtraContainers = @("sonarqube", "sonar-scanner", "k6", "testrunner-service")
function Remove-Extras {
    $all = @("--profile", "test", "--profile", "platform")
    $names = @($ExtraContainers)
    $running = @(Invoke-Quiet docker @(Get-ComposeArgs ($all + @("ps", "--status", "running", "-q", "testrunner"))) | Where-Object { $_ })
    if ($running.Count -eq 0) { $names += "testrunner" }
    Invoke-Compose ($all + @("rm", "-s", "-f") + $names) -NoThrow -Quiet | Out-Null
    # a test's own containers (scanners, k6) its run left behind; a run still going (its heartbeat fresh) keeps them
    # no double quotes in the format: Windows PowerShell 5.1 drops them on the way to docker, which then refuses the
    # format and ends with 1, failing down and up (owner, 22 Nov 2026, 07:49); so every label, and ours read from them
    $listed = @(Invoke-Quiet docker @("ps", "-a", "--filter", "label=eaexplorer.test", "--format", "{{.Names}} {{.Labels}}") | Where-Object { $_ })
    foreach ($line in $listed) {
        $name, $labels = ("$line".Trim() -split " ", 2)
        $folder = if ("$labels" -match '(?:^|,)eaexplorer\.test=([^,]*)') { $Matches[1] } else { "" }
        $beat = if ($folder -and $folder -match '^[A-Za-z0-9._-]+$') { Join-Path (Join-Path (Join-Path $WorkDir "tests") $folder) ".alive" } else { "" }
        $fresh = $beat -and (Test-Path $beat) -and (((Get-Date) - (Get-Item $beat).LastWriteTime).TotalSeconds -lt 180)
        if (-not $fresh) { Invoke-Quiet docker @("rm", "-f", $name) | Out-Null }
    }
    $global:LASTEXITCODE = 0   # tidying up is best effort: what it could not remove never fails down or up
}
# start-later: the second tier (run by Start-Later): the rest without touching the core, then the switched-off ones created
function Invoke-Later {
    $t = Get-Tiers
    if ($t.Later.Count -gt 0) {
        Write-Log "Starting after the core (D255): $($t.Later -join ', ')"
        Invoke-Compose (@("up", "-d", "--build", "--no-deps") + $t.Later) -NoThrow | Out-Null
    }
    if ($t.Off.Count -gt 0) {
        Invoke-Compose (@("create", "--build") + $t.Off) -NoThrow | Out-Null
        Invoke-Compose (@("stop") + $t.Off) -NoThrow -Quiet | Out-Null
    }
    Remove-Extras      # nothing that is not part of running EA Explorer (test, scan and platform containers)
    Write-Log "Everything is started."
}
# the file systems after the containers (owner, 8 Nov 2026): Docker's disk and the work and backups folders, read by
# the operations helper; and this computer's drive the project sits on, read here (so it shows with the helper down too)
function Show-FileSystems {
    Write-Log ""
    $ops = @(Invoke-Quiet docker @(Get-ComposeArgs @("ps", "--status", "running", "-q", "ops")) | Where-Object { $_ })
    if ($ops.Count -gt 0) {
        Invoke-Quiet docker @(Get-ComposeArgs @("exec", "-T", "ops", "python3", "/app/ops.py", "filesystems")) | ForEach-Object { Write-Log $_ }
    } else {
        Write-Log "File systems: the operations helper is not running, so Docker's disk is not read (docker system df below)." "Yellow"
        Invoke-Quiet docker @("system", "df") | ForEach-Object { Write-Log "  $_" }
    }
    try {
        $drive = Get-PSDrive -Name ((Split-Path -Qualifier $PSScriptRoot).TrimEnd(":")) -ErrorAction Stop
        $total = $drive.Used + $drive.Free
        if ($total -gt 0) {
            $pct = [math]::Round($drive.Used / $total * 100, 1)
            $color = if ($pct -ge 90) { "Red" } elseif ($pct -ge 80) { "Yellow" } else { "" }
            Write-Log ("  This computer's drive {0}: {1:N1} GB, {2:N1} GB used, {3:N1} GB free ({4}% used)" -f $drive.Name, ($total / 1e9), ($drive.Used / 1e9), ($drive.Free / 1e9), $pct) $color
        }
    } catch { }
}

function Show-Services {
    foreach ($n in $Services.Keys) {
        $state = if (Test-ServiceOn $n) { "on " } else { "off" }
        Write-Log ("{0,-11} {1}   {2} = {3}   containers: {4}" -f $n, $state, $Services[$n][0], (Get-Setting $Services[$n][0] "on"), ($Services[$n][1] -join ", "))
    }
    Invoke-Compose @("ps", "-a") | Out-Null
}
function Set-Service([string]$Name, [string]$Value) {
    if (-not $Services.Contains($Name)) { throw "Unknown service '$Name'. One of: $($Services.Keys -join ', ')" }
    if ($Value -notin @("on", "off")) { throw "Say on or off: .\eax service $Name on" }
    $history = Join-Path $WorkDir "config-history"
    New-Item -ItemType Directory -Force -Path $history | Out-Null
    $copy = "eaexplorer.env.$((Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmss')).$($env:USERNAME -replace '[^A-Za-z0-9_.-]', '-').$Name-$Value"
    Copy-Item $EnvFile (Join-Path $history $copy)
    $setting = $Services[$Name][0]
    $lines = @(Get-Content $EnvFile | Where-Object { -not ($Name -eq "mcp" -and $_ -match "^\s*EAX_MCP_ENABLED\s*=") })
    if ($lines | Where-Object { $_ -match "^\s*$setting\s*=" }) {
        $lines = @($lines | ForEach-Object { if ($_ -match "^\s*$setting\s*=") { "$setting=$Value" } else { $_ } })
    } else { $lines += @("", "$setting=$Value") }
    [System.IO.File]::WriteAllText((Join-Path $PSScriptRoot $EnvFile), (($lines -join "`n") + "`n"), $Utf8)
    Write-ServicesFile
    Write-Log "$setting=$Value written (the config file before is kept as work\config-history\$copy)."
    $names = $Services[$Name][1]
    if ($names[0] -eq "api") { Invoke-Compose @("restart", "api") | Out-Null }
    elseif ($Value -eq "on") { Invoke-Compose (@("up", "-d") + $names) | Out-Null }
    else { Invoke-Compose (@("stop") + $names) | Out-Null }
}

# ------------------------------------------------------------------ output helpers
function Show-Urls {
    $h = Get-Setting "EAX_HOSTNAME" "localhost"; $p = Get-Setting "EAX_HTTPS_PORT" "443"
    $s = if ($p -eq "443") { "" } else { ":$p" }
    Write-Log "Start page:  https://$h$s/"
    Write-Log "Swagger:     https://$h$s/api/docs"
    if (Test-ServiceOn "reports") { Write-Log "Reports:     https://reports.$h$s/" }
    if (Test-ServiceOn "documents") { Write-Log "Documents:   https://docs.$h$s/" }
    Write-Log "Keycloak:    https://$h$s/auth/admin/"
    if (Test-ServiceOn "mcp") { Write-Log "MCP server:  https://$h$s/mcp" }
    if ((Get-Setting "EAX_HTTP_API_MCP" "false") -eq "true") {
        $hp = Get-Setting "EAX_HTTP_PORT" "80"; $hs = if ($hp -eq "80") { "" } else { ":$hp" }
        Write-Log "Also on plain http (this computer only): http://localhost$hs/api/docs and http://localhost$hs/mcp"
    }
    Show-TrustHint
    Show-TemplatesHint
}
# one-time admin task (phase 13, D262): the TOGAF template deliverables are bought or downloaded from The Open Group
# (publication I094) and kept in the library folder, never in git; shown until the folder has them
function Show-TemplatesHint {
    $dir = Get-Setting "EAX_LIBRARY_DIR" "./library"
    $togaf = Join-Path (Join-Path $dir "templates") "togaf"
    $have = @(Get-ChildItem -Path $togaf -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension -in @(".docx", ".doc", ".pptx", ".xlsx") })
    if ($have.Count -gt 0) { return }
    Write-Log ""
    Write-Log "One-time admin task: the TOGAF template deliverables (for architecture projects)" "Yellow"
    Write-Log "  1. Download 'The TOGAF Standard, 10th Edition - Template Deliverables' (The Open Group publication I094):" "Yellow"
    Write-Log "     https://publications.opengroup.org/i094" "Yellow"
    Write-Log "  2. Unzip it into $togaf, keeping its phase folders (the files stay on this computer; git ignores them)." "Yellow"
    Write-Log "     To use another folder, set EAX_LIBRARY_DIR in $EnvFile (it must hold templates\togaf) and run .\eax up." "Yellow"
    Write-Log "  3. As a Super Admin: Administration > Project library > Load templates from the folder." "Yellow"
}

# ------------------------------------------------------------------ the local certificate (D107)
# The setup service makes a local certificate authority (ca.crt) and signs the site certificate with it.
# "trust" adds ca.crt to this Windows user's trusted root certificates (Windows asks you to confirm),
# after removing earlier EA Explorer ones, so Edge, Chrome and Windows tools trust https://localhost.
function Get-CaPath {
    $d = Get-Setting "EAX_TLS_DIR" "./work/data/tls"
    if ($d -notmatch '[\\/]') { throw "EAX_TLS_DIR is the Docker volume '$d', not a folder: copy ca.crt out with docker compose cp setup:/tls/ca.crt ." }
    return Join-Path (Join-Path $PSScriptRoot $d) "ca.crt"
}
function Get-OurCas { Get-ChildItem Cert:\CurrentUser\Root | Where-Object { $_.Subject -like "*O=EA Explorer (self-signed)*" } }
function Show-TrustHint {
    try { $ca = Get-CaPath } catch { return }
    if (-not (Test-Path $ca)) { return }
    $want = (New-Object System.Security.Cryptography.X509Certificates.X509Certificate2 $ca).Thumbprint
    if (-not (Get-OurCas | Where-Object { $_.Thumbprint -eq $want })) {
        Write-Log "Optional: run  .\eax trust  once so the browser stops warning about the certificate (it survives clean-run)." "Yellow"
        Write-Log "Without it, accept the warning once for localhost, reports.localhost and docs.localhost, as before." "Yellow"
    }
}
function Invoke-Trust([string[]]$Options) {
    $ca = Get-CaPath
    if ($Options -contains "--remove") {
        $old = @(Get-OurCas); $old | Remove-Item
        Write-Log "Removed $($old.Count) EA Explorer certificate(s) from your trusted root certificates."
        return
    }
    if (-not (Test-Path $ca)) { throw "No $ca yet: run .\eax up first (the setup service makes it)." }
    $new = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2 $ca
    Get-OurCas | Where-Object { $_.Thumbprint -ne $new.Thumbprint } | Remove-Item
    if (Get-OurCas | Where-Object { $_.Thumbprint -eq $new.Thumbprint }) { Write-Log "Already trusted: $($new.Subject)" }
    else {
        Write-Log "Adding $($new.Subject) to your trusted root certificates. Windows asks you to confirm: choose Yes." "Yellow"
        Import-Certificate -FilePath $ca -CertStoreLocation Cert:\CurrentUser\Root | Out-Null
        Write-Log "Trusted. Restart the browser. It may vouch only for this installation's names (localhost and EAX_HOSTNAME)."
    }
    Write-Log "Firefox: set security.enterprise_roots.enabled to true in about:config, or import $ca there."
    Write-Log "MCP clients that run on Node (Claude Code, mcp-remote): setx NODE_EXTRA_CA_CERTS `"$ca`"  and open a new window."
}

function Show-Logins {
    if ((Get-Setting "EAX_DEPLOYMENT" "laptop") -ne "laptop") {
        Write-Log "Logins are only printed for a laptop (development) installation. See $EnvFile."
        return
    }
    $rows = @(
        @("EA Explorer (Keycloak realm)",     (Get-Setting "EAX_FIRST_ADMIN_USER" "eaadmin"), (Get-Setting "EAX_FIRST_ADMIN_PASSWORD"),    "start page sign-in; Superset and Mayan via SSO"),
        @("Keycloak administrator",           (Get-Setting "EAX_KC_ADMIN" "kcadmin"),         (Get-Setting "EAX_KC_ADMIN_PASSWORD"),       "/auth/admin/ (master realm)"),
        @("Superset break-glass admin",       "admin",                                        (Get-Setting "EAX_SUPERSET_ADMIN_PASSWORD"), "only when EAX_SUPERSET_AUTH=db"),
        @("Mayan EDMS administrator",         (Get-Setting "EAX_MAYAN_ADMIN_USER" "admin"),   (Get-Setting "EAX_MAYAN_ADMIN_PASSWORD"),    "local Mayan account"),
        @("PostgreSQL superuser",             "postgres",                                     (Get-Setting "EAX_DB_SUPERUSER_PASSWORD"),   "docker compose exec db psql -U postgres"),
        @("PostgreSQL EA Explorer",           "eax_app",                                      (Get-Setting "EAX_DB_PASSWORD"),             "database $(Get-Setting 'EAX_DB_NAME' 'eaexplorer')"),
        @("PostgreSQL reporting (read only)", "eax_report",                                   (Get-Setting "EAX_DB_REPORT_PASSWORD"),      "schema rpt"),
        @("PostgreSQL installer",             "eax_migrator",                                 (Get-Setting "EAX_DB_MIGRATOR_PASSWORD"),    "loads reference models only"),
        @("PostgreSQL Keycloak",              "keycloak",                                     (Get-Setting "EAX_KEYCLOAK_DB_PASSWORD"),    "database keycloak"),
        @("PostgreSQL Superset",              "superset",                                     (Get-Setting "EAX_SUPERSET_DB_PASSWORD"),    "database superset"),
        @("PostgreSQL Mayan",                 "mayan",                                        (Get-Setting "EAX_MAYAN_DB_PASSWORD"),       "database mayan"),
        @("PostgreSQL Library",               "eax_library",                                  (Get-Setting "EAX_LIBRARY_DB_PASSWORD"),     "database eaxlibrary"),
        @("PostgreSQL Views",                 "eax_views",                                    (Get-Setting "EAX_VIEWS_DB_PASSWORD"),       "database eaxviews"),
        @("Mayan broker (Valkey)",            "(none)",                                       (Get-Setting "EAX_DMS_BROKER_PASSWORD"),     "password only"),
        @("MCP server (development token)",   "(bearer)",                                     (Get-Setting "EAX_MCP_DEV_TOKEN"),           "https://localhost/mcp or http://localhost/mcp"),
        @("Keycloak client secrets",          "superset/mayan",                               (Get-Setting "EAX_SUPERSET_OIDC_SECRET"),    "OIDC clients"),
        @("Keycloak API client (eax-admin)",  "eax-admin",                                    (Get-Setting "EAX_KC_SERVICE_SECRET"),       "reads people and roles"),
        @("Break-glass account",              "break-glass",                                  (Get-Setting "EAX_BREAK_GLASS_PASSWORD"),    "when Keycloak is down: start page")
    )
    # Test users (phase 3.1): their global Keycloak role and the model roles the seed gives them
    $testPw = Get-Setting "EAX_TEST_USER_PASSWORD" ""
    if (-not $testPw) { $testPw = Get-Setting "EAX_FIRST_ADMIN_PASSWORD" }
    $tests = @(
        @("user_super_admin", "eax-super-admin", "everything, every model"),
        @("user_it_admin", "eax-it-admin", "runs the installation; no models"),
        @("user_keycloak_admin", "eax-keycloak-admin", "Keycloak console of the realm"),
        @("user_user_admin", "eax-user-admin", "Users page, role mapping; reads no model"),
        @("user_library_admin", "eax-library-admin", "curates the model library: create, publish, promote, upload, withdraw"),
        @("user_model_creator", "eax-model-creator", "creates models; Model Admin: Karoo Re, Lean EA metamodel, Karoo Digital"),
        @("user_model_admin", "eax-user", "Model Admin: Fynbos group, Fynbos Life, Protea demo; Architect: Sample"),
        @("user_architect", "eax-user", "Architect: Sample, Fynbos Life, Protea demo; Model Sub Admin + Report Viewer: Fynbos Commercial"),
        @("user_model_sub_admin", "eax-user", "Model Sub Admin: Sample, Fynbos Life, Fynbos Commercial, Karoo Re"),
        @("user_committer", "eax-user", "Committer: Protea demo, Sample (commits what others ask to commit)"),
        @("user_history_viewer", "eax-user", "History Viewer and Report Viewer: Protea demo (sees everyone's commits)"),
        @("user_report_viewer", "eax-user", "Report Viewer: Fynbos group, Sample, Protea demo"),
        @("user_global_architect", "eax-user", "Architect on every model"),
        @("user_project_admin", "eax-user", "Project Admin of the sample architecture project (runs its setup and people)"),
        @("user_lead_architect", "eax-user", "Lead Architect of the sample architecture project"),
        @("user_stakeholder", "eax-user", "Stakeholder of the sample architecture project (reads; approves documents in 13.1)")
    )
    foreach ($t in $tests) { $rows += ,@("Test user ($($t[1]))", $t[0], $testPw, $t[2]) }
    # Write-Host, never Write-Log: no password goes in a log (D975)
    Write-Host ""
    Write-Host "================ DEVELOPMENT LOGINS (laptop only - never use these on a server) ================" -ForegroundColor Yellow
    Write-Host ("{0,-38} {1,-22} {2,-16} {3}" -f "Account", "User", "Password", "Notes")
    foreach ($r in $rows) { Write-Host ("{0,-38} {1,-22} {2,-16} {3}" -f $r[0], $r[1], $r[2], $r[3]) }
    Write-Host "=================================================================================================" -ForegroundColor Yellow
    if ($script:Log) { $script:Log.WriteLine("(the logins were shown on the screen; they are not written to this log, D975)") }
}

# After starting only some services: where to reach them directly (laptop)
function Show-PartUrls([string[]]$Services) {
    Write-Log ""
    Write-Log "Started: $($Services -join ', ') (and what they depend on). The rest stays stopped."
    if ($Services -contains "api") {
        Write-Log "The API goes through nginx: start it too with  .\eax up api proxy  (no Keycloak needed for public endpoints):"
        Write-Log "  Swagger:    https://localhost/api/docs   (laptop also http://localhost/api/docs)"
        Write-Log "  Heartbeat:  https://localhost/api/v1/heartbeat"
    }
    Write-Log "Stop everything with .\eax down"
}

# Follows every container's log into logs\containers-<stamp>.log (and the console) until Ctrl+C
function Watch-Containers([string[]]$Services = @()) {
    $path = Join-Path $LogDir "containers-$Stamp.log"
    Write-Log ""
    Write-Log "Recording every container's log to $path" "Yellow"
    Write-Log "Leave this window open while you test; press Ctrl+C to stop recording (the containers keep running)." "Yellow"
    $w = Open-Writer $path
    $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    try {
        & docker @(Get-ComposeArgs (@("logs", "-f", "--no-color", "--timestamps", "--tail", "500") + $Services)) 2>&1 | ForEach-Object {
            $raw = if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { "$_" }
            $line = Hide-Secrets $raw
            Write-Host $line
            $w.WriteLine($line)
        }
    } finally { $ErrorActionPreference = $old; $w.Dispose() }
}

# Stops early with a plain message when the Docker engine is not reachable
function Assert-Docker {
    $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    & docker info --format "{{.ServerVersion}}" 2>&1 | Out-Null
    $ok = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $old
    if (-not $ok) {
        throw "Docker Desktop is not running (or still starting). Start Docker Desktop, wait until it shows 'Engine running', check with: docker version (it must show a Server section), then run this again."
    }
}

# ------------------------------------------------------------------ help
# The help is read from eaxcli\help.txt, the one source for every form of eax (D331; tests/test_eax_help.py):
# Show-Help prints the overview, one command in full (Show-Help stop) or everything (Show-Help --all).
function Get-HelpText([string]$Name, [string]$Arg = "") {
    $src = [System.IO.File]::ReadAllLines((Join-Path $PSScriptRoot "eaxcli\help.txt"), [System.Text.Encoding]::UTF8)
    $intro = New-Object 'System.Collections.Generic.List[string]'
    $footer = New-Object 'System.Collections.Generic.List[string]'
    $sections = New-Object 'System.Collections.Generic.List[object]'
    $internal = New-Object 'System.Collections.Generic.List[object]'
    $where = "intro"; $cmd = $null
    foreach ($raw in $src) {
        $line = $raw.TrimEnd()
        if ($line.StartsWith(";")) { continue }
        if ($line -match '^\[(win|unix|ps1|sh|py)\]') {
            if ($Matches[1] -notin @("ps1", "win")) { continue }
            $line = $line.Substring($Matches[0].Length); if ($line.StartsWith(" ")) { $line = $line.Substring(1) }
        }
        if ($where -eq "footer") { $footer.Add($line); continue }
        if ($line -eq "@footer") { $where = "footer"; continue }
        if ($line.StartsWith("@internal ")) {
            $r = $line.Substring(10); $p = $r.IndexOf(" ")
            $internal.Add(@{ Name = $r.Substring(0, $p); What = $r.Substring($p + 1) }); continue
        }
        if ($line.StartsWith("## ")) {
            $sections.Add(@{ Title = $line.Substring(3); Notes = (New-Object 'System.Collections.Generic.List[string]'); Cmds = (New-Object 'System.Collections.Generic.List[object]') })
            $where = "section"; $cmd = $null; continue
        }
        if ($line.StartsWith("### ")) {
            $r = $line.Substring(4); $p = $r.IndexOf(" ")
            $names = if ($p -ge 0) { $r.Substring(0, $p) } else { $r }
            $cmd = @{ Names = @($names -split '\|'); Args = $(if ($p -ge 0) { $r.Substring($p + 1) } else { "" }); Summary = "";
                      Detail = (New-Object 'System.Collections.Generic.List[string]'); Examples = (New-Object 'System.Collections.Generic.List[string]') }
            $sections[$sections.Count - 1].Cmds.Add($cmd); continue
        }
        if ($where -eq "intro") { if ($line) { $intro.Add($line) }; continue }
        if ($line.StartsWith(": ") -and $null -eq $cmd) { $sections[$sections.Count - 1].Notes.Add($line.Substring(2)); continue }
        if ($null -eq $cmd) { continue }
        if ($line.StartsWith("> ")) { $cmd.Summary = $line.Substring(2) }
        elseif ($line.StartsWith('$ ')) { $cmd.Examples.Add($line.Substring(2)) }
        elseif ($line) { $cmd.Detail.Add($line) }
    }
    while ($footer.Count -gt 0 -and -not $footer[$footer.Count - 1]) { $footer.RemoveAt($footer.Count - 1) }
    $block = {
        param($c)
        $h = "  " + ((@($c.Names[0], $c.Args) | Where-Object { $_ }) -join " ")
        if ($c.Names.Count -gt 1) { $h += "   (also: " + (($c.Names | Select-Object -Skip 1) -join ", ") + ")" }
        $b = @($h, ("    " + $c.Summary))
        foreach ($d in $c.Detail) { $b += "    " + $d }
        if ($c.Examples.Count -gt 0) { $b += "    Examples:"; foreach ($e in $c.Examples) { $b += "      " + $e } }
        , $b
    }
    $out = @(); $code = 0
    $all = @(); foreach ($s in $sections) { foreach ($c in $s.Cmds) { $all += , @($s, $c) } }
    if ($Name -eq "--groups") {
        for ($i = 0; $i -lt $sections.Count; $i++) { $out += ("{0,4}  {1}" -f ($i + 1), $sections[$i].Title) }
    } elseif ($Name -eq "--group") {
        $n = 0; if ($Arg -match '^[0-9]+$') { $n = [int]$Arg }
        if ($n -lt 1 -or $n -gt $sections.Count) { $out = @("No group $Arg."); $code = 1 }
        else {
            $s = $sections[$n - 1]; $out += $s.Title
            foreach ($x in $s.Notes) { $out += "  " + $x }
            foreach ($c in $s.Cmds) { $out += ""; $out += & $block $c }
        }
    } elseif ($Name -eq "--search") {
        $w = $Arg.ToLower(); $found = $false
        foreach ($pair in $all) {
            $c = $pair[1]
            $t = ((@($c.Names) + @($c.Args, $c.Summary) + @($c.Detail) + @($c.Examples)) -join " ").ToLower()
            if ($w -and $t.Contains($w)) { if ($found) { $out += "" }; $out += & $block $c; $found = $true }
        }
        if (-not $found) { $out = @("Nothing found for '$Arg'."); $code = 1 }
    } elseif (-not $Name -or $Name -eq "--all") {
        $out += $intro
        foreach ($s in $sections) {
            $out += ""; $out += $s.Title
            foreach ($n in $s.Notes) { $out += "  " + $n }
            foreach ($c in $s.Cmds) {
                if ($Name) { $out += ""; $out += & $block $c; continue }
                $lab = (@(($c.Names -join ", "), $c.Args) | Where-Object { $_ }) -join " "
                if ($lab.Length -le 20) { $out += "  " + $lab.PadRight(22) + $c.Summary }
                else { $out += "  " + $lab; $out += (" " * 24) + $c.Summary }
            }
        }
        if ($Name -and $internal.Count -gt 0) {
            $out += ""; $out += "Internal (run by eax itself; not for typing)"
            foreach ($i in $internal) { $out += "  " + $i.Name.PadRight(22) + $i.What }
        }
        $out += ""; $out += $footer
    } else {
        $found = $false
        foreach ($s in $sections) { foreach ($c in $s.Cmds) { if (-not $found -and $c.Names -contains $Name) { $out = & $block $c; $found = $true } } }
        if (-not $found) { foreach ($i in $internal) { if (-not $found -and $i.Name -eq $Name) { $out = @(("  " + $i.Name), ("    " + $i.What)); $found = $true } } }
        if (-not $found) { $out = @("No command '$Name'. Run {eax} help to list them."); $code = 1 }
    }
    $text = ($out -join "`n").Replace("{eax}", ".\eax")
    $text = [regex]::Replace($text, '\bwork/[^\s,;)]*', [System.Text.RegularExpressions.MatchEvaluator] { param($m) $m.Value.Replace("/", "\") })
    @{ Text = $text; Code = $code }
}

# eax document (D331): every command in full, from eaxcli\help.txt, as a web page (eaxcli\document.html with the help
# copied in; eaxpy and eax.sh make the same file) or in the console (a menu of the groups, page by page)
function Save-DocumentPage {
    $page = [System.IO.File]::ReadAllText((Join-Path $PSScriptRoot "eaxcli\document.html"), [System.Text.Encoding]::UTF8).Replace("`r`n", "`n")
    $help = [System.IO.File]::ReadAllText((Join-Path $PSScriptRoot "eaxcli\help.txt"), [System.Text.Encoding]::UTF8).Replace("`r`n", "`n")
    if ($help.EndsWith("`n")) { $help = $help.Substring(0, $help.Length - 1) }
    $html = $page.Replace("__FORM__", "ps1").Replace("__EAX__", ".\eax").Replace("__WINDOWS__", "true").Replace("__HELP__", $help)
    $dir = Join-Path $PSScriptRoot "work\docs"
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $out = Join-Path $dir "eax-commands.html"
    [System.IO.File]::WriteAllText($out, $html, (New-Object System.Text.UTF8Encoding $false))
    Write-Host "The commands as a web page: $out"
    if (-not $env:EAX_NO_BROWSER) { Start-Process $out }
}

function Show-Paged([string]$Text) {
    $rows = 22
    try { $rows = [Math]::Max(10, $Host.UI.RawUI.WindowSize.Height - 2) } catch { }
    $n = 0
    foreach ($line in ($Text -split "`n")) {
        Write-Host $line; $n++
        if ($n -ge $rows -and -not [Console]::IsOutputRedirected) { $n = 0; $k = Read-Host "-- Enter for more, q to stop --"; if ($k -eq "q") { break } }
    }
}

function Invoke-Document([string[]]$Options) {
    $mode = if ($Options -contains "--console") { "console" } elseif ($Options -contains "--web") { "web" } else { "" }
    if (-not $mode) {
        $a = Read-Host "Show the commands (1) here in the console or (2) as a web page in your browser? [1/2]"
        $mode = if ($a -in @("2", "w", "web")) { "web" } else { "console" }
    }
    if ($mode -eq "web") { Save-DocumentPage; return }
    while ($true) {
        Write-Host ""; Write-Host "EA Explorer commands (.\eax document)" -ForegroundColor Cyan
        Write-Host (Get-HelpText "--groups").Text
        $a = Read-Host "Number, s to search, q to quit"
        if ($null -eq $a -or $a -in @("q", "Q")) { return }
        if ($a -in @("s", "S")) { $w = Read-Host "Search for"; if ($null -eq $w) { return }; Show-Paged (Get-HelpText "--search" $w).Text }
        elseif ($a -match '^[0-9]+$') { Show-Paged (Get-HelpText "--group" $a).Text }
        elseif ($a) { Write-Host "Choose a number, s or q." }
    }
}

function Show-Help([string]$Name, [string]$Arg = "") {
    $h = Get-HelpText $Name $Arg
    Write-Host $h.Text
    return $h.Code
}

# Backups and restores from the command line (D227): they talk to the operations helper and the backup container, so
# those (and the database) are started first if they are not running; the console is not needed.
function Start-BackupHelpers {
    Invoke-Compose @("up", "-d", "db", "backup", "ops") -Quiet | Out-Null
}
function Get-Version {
    return (Select-String -Path "services\api\version.toml" -Pattern '^version = "(.*)"').Matches[0].Groups[1].Value
}
# Runs a command in a container with this console attached, so it can ask (choose a backup, type RESTORE) and show
# progress as it comes; the restore keeps its own log in work\backups\restores
function Invoke-Interactive([string[]]$Target, [string[]]$Arguments) {
    Write-Log "> docker compose exec $($Target -join ' ') $($Arguments -join ' ')  (interactive: output in this window, not in this log)"
    $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    $rest = @($Arguments | Where-Object { $null -ne $_ -and $_ -ne "" })
    & docker @(Get-ComposeArgs (@("exec") + $Target + $rest))
    $code = $LASTEXITCODE
    $ErrorActionPreference = $old
    if ($code -ne 0) { throw "$($Target[0]) $($Target[2..($Target.Count - 1)] -join ' ') ended with exit $code" }
}

# Shows the maintenance page while up rebuilds a running installation (D230); only when the proxy runs already and the
# page is not on for another reason. Returns whether it switched it on.
function Set-UpgradePage([bool]$All) {
    if (-not $All -or (Test-Path "work/proxy/maintenance")) { return $false }
    $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    $running = @(Invoke-Quiet docker @(Get-ComposeArgs @("ps", "--status", "running", "-q", "proxy")) | Where-Object { $_ })
    $ErrorActionPreference = $old
    if ($running.Count -eq 0) { return $false }
    New-Item -ItemType Directory -Force -Path "work/proxy" | Out-Null
    [System.IO.File]::WriteAllText((Join-Path $PSScriptRoot "work/proxy/maintenance"), "upgrade`n", $Utf8)
    Write-Log "Everyone sees the maintenance page until this has finished."
    return $true
}

# Stops the containers and empties the work folder (no log: the logs folder is being deleted)
function Invoke-Cleanup([string[]]$Options) {
    $all = $false; $yes = $false; $cert = $false
    foreach ($o in $Options) {
        switch ($o) { "--all" { $all = $true } "--yes" { $yes = $true } "-y" { $yes = $true } "--certificate" { $cert = $true } default { throw "Unknown option $o" } }
    }
    Write-Host "This deletes everything in ${WorkDir}: the config file, all logs, the laptop data folders, and every backup and restore log (work\backups)." -ForegroundColor Yellow
    if ($all) { Write-Host "With --all it also deletes the Docker volumes: the databases and documents start empty." -ForegroundColor Yellow }
    if (-not $yes) {
        $answer = Read-Host "Type yes to continue"
        if ($answer -ne "yes") { Write-Host "Nothing deleted."; return }
    }
    # the logs first, where no reset deletes them (R2.30); a log backup never stops the cleanup
    # the Jenkins agent stopped first: it holds its log open in work\logs (owner's clean-restart, 18 Nov 2026, 09:49)
    if (Test-Path (Join-Path $WorkDir "jenkins\agent.pid")) { try { & (Join-Path $PSScriptRoot "eaxpy.ps1") jenkins stop-agent } catch { }; $global:LASTEXITCODE = 0 }
    # and any agent of this installation still running without its pid file (a cleanup stopped half way): found by its
    # command line, this folder's eaxpy.py with "jenkins agent", nothing else
    try {
        $mine = [regex]::Escape((Join-Path $PSScriptRoot "eaxpy.py"))
        Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object { $_.CommandLine -match $mine -and $_.CommandLine -match "jenkins\s+agent" } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; Write-Host "The Jenkins agent stopped." }
        Start-Sleep -Seconds 1
    } catch { }
    try { & (Join-Path $PSScriptRoot "eaxpy.ps1") logs backup before-cleanup --outside-work --then-clear } catch { Write-Host "The logs could not be backed up first." }
    if (Test-Path $EnvFile) {
        $down = if ($all) { @("down", "-v", "--remove-orphans") } else { @("down", "--remove-orphans") }
        Invoke-Logged "docker" (Get-ComposeArgs $down) | Out-Null
    } elseif ($all) {
        Write-Host "No $EnvFile, so the Docker volumes cannot be found by name; list them with: docker volume ls"
    }
    if (Test-Path $WorkDir) {
        # work\tools (uv and its Python, for eaxpy, D331) is kept either way
        if ($cert) { Get-ChildItem -Path $WorkDir -Force | Where-Object { $_.Name -ne "tools" } | Remove-Item -Recurse -Force }
        else {
            # keep work\data\tls: the local certificate you trusted with .\eax trust (D107)
            Get-ChildItem -Path $WorkDir -Force | Where-Object { $_.Name -notin @("data", "tools") } | Remove-Item -Recurse -Force
            $data = Join-Path $WorkDir "data"
            if (Test-Path $data) { Get-ChildItem -Path $data -Force | Where-Object { $_.Name -ne "tls" } | Remove-Item -Recurse -Force }
        }
    }
    foreach ($b in @((Join-Path $WorkDir "backups"), (Join-Path $WorkDir "data\backups"))) {
        if (Test-Path $b) { Remove-Item -Recurse -Force $b -ErrorAction SilentlyContinue }
    }
    if (Test-Path (Join-Path $WorkDir "backups")) { Write-Host "WARNING: work\backups could not be deleted completely (a file is in use?): delete it by hand." -ForegroundColor Yellow }
    else { Write-Host "Every backup and restore log is deleted." }
    if ($cert) { Write-Host "The work folder is empty. Run .\eax init laptop to start again." }
    else { Write-Host "The work folder is empty apart from the local certificate (work\data\tls). Run .\eax init laptop to start again." }
}

# ------------------------------------------------------------------ commands
if ($Command -in @("help", "-h", "--help", "/?")) { exit (Show-Help $(if ($RestArgs.Count -gt 0) { $RestArgs[0] } else { "" }) $(if ($RestArgs.Count -gt 1) { $RestArgs[1] } else { "" })) }
if ($Rest | Where-Object { $_ -in @("--help", "-h", "/?") }) { exit (Show-Help $AskedFor) }   # <command> --help: that command's help
# restart: down, then up, each as its own run of this script (own log); the data is kept
if ($Command -eq "restart") {
    [string[]]$up = @("up")
    if ($WaitAll) { $up += "--wait-all" }
    foreach ($step in @(, @("down")) + @(, $up)) {
        Write-Host ""
        Write-Host "=== .\eax $($step -join ' ')" -ForegroundColor Cyan
        & $PSCommandPath @step
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: .\eax $($step -join ' ') failed (exit $LASTEXITCODE); restart stopped there." -ForegroundColor Red
            exit $LASTEXITCODE
        }
        if ($step[0] -eq "down") {
            # nothing runs now, so a maintenance page or a paused background left behind is stale: taken away, so the
            # restart brings EA Explorer back open (owner, 18 Nov 2026, 11:50: "eax restart should remove mantainance page if any")
            foreach ($f in @("work/proxy/maintenance", "work/quiet.json")) {
                if (Test-Path $f) { Remove-Item -Force $f; Write-Host "Removed what was left: $f (the maintenance page and the paused background)." -ForegroundColor Yellow }
            }
        }
    }
    exit 0
}
# clean-run and clean-debug: cleanup --all --yes, init, then up or debug, each as its own run of
# this script (so each step writes its own log, like typing the three commands)
# clean-restart: down first (when there is a config file to find the containers by), then the same
if ($Command -in @("clean-run", "clean-debug", "clean-restart")) {
    $words = @($RestArgs | Where-Object { -not "$_".StartsWith("--") })
    $kind = if ($words.Count -gt 0) { $words[0] } else { "laptop" }
    # --certificate or --password passed on to init (R11.2): without either, init keeps the choice made before
    [string[]]$modes = @($RestArgs | Where-Object { $_ -eq "--certificate" -or $_ -eq "--password" })
    $last = if ($Command -eq "clean-debug") { "debug" } else { "up" }
    # built as an array on purpose: an if-expression would turn @("up") into the string "up", and splatting a string
    # passes its letters one by one ("u")
    [string[]]$finish = @($last)
    if ($WaitAll) { $finish += "--wait-all" }
    [string[]]$initStep = @("init", $kind) + $modes
    $steps = @(@("cleanup", "--all", "--yes"), $initStep, $finish)
    if ($Command -eq "clean-restart") {
        if (Test-Path $EnvFile) { $steps = @(, @("down")) + $steps }
        else { Write-Host "No $EnvFile yet: nothing running to bring down; going straight to clean-run." -ForegroundColor Yellow }
    }
    $env:EAX_BUILD_PULL = "1"   # the last step builds on fresh base images (R3.12, D673)
    foreach ($step in $steps) {
        Write-Host ""
        Write-Host "=== .\eax $($step -join ' ')" -ForegroundColor Cyan
        & $PSCommandPath @step
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: .\eax $($step -join ' ') failed (exit $LASTEXITCODE); $Command stopped there." -ForegroundColor Red
            exit $LASTEXITCODE
        }
    }
    exit 0
}
# the console (phase 13.5, D330): a numbered menu for getting a system that is down back up. It runs in the operations
# helper (services/ops/console.py); what needs this machine (start, stop, diagnostics, any eax command) it hands back here
# by its exit code. No sign-in: being on the machine is the trust. With --server: another installation, through its API.
function Invoke-Console([string[]]$Options) {
    if ($Options -contains "--server") {
        Assert-Docker
        & docker @(Get-ComposeArgs (@("run", "--rm", "--no-deps", "api", "python", "-m", "eax.console_cli", "remote") + $Options))
        return
    }
    $stopped = $false            # after Stop everything, nothing is started again until asked (1 below)
    while ($true) {
        $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        & docker info --format "{{.ServerVersion}}" 2>&1 | Out-Null
        $dockerOk = ($LASTEXITCODE -eq 0)
        $code = 99
        if ($dockerOk -and (Test-Path $EnvFile) -and -not $stopped) {
            # built first: an ops image from before the console has no console.py (a rebuild takes seconds when nothing changed)
            Write-Host "Starting the console (the operations helper; the first time it is built, a minute)..." -ForegroundColor DarkGray
            & docker @(Get-ComposeArgs @("up", "-d", "--build", "--no-deps", "ops")) 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                & docker @(Get-ComposeArgs @("exec", "ops", "python3", "/app/console.py", "--version", (Get-Version)))
                $code = $LASTEXITCODE
                # anything but the console's own answers (it failed): the basic menu, not the same failure again
                if ($code -notin @(0, 20, 21, 23, 25, 26, 27, 28, 29)) {
                    Write-Host "The console stopped with an error (exit $code); the basic menu follows. Its log: work\logs\console-*.log" -ForegroundColor Yellow
                    $code = 99
                }
            }
        }
        $ErrorActionPreference = $old
        if ($code -eq 99) {          # the helper could not start: only what this machine can do
            Write-Host ""
            Write-Host "EA Explorer console (basic: $(if ($stopped) { 'everything is stopped' } else { 'the operations helper is not running' }))" -ForegroundColor Cyan
            if (-not $dockerOk) { Write-Host "Docker Desktop is not running: start it, wait for 'Engine running', then choose 1." -ForegroundColor Yellow }
            elseif (-not (Test-Path $EnvFile)) { Write-Host "Not set up yet: there is no $EnvFile. Run .\eax init laptop first." -ForegroundColor Yellow }
            Write-Host "  1  Start everything"; Write-Host "  2  Save a diagnostics file for support"
            Write-Host "  c  Command prompt (every eax command)"; Write-Host "  q  Quit"
            $a = Read-Host "Choose"
            $code = switch ($a) { "1" { 20 } "2" { 23 } "c" { 25 } "q" { 0 } default { 98 } }
        }
        switch ($code) {
            0 { return }
            20 { $stopped = $false; & $PSCommandPath up }
            21 { & $PSCommandPath down; $stopped = $true }
            23 { & $PSCommandPath diag }
            26 { & $PSCommandPath test }                       # the tests chosen in the console (D953)
            27 { & $PSCommandPath test full }
            28 { & $PSCommandPath test full --risky }
            29 { & $PSCommandPath test failed }
            25 {
                Write-Host "Type an eax command (for example: test, test full, test full --risky, test failed, logs api, services, backups). Empty or back: the menu." -ForegroundColor Cyan
                while ($true) {
                    $line = Read-Host "eax"
                    if (-not $line -or $line -in @("back", "b", "menu")) { break }
                    $words = @($line -split "\s+" | Where-Object { $_ })
                    if ($words[0] -eq "console") { Write-Host "You are in the console already."; continue }
                    & $PSCommandPath @words
                }
            }
            default { }
        }
    }
}
if ($Command -eq "console") {
    try { Invoke-Console $RestArgs; exit 0 }
    catch { Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red; exit 1 }
}
if ($Command -eq "screen") {   # the full screen in the style of Turbo Pascal (R3.1): Python with Textual, run back here
    $env:EAX_FORM = "ps1"; $env:EAX_FORM_EXE = (Get-Process -Id $PID).Path
    & (Join-Path $PSScriptRoot "eaxpy.ps1") screen
    exit $LASTEXITCODE
}
if ($Command -eq "measure") {   # how much memory it needs, measured in one go (R3.5-M1): Python, eax commands run back here
    $env:EAX_FORM = "ps1"; $env:EAX_FORM_EXE = (Get-Process -Id $PID).Path
    & (Join-Path $PSScriptRoot "eaxpy.ps1") measure @RestArgs
    exit $LASTEXITCODE
}
if ($Command -eq "menu") {   # the numbered menu (R2.29): one Python program for every form, run back here
    $env:EAX_FORM = "ps1"; $env:EAX_FORM_EXE = (Get-Process -Id $PID).Path
    & (Join-Path $PSScriptRoot "eaxpy.ps1") menu
    exit $LASTEXITCODE
}
if (($Command -in @("init", "certs", "deploy", "secrets", "packs", "schedule", "persist", "folders", "allow", "drill", "dr-pack", "sign", "verify", "db", "ticket", "jobs", "optimise", "estimate", "dev", "jenkins", "setup", "access", "hostname", "settings", "site", "errors", "sonar", "images", "diag")) -or ($Command -eq "logs" -and $RestArgs.Count -gt 0 -and $RestArgs[0] -in @("backup", "clean")) -or ($Command -eq "test" -and ($RestArgs -contains "--reset-survival" -or $RestArgs -contains "backup-restore" -or $RestArgs -contains "restore" -or $RestArgs -contains "full" -or $RestArgs -contains "sonar" -or $RestArgs[0] -eq "jenkins" -or $RestArgs[0] -eq "commands" -or $RestArgs[0] -eq "backup-cases"))) {   # packs (D546); schedule (D559); test --reset-survival (D561); test backup-restore, restore, full (R5.6-B1)
    # phase 36 (D498, D504): one Python program for every form (D500); eaxpy.ps1 fetches uv and Python into work\tools
    $env:EAX_TYPED = ".\eax"   # messages then say .\eax, as typed, not .\eaxpy (R14)
    & (Join-Path $PSScriptRoot "eaxpy.ps1") $Command @RestArgs
    exit $LASTEXITCODE
}
if ($Command -eq "document") {
    try { Invoke-Document $RestArgs; exit 0 }
    catch { Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red; exit 1 }
}
if ($Command -eq "cleanup") {
    try { Invoke-Cleanup $RestArgs; exit 0 }
    catch { Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red; exit 1 }
}

Start-Log $Command
if ((Test-Path "eaexplorer.env") -and -not (Test-Path $EnvFile)) {
    Write-Log "Found eaexplorer.env in the main folder: it is no longer used. The config now lives in work\eaexplorer.env." "Yellow"
    Write-Log "Delete the old file and run .\eax init laptop (or copy your changes into work\eaexplorer.env)." "Yellow"
}
$failed = $false
try {
    if ($Command -in @("check", "up", "start-later", "debug", "status", "logs", "down", "backup", "backups", "restore", "restores", "restore-log", "databases", "footprint",
                       "delete-backup", "delete-restore", "app-backup", "restore-model", "restore-app", "model-backup", "project-backup", "restore-project", "check-backup", "stop-backup", "services", "service", "import", "update", "rollback", "test", "standby")) { Assert-Docker }
    switch ($Command) {
        "check" {
            if ((Invoke-Logged "docker" @("version", "--format", "Docker {{.Server.Version}}")) -ne 0) { throw "Docker Desktop is not running." }
            Invoke-Logged "docker" @("compose", "version") | Out-Null
            if (Test-Path $EnvFile) { Write-Log "Config: $EnvFile ($(Get-Setting 'EAX_DEPLOYMENT' 'laptop'))" } else { throw "No $EnvFile yet: run .\eax init" }
            Invoke-Compose @("config", "--quiet") | Out-Null
            Write-Log "Compose configuration is valid."
        }
        "up"      {
            # a newer release's new settings first, their passwords made here (R6; eax secrets fill); never fatal
            & (Join-Path $PSScriptRoot "eaxpy.ps1") secrets fill; $global:LASTEXITCODE = 0
            # the industry packs first (D584): new or changed files from the pack sources into library/industry-packs;
            # quick when nothing changed; a start never fails because of them
            if ($RestArgs.Count -eq 0) { & (Join-Path $PSScriptRoot "eaxpy.ps1") packs auto; $global:LASTEXITCODE = 0 }
            # an upgrade (D230): while the containers are rebuilt and restarted, the proxy shows the maintenance page
            $page = Set-UpgradePage ($RestArgs.Count -eq 0)
            try { Invoke-Up $RestArgs | Out-Null } finally { if ($page) { Remove-Item -Force "work/proxy/maintenance" -ErrorAction SilentlyContinue } }
            if ($RestArgs.Count -gt 0) { Show-PartUrls $RestArgs } else { Show-Urls; Show-Logins }
        }
        "start-later" { Invoke-Later }
        "debug" {
            & (Join-Path $PSScriptRoot "eaxpy.ps1") secrets fill; $global:LASTEXITCODE = 0   # a newer release's new settings (R6)
            if ($RestArgs.Count -eq 0) { & (Join-Path $PSScriptRoot "eaxpy.ps1") packs auto; $global:LASTEXITCODE = 0 }   # D584
            $code = Invoke-Up $RestArgs -NoThrow
            if ($code -ne 0) { Write-Log "docker compose up failed (exit $code); recording what is running anyway." "Red" }
            Save-Diagnostics
            if ($RestArgs.Count -gt 0) { Show-PartUrls $RestArgs } else { Show-Urls; Show-Logins }
            Watch-Containers $RestArgs
        }
        "status"  {
            Write-Log "EA Explorer $(Get-Release), build $(Get-BuildId)" "Cyan"
            $script:StatusColours = $true      # each container line in its state's colour (R2.10)
            try { Invoke-Compose @("ps", "-a") | Out-Null } finally { $script:StatusColours = $false }
            Show-FileSystems
            # every problem with its error code and what to do (R7.9, D787): one Python program for every form (D331)
            try { & (Join-Path $PSScriptRoot "eaxpy.ps1") status problems } catch { Write-Log "The problems could not be listed: $($_.Exception.Message)" "Yellow" }
            $global:LASTEXITCODE = 0
        }
        "logs"    { Invoke-Compose (@("logs", "-f", "--tail=100") + $RestArgs) -NoThrow | Out-Null }
        "down"    { Invoke-Compose @("down") | Out-Null; Remove-Extras }
        "backup"  { if (-not (Test-ServiceOn "backups")) { throw "Backups are switched off: .\eax service backups on" }
                    Start-BackupHelpers
                    Invoke-Interactive @("ops", "python3", "/app/ops.py", "backup") $RestArgs }
        "backups" { Start-BackupHelpers; Invoke-Interactive @("ops", "python3", "/app/ops.py", "list") $RestArgs }
        "footprint" {   # how much each container takes (R2.22); --history: the resource history (R3.5-M8)
            if ($RestArgs.Count -gt 0 -and $RestArgs[0] -eq "--history") {
                Invoke-Interactive @("api", "python", "-m", "eax.resources", "history") @($RestArgs | Select-Object -Skip 1)
            } else { Invoke-Interactive @("ops", "python3", "/app/ops.py", "footprint") $RestArgs }
        }
        "stop-backup" { Start-BackupHelpers; Invoke-Interactive @("ops", "python3", "/app/ops.py", "stop-backup") @() }
        "restore-app" { Invoke-Interactive @("api", "python", "-m", "eax.backups_cli", "restore-all") $RestArgs }
        "maintenance" {
            $flag = "work/proxy/maintenance"
            if ($RestArgs.Count -ge 1 -and $RestArgs[0] -in @("status", "clear")) {   # what a cut-off backup or DR run left (R5.6)
                & (Join-Path $PSScriptRoot "eaxpy.ps1") maintenance @RestArgs
                exit $LASTEXITCODE
            }
            if ($RestArgs.Count -lt 1 -or $RestArgs[0] -notin @("on", "off")) { throw "Usage: .\eax maintenance on|off|status|clear" }
            if ($RestArgs[0] -eq "on") {
                New-Item -ItemType Directory -Force -Path "work/proxy" | Out-Null
                [System.IO.File]::WriteAllText((Join-Path $PSScriptRoot $flag), "maintenance`n", $Utf8)
                Write-Log "The maintenance page is shown to everyone until: .\eax maintenance off"
            } else {
                if (Test-Path $flag) { Remove-Item -Force $flag }
                Write-Log "The maintenance page is off."
            }
        }
        "restore" { if (-not (Test-ServiceOn "backups")) { throw "Backups are switched off: .\eax service backups on" }
                    Start-BackupHelpers
                    Invoke-Interactive @("ops", "python3", "/app/ops.py", "restore") ($RestArgs + @("--version", (Get-Version))) }
        "restores" { Start-BackupHelpers; Invoke-Interactive @("ops", "python3", "/app/ops.py", "restores") @() }
        "databases" { Invoke-Interactive @("api", "python", "-m", "eax.databases") $RestArgs }   # where each database lives (R2.50)
        "restore-log" { Start-BackupHelpers; Invoke-Interactive @("ops", "python3", "/app/ops.py", "restore-log") $RestArgs }
        "delete-backup" { Start-BackupHelpers; Invoke-Interactive @("ops", "python3", "/app/ops.py", "delete-backup") $RestArgs }
        "delete-restore" { Start-BackupHelpers; Invoke-Interactive @("ops", "python3", "/app/ops.py", "delete-restore") $RestArgs }
        "app-backup" { Invoke-Interactive @("api", "python", "-m", "eax.backups_cli", "backup") $RestArgs }
        "import" { Invoke-Interactive @("api", "python", "-m", "eax.deliveries_cli") $RestArgs }
        "update" { Start-BackupHelpers; Invoke-Interactive @("ops", "python3", "/app/ops.py", "update") $RestArgs }      # phase 36, D417
        "rollback" { Start-BackupHelpers; Invoke-Interactive @("ops", "python3", "/app/ops.py", "rollback") $RestArgs }
        "restore-model" { Invoke-Interactive @("api", "python", "-m", "eax.backups_cli", "restore") $RestArgs }
        "model-backup" { Invoke-Interactive @("api", "python", "-m", "eax.backups_cli", "model-backup") $RestArgs }      # D970
        "project-backup" { Invoke-Interactive @("api", "python", "-m", "eax.backups_cli", "project-backup") $RestArgs }  # D970
        "restore-project" { Invoke-Interactive @("api", "python", "-m", "eax.backups_cli", "restore-project") $RestArgs } # D970
        "check-backup" { Invoke-Interactive @("api", "python", "-m", "eax.backups_cli", "check") $RestArgs }            # D968
        "test" {     # the self-test (phase 36.1, D367, D529, D530): reading results in the api container; a run, at once,
                     # through the operations helper (it builds the test runner first)
            $read = @{ "--status" = "status"; "--last" = "last"; "--report" = "report"; "--fixtures" = "fixtures"; "--clean" = "clean" }
            $which = @($RestArgs | Where-Object { $read.ContainsKey($_) })
            if ($RestArgs.Count -gt 0 -and $RestArgs[0] -eq "clean") {   # delete every test run's data, for good (R2.0.1, D593)
                Invoke-Interactive @("api", "python", "-m", "eax.testing.cli", "clean", "all") @($RestArgs | Select-Object -Skip 1)
            } elseif ($RestArgs.Count -gt 0 -and $RestArgs[0] -eq "delete") {   # delete test results for good (R2.43)
                Invoke-Interactive @("api", "python", "-m", "eax.testing.cli", "delete") @($RestArgs | Select-Object -Skip 1)
            } elseif ($RestArgs.Count -gt 0 -and ($RestArgs[0] -eq "prune" -or $RestArgs[0] -eq "summary")) {   # only the detailed files; the summaries (D825)
                Invoke-Interactive @("api", "python", "-m", "eax.testing.cli", $RestArgs[0]) @($RestArgs | Select-Object -Skip 1)
            } elseif ($RestArgs.Count -gt 0 -and $RestArgs[0] -eq "api") {   # the API test harness: one call (R3.16)
                Invoke-Interactive @("api", "python", "-m", "eax.testing.cli", "api") @($RestArgs | Select-Object -Skip 1)
            } elseif ($RestArgs.Count -gt 0 -and $RestArgs[0] -eq "watch" -and $RestArgs -contains "--browser") {   # the live view (R5.20)
                $run = @($RestArgs | Where-Object { $_ -match '^\d+$' } | Select-Object -First 1)
                $port = Get-Setting "EAX_HTTPS_PORT" "443"
                $url = "https://" + (Get-Setting "EAX_HOSTNAME" "localhost") + $(if ($port -eq "443") { "" } else { ":$port" }) + "/#/admin/self-test/watch" + $(if ($run) { "/$run" } else { "" })
                Write-Host "The live view: $url"
                if (-not $env:EAX_NO_BROWSER) { Start-Process $url }
            } elseif ($RestArgs.Count -gt 0 -and ($RestArgs[0] -eq "watch" -or $RestArgs[0] -eq "stop")) {   # follow a run live, or stop it (R3.2)
                Invoke-Interactive @("api", "python", "-m", "eax.testing.cli", $RestArgs[0]) @($RestArgs | Select-Object -Skip 1)
            } elseif ($RestArgs -contains "--build") {      # only build the runner image (D570; the Self-test page's button)
                Write-Host "Building the test runner (about 1.5 GB, 5 to 15 minutes the first time): base image, Python packages, Chromium, scanners."
                Invoke-Compose @("--profile", "test", "build", "testrunner") | Out-Null
                Write-Host "The test runner is built."
            } elseif ($which.Count -gt 0) {
                $rest = @($RestArgs | Where-Object { $_ -ne $which[0] })
                Invoke-Interactive @("api", "python", "-m", "eax.testing.cli", $read[$which[0]]) $rest
            } else {
                # always prepare the runner first (D584): seconds when it is current, rebuilt when the code or version changed
                Write-Host "Preparing the test runner... (the first time about 5 to 15 minutes; seconds when it is current)"
                Invoke-Compose @("--profile", "test", "build", "testrunner") | Out-Null
                Start-BackupHelpers
                Invoke-Interactive @("ops", "python3", "/app/ops.py", "test") ($RestArgs + @("--version", (Get-Version)))
            }
        }
        "standby" {  # the database standby (phase 36.3, D527; EAX_COMPOSE_EXTRA=standby)
            $what = if ($RestArgs.Count -gt 0) { $RestArgs[0] } else { "status" }
            if ($what -eq "status") {
                Invoke-Interactive @("db", "psql", "-U", "postgres", "-c") @("SELECT client_addr, state, sync_state, replay_lag FROM pg_stat_replication")
                Invoke-Interactive @("db-standby", "psql", "-U", "postgres", "-c") @("SELECT pg_is_in_recovery() AS following_the_primary, now() - pg_last_xact_replay_timestamp() AS behind_by")
            } elseif ($what -eq "promote") {
                Write-Log "The standby becomes the primary: it stops following and accepts changes. Then set EAX_DB_HOST=db-standby (or the standby's host) and run .\eax up." "Yellow"
                if ((Read-Host "Type PROMOTE to go on") -ne "PROMOTE") { Write-Log "Nothing changed."; return }
                Invoke-Interactive @("-u", "postgres", "db-standby", "pg_ctl", "promote", "-D") @("/var/lib/postgresql/data")
            } else { throw "Usage: .\eax standby status|promote" }
        }
        "services" { Show-Services }
        "servers" {
            if ($RestArgs.Count -lt 1) {
                Write-Log "API and job servers wanted: $(Get-ApiServers) (EAX_API_SERVERS). Running:"
                Invoke-Compose @("ps", "api") | Out-Null
            } else {
                $n = 0
                if (-not [int]::TryParse($RestArgs[0], [ref]$n) -or $n -lt 1 -or $n -gt 16) { throw "Usage: .\eax servers <1 to 16>" }
                $history = Join-Path $WorkDir "config-history"
                New-Item -ItemType Directory -Force -Path $history | Out-Null
                Copy-Item $EnvFile (Join-Path $history "eaexplorer.env.$((Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmss')).$($env:USERNAME -replace '[^A-Za-z0-9_.-]', '-').servers-$n")
                $lines = @(Get-Content $EnvFile)
                if ($lines | Where-Object { $_ -match "^\s*EAX_API_SERVERS\s*=" }) { $lines = $lines | ForEach-Object { if ($_ -match "^\s*EAX_API_SERVERS\s*=") { "EAX_API_SERVERS=$n" } else { $_ } } }
                else { $lines += @("", "# ---- API and job servers (D249)", "EAX_API_SERVERS=$n") }
                [System.IO.File]::WriteAllText((Join-Path $PSScriptRoot $EnvFile), (($lines -join "`n") + "`n"), $Utf8)
                Write-Log "Running $n API and job server(s); stopping a server lets the jobs it runs finish first."
                Invoke-Compose @("up", "-d", "--no-deps", "--no-recreate", "--scale", "api=$n", "api") | Out-Null
            }
        }
        "service" {
            if ($RestArgs.Count -lt 2) { throw "Usage: .\eax service <name> on|off   (names: $($Services.Keys -join ', '))" }
            Set-Service $RestArgs[0] $RestArgs[1].ToLower()
        }
        "url"     { Show-Urls; Show-Logins }
        "logins"  { if (-not (Test-Path $EnvFile)) { throw "No $EnvFile yet: run .\eax init first." }   # a server too (D975)
                    $env:EAX_TYPED = ".\eax"; & (Join-Path $PSScriptRoot "eaxpy.ps1") logins @RestArgs; exit $LASTEXITCODE }
        "trust"   { if (-not (Test-Path $EnvFile)) { throw "No $EnvFile yet: run .\eax init first." }; Invoke-Trust $RestArgs }
        default   { throw (Get-UnknownCommand $Command) }
    }
} catch {
    $failed = $true
    if ($script:Log) { $script:Log.WriteLine("ERROR: $($_.Exception.Message)") }
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
} finally {
    if ($script:LogPath) { Write-Host "Log: $script:LogPath" -ForegroundColor DarkGray }
    Stop-Log
}
if ($failed) { exit 1 }
