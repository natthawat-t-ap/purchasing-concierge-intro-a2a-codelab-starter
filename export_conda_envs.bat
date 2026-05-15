@echo off
REM Export all conda environments to YAML files
REM Saved to: C:\Users\natthawat_t\conda_env_exports\

set EXPORT_DIR=C:\Users\natthawat_t\conda_env_exports
if not exist "%EXPORT_DIR%" mkdir "%EXPORT_DIR%"

echo Exporting all conda environments to %EXPORT_DIR%...
echo.

for /f "tokens=1" %%e in ('conda env list ^| findstr /v /c:"#" ^| findstr /r /v "^$"') do (
    echo Exporting: %%e
    conda env export -n %%e > "%EXPORT_DIR%\%%e.yml"
)

echo.
echo Done! All environments exported to %EXPORT_DIR%
dir "%EXPORT_DIR%"
