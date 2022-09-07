@echo off
@setlocal enabledelayedexpansion

REM SPDX-License-Identifier: MIT
REM The content of this file has been developed in the context of the MOSIM research project.
REM Original author(s): Janis Sprenger, Bhuvaneshwaran Ilanthirayan, Klaus Fischer

REM This is a deploy script to auto-generate the components of the MOSIM-CSharp projects and move them to a new environment folder. 

call :CheckPowershell PARENT

SET VERBOSE=0

REM FONT: Mini
REM https://patorjk.com/software/taag/#p=display&f=Mini&t=MOSIM%20%20-%20%20Python

ECHO " ---------------------------------------------------- "
ECHO "       _   __ ___                  _                  "
ECHO " |\/| / \ (_   |  |\/|     __     |_) _|_ |_   _  ._  "
ECHO " |  | \_/ __) _|_ |  |            | \/ |_ | | (_) | | "
ECHO "                                    /                 "
ECHO " ---------------------------------------------------- "
ECHO.


call :argparse %*

goto :eof

REM Method Section

:: argparse
:argparse
	if [%1]==[] (
		call :DisplayUsage
		exit /b 0
	)
	if "%1"=="-h" (
		call :DisplayUsage
		exit /b 0
	)
	if "%1"=="--help" ( 
		call :DisplayUsage
		exit /b 0
	)
	if "%1"=="\?" ( 
		call :DisplayUsage
		exit /b 0
	)
	
	SET REPO=%~dp0..

	IF "%1"=="" (
		ECHO Taking default MOSIM Target Path "%MOSIM_TARGET_PATH%"
		SET "MOSIM_HOME=%MOSIM_TARGET_PATH%"
	) ELSE (
		SET "var=%1"
		IF "!var:~0,1!"=="-" (
			ECHO Taking default MOSIM Target Path "%MOSIM_TARGET_PATH%"
			SET "MOSIM_HOME=%MOSIM_TARGET_PATH%"
		) ELSE (
			FOR /F %%i IN ("%1") DO SET "MOSIM_HOME=%%~fi"	
			ECHO Taking provided MOSIM Target Path at "!MOSIM_HOME!"
			SHIFT
		)
	)
	
	if "%MOSIM_HOME%"=="" (
		ECHO Please provide a target directory 
		ECHO     - either as a parameter to this script or 
		ECHO     - adjust the Deployment\DefaultVariables.bat in the meta repository and run Deployment\Initialize.bat
		ECHO     - or use SETX MOSIM_TARGET_PATH C:\Path\To\My\Target to set the variable manually. 
		call :halt 1
	)
	
	echo Deploying to: %MOSIM_HOME%
	SET BUILDENV=%MOSIM_HOME%\Environment
	SET LIBRARYPATH=%MOSIM_HOME%\Libraries
	
	
	if "%1"=="-v" (
		ECHO Running in Verbose mode
		SET VERBOSE=1
		SHIFT
	)
	
	if [%1]==[] (
		call :DeployAll
		exit /b 0
	)

	:argparse_loop
	if not [%1]==[] (
		if "%1"=="-m" (
			if "%2"=="BlenderIK" (
				call :DeployBlenderIK 
			)
			SHIFT
		) else ( 
			if "%1"=="-a" (
				call :DeployAll
			)
		)
		SHIFT
		goto :argparse_loop
	)
exit /b 0

::DisplayUsage
:DisplayUsage
	echo Usage
exit /b 0

::FolderNotFound
:FolderNotFound
	echo Folder Not Found
exit /b 0

::DeployBlenderIK
:DeployBlenderIK
	call :DeployMethod %REPO%\Services\BlenderIK Services\BlenderIK build
exit /b 0

::DeployAll
:DeployAll
	call :DeployBlenderIK
exit /b 0


::DeployMethod 
::  %1 path to component
::  %2 target path
::  %3 build path in component
:DeployMethod
  REM Build Adapters
  set back=%CD%
  
  if exist %1 (
	  cd %1
	  call :safeCall .\deploy.bat "There has been an error when deploying %1" %back%
	  cd %back%
	  if not [%2]==[] (
		  md "%BUILDENV%\%2"
		  echo  "%1\%3\*" "%BUILDENV%\%2\"
		  cmd /c xcopy /S/Y/Q "%1\%3\*" "%BUILDENV%\%2\"
		  if %ERRORLEVEL% NEQ 0 echo There has been an error during copy. 
		  REM if %ERRORLEVEL% NEQ 0 cd %MOSIM_HOME% && call :halt %ERRORLEVEL%
	  )
  ) else (
    ECHO -----------
	ECHO [31m Path %1 does not exist and thus will not be deployed.[0m
	ECHO -----------
  )
exit /b

:: Calls a method %1 and checks the error level. If %1 failed, text %2 will be reported. 
:safeCall
SET back=%3
call %1
if %ERRORLEVEL% NEQ 0 (
  ECHO [31m %~2 [0m
  cd %back%
  call :halt %ERRORLEVEL%
) else (
	exit /b
)

:CheckPowershell
SET "PSCMD=$ppid=$pid;while($i++ -lt 3 -and ($ppid=(Get-CimInstance Win32_Process -Filter ('ProcessID='+$ppid)).ParentProcessId)) {}; (Get-Process -EA Ignore -ID $ppid).Name"

for /f "tokens=*" %%i in ('powershell -noprofile -command "%PSCMD%"') do SET %1=%%i

IF ["%PARENT%"] == ["powershell"] (
	ECHO This script should not run from within a Powershell but a Command Prompt aka cmd
	call :halt 1
) ELSE (
    exit /b 1
)


:: Sets the errorlevel and stops the batch immediately
:halt
call :__SetErrorLevel %1
call :__ErrorExit 2> nul
goto :eof

:__ErrorExit
rem Creates a syntax error, stops immediately
() 
goto :eof

:__SetErrorLevel
exit /b %time:~-2%
goto :eof

REM ErrorExit should not be called, just goto'ed. It assumes, that the ERRORLEVEL variable was set before to the appropriate value. 
REM exit /b %ERRORLEVEL%
REM Nothing should folow after this. 