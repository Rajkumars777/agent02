@echo off
set "SCRIPT_DIR=%~dp0"
if not exist "%SCRIPT_DIR%start.vbs" (
    echo Set WshShell = CreateObject("WScript.Shell"^) > "%SCRIPT_DIR%start.vbs"
    echo WshShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject"^).GetParentFolderName(WScript.ScriptFullName^) >> "%SCRIPT_DIR%start.vbs"
    echo WshShell.Run "cmd /c npx.cmd electron .", 0, False >> "%SCRIPT_DIR%start.vbs"
)
wscript.exe "%SCRIPT_DIR%start.vbs"
