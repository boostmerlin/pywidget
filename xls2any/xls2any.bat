@echo off

echo ---------------------
echo a xls2any tool by ml.
echo ---------------------

set out_dir=.
set lan_type=lua
set meta_sheet=xls2any

set CONFIG_FILE=%USERPROFILE%\xls2any.cfg

if "%1"=="d" del %CONFIG_FILE% & goto :eof

if not exist %CONFIG_FILE% (
    set pwd=%cd%
    cd \
    for %%i in (D E F C G H I J K L M N) do (
        if exist %%i: (
            %%i:
            for /f %%j in ('dir /s /b __xlsconfig__') do echo %%~dpj >> %CONFIG_FILE%
        )
    )
    cd /d %pwd%
)

for /f %%i in (%CONFIG_FILE%) do (
   for /f %%j in ('dir /s /b /a:-d %%i') do python xls2any.py --header -s local -d %out_dir% -t %lan_type% -m %meta_sheet% %%j
)

pause
