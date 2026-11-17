@echo off
rem eax-dr launcher for Command Prompt: runs eax-dr.ps1 in PowerShell with the execution policy bypassed for this run only.
rem Typing eax-dr.ps1 in Command Prompt opens it in the editor Windows links .ps1 files to instead (the owner, 17 Nov 2026).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0eax-dr.ps1" %*
exit /b %ERRORLEVEL%
