@echo off
REM SPDX-License-Identifier: MIT
REM The content of this file has been developed in the context of the MOSIM research project.
REM Original author(s): Janis Sprenger, Bhuvaneshwaran Ilanthirayan

ECHO.
ECHO _______________________________________________________
ECHO [33mdeploy.bat[0m at %cd%\deploy.bat Deploying the BlenderIK Service. 
ECHO _______________________________________________________
ECHO.

SET MOSIM=git+https://github.com/dfki-asr/MMIPython-Core.git

IF NOT EXIST blender-2.83.10-windows64.zip (
  ECHO Downloading Blender. This may take a while. [92mPlease wait[0m and consider the download progress on top of the console. 
  powershell -Command "Invoke-WebRequest https://ftp.halifax.rwth-aachen.de/blender/release/Blender2.83/blender-2.83.10-windows64.zip -OutFile blender-2.83.10-windows64.zip"
  if %ERRORLEVEL% NEQ 0 (
    ECHO [31mThere has been an error during the download of blender. Please investigate the download link in this file and your internet connection! [0m
    exit /b %ERRORLEVEL%
  )
)
IF NOT EXIST build ( 
  md build
)
REM setting up blender
IF NOT EXIST build/Blender (
  ECHO Extracting Blender. This may take a while. [92mPlease wait[0m and consider the progress bar on the top of the console. 
  
  powershell -Command "Expand-Archive -Path blender-2.83.10-windows64.zip -DestinationPath build/"
  if %ERRORLEVEL% NEQ 0 (
    ECHO [31mThere has been an error during the extraction of blender. Please investigate the blender file at %cd%\blender-2.83.10-windows64.zip for corruption. [0m
    exit /b %ERRORLEVEL%
  )
  rename build\blender-2.83.10-windows64 Blender
)

if "%~1"=="" (
  ECHO No parameters were provided, standard MMI-Python core repository from "https://github.com/dfki-asr/MMIPython-Core" is utilized
) else (
  ECHO MMIPython core repository from "%~1" is utilized. 
  SET MOSIM=%~1
)


set mypath=%~dp0
build\Blender\2.83\python\bin\python.exe -m ensurepip

REM This is very hacky. For some reason, the pip installation or any other pip installation fails at the first try.
REM By starting the initial pip upgrade in advance in a separate window and killing it after some time, we can circumvent this problem. 
REM This requires further testing, in order to test wether the threshold of 10s is long enough on different systems. 
start "install pip" build\Blender\2.83\python\bin\python.exe -m pip install --upgrade pip
timeout /t 30
taskkill /FI "WindowTitle eq install pip*" /T /F

REM reinstalling six. It this step is skipped, it might create issues for the next install. 
%mypath%\build\Blender\2.83\python\bin\python.exe -m pip install --force-reinstall six

REM installing the MOSIM Core python package (and thrift by dependency)
%mypath%\build\Blender\2.83\python\bin\python.exe -m pip install %MOSIM%

COPY Readme.md build\

COPY build-resources\version.txt build\
COPY build-resources\description.json build\
COPY build-resources\service.config build\
COPY build-resources\Start_IKService.bat build\
md build\resources
md build\src
cmd /c xcopy /S/E/Y .\build-resources\resources .\build\resources
cmd /c xcopy /S/E/Y .\src .\build\src


if %ERRORLEVEL% EQU 0 (
  REM COPY .\configurations\avatar.mos build\
  ECHO [92mSuccessfully deployed the blender IK Service [0m
  ECHO Copying the BlenderIK Service may take some while. Please wait...
  exit /b 0
) else (
  ECHO [31mDeployment of the blender IK Service failed. [0m
  exit /b 1
)