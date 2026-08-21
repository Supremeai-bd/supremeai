@echo off
setlocal EnableDelayedExpansion
title SupremeAI Project Backup & Modular AI Ingestion Master
color 0A

:menu
cls
echo =======================================================================
echo            SupremeAI 2.0 - Modular Archival ^& AI Ingestion Master
echo =======================================================================
echo.
echo  --- [ FULL REPOSITORY ] ---
echo    [1] Full Codebase Zip (.zip)
echo        - Clean, complete repository backup
echo    [2] Full Single-File Markdown AI Digest (.md)
echo        - Entire codebase in 1 file for LLM ingestion
echo    [3] Full Bundle (Zip + Markdown Digest)
echo.
echo  --- [ MODULAR SCOPES (Fast, Lightweight for AI / Audits) ] ---
echo    [4] Backend Only (.zip + .md)
echo        - All backend services, security, database, APIs (~1,190 files)
echo    [5] Backend Markdown Digest (.md Only)
echo        - Direct, lightweight LLM ingestion (~8 MB single file)
echo    [6] Frontend ^& Desktop Apps (.zip + .md)
echo        - Web, Tauri Desktop, shared UI packages
echo    [7] Security, RBAC ^& Firewalls (.zip + .md)
echo        - Guardian AI, Prompt Firewall, SSRF, Auth, Secrets
echo    [8] MCP Tools, Agents ^& Pipelines (.zip + .md)
echo        - MCP servers, AI agent tools, data pipelines
echo.
echo  --- [ INCREMENTAL / GIT DIFF ] ---
echo    [9] Latest Git Diff Patch (.md)
echo        - Syntax-highlighted diff patch of latest commit
echo    [D] Changed-Files-Only Zip (.zip)
echo        - Lightweight zip containing only modified files
echo.
echo  --- [ BATCH / EXIT ] ---
echo    [A] Generate All Standard Artifacts (Full + Backend + Diff)
echo    [Q] Quit / Exit
echo.
echo =======================================================================
set /p choice=" Enter your choice (1-9, D, A, or Q): "

if "%choice%"=="1" (
    set "CMD_ARGS=--scope all --format zip"
    goto run
)
if "%choice%"=="2" (
    set "CMD_ARGS=--scope all --format md"
    goto run
)
if "%choice%"=="3" (
    set "CMD_ARGS=--scope all --format both"
    goto run
)
if "%choice%"=="4" (
    set "CMD_ARGS=--scope backend --format both"
    goto run
)
if "%choice%"=="5" (
    set "CMD_ARGS=--scope backend --format md"
    goto run
)
if "%choice%"=="6" (
    set "CMD_ARGS=--scope frontend --format both"
    goto run
)
if "%choice%"=="7" (
    set "CMD_ARGS=--scope security --format both"
    goto run
)
if "%choice%"=="8" (
    set "CMD_ARGS=--scope tools --format both"
    goto run
)
if "%choice%"=="9" (
    set "CMD_ARGS=--scope diff --format diff-md"
    goto run
)
if /i "%choice%"=="d" (
    set "CMD_ARGS=--scope diff --format diff-zip"
    goto run
)
if /i "%choice%"=="a" (
    set "CMD_ARGS=--scope all --format all"
    goto run
)
if /i "%choice%"=="q" (
    echo Exiting...
    exit /b 0
)

echo.
echo [!] Invalid selection "%choice%". Please enter an option from the menu.
timeout /t 2 >nul
goto menu

:run
cls
echo =======================================================================
echo  Running SupremeAI Archival Master (%CMD_ARGS%)
echo =======================================================================
echo.
python "C:\Users\N\Desktop\create_project_zip.py" %CMD_ARGS%
echo.
echo =======================================================================
echo Operation complete! Press any key to return to menu...
pause >nul
goto menu
