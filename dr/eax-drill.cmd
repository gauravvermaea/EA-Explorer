@echo off
rem eax-drill launcher for Command Prompt: runs eax-drill.ps1 in PowerShell with the execution policy bypassed for this run only.
rem Typing eax-drill.ps1 in Command Prompt opens it in the editor Windows links .ps1 files to instead (the owner, 17 Nov 2026).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0eax-drill.ps1" %*
exit /b %ERRORLEVEL%
