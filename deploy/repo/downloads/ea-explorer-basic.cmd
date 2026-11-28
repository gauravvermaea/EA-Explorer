<# : batch part, the EA Explorer basic install (double-click to run)
@echo off
powershell -NoProfile -ExecutionPolicy Bypass -STA -Command "Invoke-Expression ([IO.File]::ReadAllText('%~f0'))"
exit /b
#>
# EA Explorer {{VERSION}}: the laptop setup, no questions. Written by the deploy page; it holds no password.
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$Folder = Join-Path $env:USERPROFILE "EA-Explorer"
$Zip = "{{DEPLOY_REPO}}/archive/refs/heads/main.zip"
$Log = Join-Path $env:TEMP "ea-explorer-basic.log"

# ---- the window: what is happening, and the last lines of output
$form = New-Object Windows.Forms.Form
$form.Text = "EA Explorer {{VERSION}}: setting up"; $form.Width = 760; $form.Height = 520; $form.StartPosition = "CenterScreen"
$title = New-Object Windows.Forms.Label; $title.Dock = "Top"; $title.Height = 44; $title.Font = New-Object Drawing.Font("Segoe UI", 12)
$title.Padding = New-Object Windows.Forms.Padding(10, 10, 10, 0)
$bar = New-Object Windows.Forms.ProgressBar; $bar.Dock = "Top"; $bar.Height = 18; $bar.Maximum = 8
$box = New-Object Windows.Forms.TextBox; $box.Multiline = $true; $box.ReadOnly = $true; $box.ScrollBars = "Vertical"; $box.Dock = "Fill"
$box.Font = New-Object Drawing.Font("Consolas", 9)
$form.Controls.Add($box); $form.Controls.Add($bar); $form.Controls.Add($title)
$form.Show(); [Windows.Forms.Application]::DoEvents()

function Say([string]$Text) { $box.AppendText($Text + [Environment]::NewLine); [Windows.Forms.Application]::DoEvents() }
function Stage([int]$N, [string]$Text) { $bar.Value = $N; $title.Text = "Step $N of 8: $Text"; Say ""; Say "== $Text" }
function Fail([string]$Text) {
  $title.Text = "Stopped"; Say ""; Say "STOPPED: $Text"; Say "The full log: $Log"
  [Windows.Forms.MessageBox]::Show($Text + [Environment]::NewLine + [Environment]::NewLine + "The full log: $Log", "EA Explorer", "OK", "Warning") | Out-Null
  while ($form.Visible) { [Windows.Forms.Application]::DoEvents(); Start-Sleep -Milliseconds 100 }
  exit 1
}
# Run: a command in the background, its output shown as it comes (the window stays alive)
function Run([string]$Command, [string]$Where = $env:TEMP) {
  $out = Join-Path $env:TEMP "ea-explorer-step.log"; Set-Content $out ""
  $p = Start-Process cmd.exe -ArgumentList "/c $Command > ""$out"" 2>&1" -WorkingDirectory $Where -WindowStyle Hidden -PassThru
  $seen = 0
  while (-not $p.HasExited) {
    Start-Sleep -Milliseconds 300; [Windows.Forms.Application]::DoEvents()
    $lines = @(Get-Content $out -ErrorAction SilentlyContinue); for ($i = $seen; $i -lt $lines.Count; $i++) { Say $lines[$i] }; $seen = $lines.Count
  }
  $lines = @(Get-Content $out -ErrorAction SilentlyContinue); for ($i = $seen; $i -lt $lines.Count; $i++) { Say $lines[$i] }
  Add-Content $Log $lines
  return $p.ExitCode
}
function DockerUp { cmd /c "docker info >nul 2>&1"; return ($LASTEXITCODE -eq 0) }

Stage 1 "Checking this computer"
$mem = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
$free = [math]::Round((Get-PSDrive ($env:USERPROFILE.Substring(0, 1))).Free / 1GB)
Say "Memory: $mem GB   Free disk: $free GB"
if ($mem -lt 15) { Say "Warning: 16 GB of memory or more is advised." }
if ($free -lt 30) { Fail "There are only $free GB free: EA Explorer needs about 30 GB." }

Stage 2 "Docker Desktop"
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  $a = [Windows.Forms.MessageBox]::Show("Docker Desktop is not installed. Install it now? Windows asks for an administrator's yes, and may ask to restart (run this file again afterwards).", "EA Explorer", "YesNo", "Question")
  if ($a -ne "Yes") { Fail "EA Explorer needs Docker Desktop: https://docs.docker.com/desktop/setup/install/windows-install/" }
  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { Fail "winget is missing: install Docker Desktop yourself from https://docs.docker.com/desktop/setup/install/windows-install/ and run this file again." }
  if ((Run "winget install -e --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements") -ne 0) { Fail "Docker Desktop could not be installed (the reason is above)." }
  [Windows.Forms.MessageBox]::Show("Docker Desktop is installed. Restart Windows if it asks, start Docker Desktop once (accept its terms), then run this file again.", "EA Explorer") | Out-Null
  exit 0
}
if (-not (DockerUp)) {
  Say "Starting Docker Desktop..."
  $dd = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
  if (Test-Path $dd) { Start-Process $dd }
  for ($i = 0; $i -lt 90 -and -not (DockerUp); $i++) { Start-Sleep 2; [Windows.Forms.Application]::DoEvents() }
  if (-not (DockerUp)) { Fail "Docker Desktop does not answer. Start it, wait until it says it is running, and run this file again." }
}
Say "Docker is running."

Stage 3 "Getting EA Explorer"
if (-not (Test-Path (Join-Path $Folder "eax.cmd"))) {
  $z = Join-Path $env:TEMP "ea-explorer.zip"; $x = Join-Path $env:TEMP "ea-explorer-unzip"
  Say "Downloading $Zip"
  try { [Net.ServicePointManager]::SecurityProtocol = "Tls12"; Invoke-WebRequest $Zip -OutFile $z -UseBasicParsing } catch { Fail "Could not download EA Explorer: $($_.Exception.Message)" }
  if (Test-Path $x) { Remove-Item $x -Recurse -Force }
  Expand-Archive $z $x -Force
  $inner = Get-ChildItem $x -Directory | Select-Object -First 1
  New-Item -ItemType Directory -Force $Folder | Out-Null
  Copy-Item (Join-Path $inner.FullName "*") $Folder -Recurse -Force
  Remove-Item $z, $x -Recurse -Force
} else { Say "Already here: $Folder" }
Say "EA Explorer's folder: $Folder"

Stage 4 "The settings (laptop)"
$env:EAX_NONINTERACTIVE = "1"; $env:EAX_NO_BROWSER = "1"
if (-not (Test-Path (Join-Path $Folder "work\eaexplorer.env"))) {
  if ((Run "eax.cmd init laptop --password" $Folder) -ne 0) { Fail "The settings could not be made (the reason is above)." }
} else { Say "Kept: the settings are already there." }

Stage 5 "Downloading the images (the first time takes a while)"
if ((Run "eax.cmd images pull --missing" $Folder) -ne 0) { Fail "The images could not be downloaded (the reason is above)." }

Stage 6 "Starting EA Explorer (several minutes)"
if ((Run "eax.cmd up --wait-all" $Folder) -ne 0) { Fail "EA Explorer did not start (the reason is above). In its folder: eax.cmd status" }

Stage 7 "The smoke test (a few minutes)"
if ((Run "eax.cmd test smoke" $Folder) -ne 0) { Say ""; Say "The smoke test found a problem: its report is in $Folder\work\tests (and on the Self-test screen)." }
else { Say "The smoke test passed." }

Stage 8 "Done"
$out = Join-Path $env:TEMP "ea-explorer-logins.txt"
cmd /c "cd /d ""$Folder"" && eax.cmd url > ""$out"" 2>&1 && eax.cmd logins >> ""$out"" 2>&1"
$esc = [char]27; $text = (Get-Content $out) -replace "$esc\[[0-9;]*[A-Za-z]", ""; Remove-Item $out
$url = ([regex]::Match(($text -join " "), "https?://localhost[^\s,)]*")).Value; if (-not $url) { $url = "https://localhost" }
$form.Text = "EA Explorer {{VERSION}}: ready"; $title.Text = "EA Explorer is running: $url"
$box.Clear(); Say "EA Explorer is running at $url"; Say ""; Say "Sign in with these (laptop passwords: for trying it out only):"; Say ""
foreach ($l in $text) { Say $l }
Say ""; Say "Later, in $Folder :  eax.cmd stop   eax.cmd up   eax.cmd logins"
Say "If the browser warns about the certificate: eax.cmd trust (once)."
Start-Process $url
$a = [Windows.Forms.MessageBox]::Show("EA Explorer is running and the smoke test is done." + [Environment]::NewLine + [Environment]::NewLine +
  "Run the full test now? It tests everything, backups and DR included, and takes a few hours. You can keep using EA Explorer meanwhile, but it is slower and restarted now and then.", "EA Explorer: the full test", "YesNo", "Question")
if ($a -eq "Yes") {
  $title.Text = "The full test is running (a few hours): you can close this window, it keeps going"
  Say ""; Say "== The full test (a few hours). Follow it on the Self-test screen too."
  Start-Process cmd.exe -ArgumentList "/c cd /d ""$Folder"" && eax.cmd test full & pause" -WorkingDirectory $Folder
}
while ($form.Visible) { [Windows.Forms.Application]::DoEvents(); Start-Sleep -Milliseconds 100 }
