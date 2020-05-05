@echo off

echo ---------------------
echo a xls2any tool by ml.
echo ---------------------

set out_dir=.
set lan_type=lua
set meta_sheet=xls2any
set scope=local
set header_mode=--header

set CONFIG_FILE=%USERPROFILE%\xls2any.cfg
set PACKAGE_FILE=__xlsconfig__

if "%1"=="-d" del %CONFIG_FILE% & goto :eof

if not exist %CONFIG_FILE% (
    set pwd=%cd%
    if not exist "%1" (
        cd \
        for %%i in (D E F C G H I J K L M N) do (
            if exist %%i: (
                echo search %PACKAGE_FILE% in %%i
                %%i:
                for /f %%j in ('dir /s /b %PACKAGE_FILE%') do echo %%~dpj >> %CONFIG_FILE%
            )
        )
    ) else (
        echo search %PACKAGE_FILE% in %1...
        cd /d "%1"
        for /f %%j in ('dir /s /b %PACKAGE_FILE%') do echo %%~dpj >> %CONFIG_FILE%
    )
    
    cd /d %pwd%
)

chcp 936 >nul
for /f %%i in (%CONFIG_FILE%) do (
   for /f %%j in ('dir /s /b /a:-d %%i*.xls') do python xls2any.py %header_mode% -s %scope% -d %out_dir% -t %lan_type% -m %meta_sheet% %%j
)

pause
