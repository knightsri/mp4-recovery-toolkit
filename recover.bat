@echo off
:: MP4 Recovery Toolkit - Windows Batch File (with Docker integration)
:: Builds Docker image, and repairs, analyzes, or batch processes MP4 files.
:: Author: Your Name
:: License: MIT

setlocal enabledelayedexpansion

:: --- Configuration ---
set "DOCKER_IMAGE_NAME=mp4-recovery-toolkit"
set "DOCKER_IMAGE_TAG=latest"
set "FULL_IMAGE_NAME=%DOCKER_IMAGE_NAME%:%DOCKER_IMAGE_TAG%"
:: --- End Configuration ---

:: Check for Docker early
docker --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Docker is not installed or not in PATH.
    echo Please install Docker Desktop for Windows: https://docs.docker.com/desktop/install/windows-install/
    goto :script_error_exit_no_cleanup
)

:: Main command dispatcher
set "MAIN_COMMAND=%~1"

if /i "%MAIN_COMMAND%"=="setup"    shift /1 & goto :setup_docker
if /i "%MAIN_COMMAND%"=="repair"   shift /1 & goto :handle_repair_command
if /i "%MAIN_COMMAND%"=="info"     shift /1 & goto :handle_info_command
if /i "%MAIN_COMMAND%"=="batch"    shift /1 & goto :handle_batch_command
if /i "%MAIN_COMMAND%"=="list"     shift /1 & goto :list_techniques_docker
if /i "%MAIN_COMMAND%"=="--help"   shift /1 & goto :show_main_help
if /i "%MAIN_COMMAND%"=="-h"       shift /1 & goto :show_main_help
if "%MAIN_COMMAND%"==""            goto :show_main_help

echo ERROR: Unknown main command "%MAIN_COMMAND%".
goto :show_main_help

:: ============================================================================
:: Docker Setup
:: ============================================================================
:setup_docker
echo.
echo ===== DOCKER IMAGE SETUP =====
echo Building Docker image: %FULL_IMAGE_NAME% ...
docker build -t "%FULL_IMAGE_NAME%" .
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to build Docker image. Make sure Dockerfile is in the current directory.
    goto :script_error_exit
) else (
    echo Docker image %FULL_IMAGE_NAME% built successfully!
)
goto :script_success_exit

:: ============================================================================
:: List Techniques (via Docker)
:: ============================================================================
:list_techniques_docker
echo.
echo ===== LIST AVAILABLE TECHNIQUES (via Docker) =====
docker run --rm "%FULL_IMAGE_NAME%" --list
set "SCRIPT_RUN_ERRORLEVEL=%ERRORLEVEL%"
goto :end_script_with_code


:: ============================================================================
:: Handle 'repair' command and its arguments
:: ============================================================================
:handle_repair_command
set "INPUT_FILE_ARG="
set "REFERENCE_FILE_ARG="
set "OUTPUT_FILE_ARG="
set "TECHNIQUE_OPTION="
set "ARGS_OK=true"

:parse_repair_args_loop
if "%~1"=="" goto :validate_repair_args

if /i "%~1"=="--technique" (
    if "%~2"=="" ( echo ERROR: --technique option requires a value. & set "ARGS_OK=false" & goto :validate_repair_args )
    set "TECHNIQUE_OPTION=-t %~2"
    shift
    goto :next_repair_arg_loop
)
if /i "%~1"=="-t" (
    if "%~2"=="" ( echo ERROR: -t option requires a value. & set "ARGS_OK=false" & goto :validate_repair_args )
    set "TECHNIQUE_OPTION=-t %~2"
    shift
    goto :next_repair_arg_loop
)

if "!INPUT_FILE_ARG!"=="" ( set "INPUT_FILE_ARG=%~1"
) else if "!REFERENCE_FILE_ARG!"=="" ( set "REFERENCE_FILE_ARG=%~1"
) else if "!OUTPUT_FILE_ARG!"=="" ( set "OUTPUT_FILE_ARG=%~1"
) else ( echo WARNING: Extraneous argument for repair: %~1 )

:next_repair_arg_loop
shift
goto :parse_repair_args_loop

:validate_repair_args
if "!ARGS_OK!"=="false" ( call :show_help_for_sub_command repair & goto :script_error_exit )
if "!INPUT_FILE_ARG!"=="" ( echo ERROR: Missing INPUT_FILE for 'repair'. & call :show_help_for_sub_command repair & goto :script_error_exit )
if "!REFERENCE_FILE_ARG!"=="" ( echo ERROR: Missing REFERENCE_FILE for 'repair'. & call :show_help_for_sub_command repair & goto :script_error_exit )
if "!OUTPUT_FILE_ARG!"=="" ( echo ERROR: Missing OUTPUT_FILE for 'repair'. & call :show_help_for_sub_command repair & goto :script_error_exit )
goto :execute_repair_docker

:execute_repair_docker
echo.
echo ===== REPAIR MP4 (Dockerized) =====
for %%F in ("!INPUT_FILE_ARG!") do set "ABS_INPUT_FILE=%%~fF"
for %%F in ("!REFERENCE_FILE_ARG!") do set "ABS_REFERENCE_FILE=%%~fF"
for %%F in ("!OUTPUT_FILE_ARG!") do set "ABS_OUTPUT_FILE=%%~fF"

if not exist "!ABS_INPUT_FILE!" ( echo ERROR: Input file does not exist: "!ABS_INPUT_FILE!" & goto :script_error_exit )

for %%F in ("!ABS_INPUT_FILE!") do ( set "INPUT_DIR=%%~dpF" & set "INPUT_FILENAME=%%~nxF" )
for %%F in ("!ABS_REFERENCE_FILE!") do ( set "REF_DIR=%%~dpF" & set "REF_FILENAME=%%~nxF" )
for %%F in ("!ABS_OUTPUT_FILE!") do ( set "OUTPUT_DIR=%%~dpF" & set "OUTPUT_FILENAME=%%~nxF" )

if not exist "!OUTPUT_DIR!" (
    echo Creating output directory: "!OUTPUT_DIR!"
    mkdir "!OUTPUT_DIR!"
    if errorlevel 1 ( echo ERROR: Could not create output directory: "!OUTPUT_DIR!" & goto :script_error_exit)
)

echo   Input File (Host): "!ABS_INPUT_FILE!"
echo   Reference File (Host): "!ABS_REFERENCE_FILE!"
echo   Output File (Host): "!ABS_OUTPUT_FILE!"
if defined TECHNIQUE_OPTION ( echo   Technique Option: !TECHNIQUE_OPTION! )

set "DOCKER_VOLUMES=-v "!INPUT_DIR!:/input:ro" -v "!REF_DIR!:/reference:ro" -v "!OUTPUT_DIR!:/output""
set "DOCKER_SCRIPT_ARGS="/input/!INPUT_FILENAME!" "/reference/!REF_FILENAME!" "/output/!OUTPUT_FILENAME!""
if defined TECHNIQUE_OPTION ( set "DOCKER_SCRIPT_ARGS=!DOCKER_SCRIPT_ARGS! !TECHNIQUE_OPTION!" )

set "DOCKER_RUN_CMD=docker run --rm !DOCKER_VOLUMES! "%FULL_IMAGE_NAME%" !DOCKER_SCRIPT_ARGS!"
echo Running: !DOCKER_RUN_CMD!
!DOCKER_RUN_CMD!
set "SCRIPT_RUN_ERRORLEVEL=%ERRORLEVEL%"

if %SCRIPT_RUN_ERRORLEVEL% EQU 0 (
    echo SUCCESS: Repair process completed. Output: "!ABS_OUTPUT_FILE!"
) else (
    echo FAILED: Repair process failed (Error Code: %SCRIPT_RUN_ERRORLEVEL%).
)
goto :end_script_with_code

:: ============================================================================
:: Handle 'info' command and its arguments
:: ============================================================================
:handle_info_command
set "INFO_FILE_ARG="
set "DETAILED_OPTION="
set "ARGS_OK=true"

:parse_info_args_loop
if "%~1"=="" goto :validate_info_args
if /i "%~1"=="--detailed" ( set "DETAILED_OPTION=--detailed" & goto :next_info_arg_loop )
if "!INFO_FILE_ARG!"=="" ( set "INFO_FILE_ARG=%~1"
) else ( echo WARNING: Extraneous argument for info: %~1 )
:next_info_arg_loop
shift
goto :parse_info_args_loop

:validate_info_args
if "!ARGS_OK!"=="false" ( call :show_help_for_sub_command info & goto :script_error_exit )
if "!INFO_FILE_ARG!"=="" ( echo ERROR: Missing MP4_FILE for 'info'. & call :show_help_for_sub_command info & goto :script_error_exit )
goto :execute_info_docker

:execute_info_docker
echo.
echo ===== ANALYZE MP4 (Dockerized) =====
for %%F in ("!INFO_FILE_ARG!") do set "ABS_INFO_FILE=%%~fF"
if not exist "!ABS_INFO_FILE!" ( echo ERROR: MP4 file for info does not exist: "!ABS_INFO_FILE!" & goto :script_error_exit )

for %%F in ("!ABS_INFO_FILE!") do ( set "INFO_DIR=%%~dpF" & set "INFO_FILENAME=%%~nxF" )

echo   Analyzing File (Host): "!ABS_INFO_FILE!"
if defined DETAILED_OPTION ( echo   Detailed: Yes )

set "DOCKER_VOLUMES=-v "!INFO_DIR!:/data:ro""
set "DOCKER_SCRIPT_ARGS="/data/!INFO_FILENAME!""
if defined DETAILED_OPTION ( set "DOCKER_SCRIPT_ARGS=!DOCKER_SCRIPT_ARGS! !DETAILED_OPTION!" )

set "DOCKER_RUN_CMD=docker run --rm !DOCKER_VOLUMES! --entrypoint python "%FULL_IMAGE_NAME%" /app/mp4_info.py !DOCKER_SCRIPT_ARGS!"
echo Running: !DOCKER_RUN_CMD!
!DOCKER_RUN_CMD!
set "SCRIPT_RUN_ERRORLEVEL=%ERRORLEVEL%"

if %SCRIPT_RUN_ERRORLEVEL% EQU 0 (
    echo SUCCESS: Analysis completed.
) else (
    echo FAILED: Analysis failed or file is corrupt (Error Code: %SCRIPT_RUN_ERRORLEVEL%).
    echo Suggestion: Try 'repair' command if the file seems damaged.
)
goto :end_script_with_code

:: ============================================================================
:: Handle 'batch' command and its arguments
:: ============================================================================
:handle_batch_command
set "BATCH_INPUT_DIR_ARG="
set "BATCH_REF_FILE_ARG="
set "BATCH_OUTPUT_DIR_ARG="
set "BATCH_TECHNIQUE_OPTION="
set "ARGS_OK=true"

:parse_batch_args_loop
if "%~1"=="" goto :validate_batch_args
if /i "%~1"=="--technique" (
    if "%~2"=="" ( echo ERROR: --technique option requires a value. & set ARGS_OK=false & goto :validate_batch_args )
    set "BATCH_TECHNIQUE_OPTION=-t %~2"
    shift
    goto :next_batch_arg_loop
)
if /i "%~1"=="-t" (
    if "%~2"=="" ( echo ERROR: -t option requires a value. & set ARGS_OK=false & goto :validate_batch_args )
    set "BATCH_TECHNIQUE_OPTION=-t %~2"
    shift
    goto :next_batch_arg_loop
)

if "!BATCH_INPUT_DIR_ARG!"=="" ( set "BATCH_INPUT_DIR_ARG=%~1"
) else if "!BATCH_REF_FILE_ARG!"=="" ( set "BATCH_REF_FILE_ARG=%~1"
) else if "!BATCH_OUTPUT_DIR_ARG!"=="" ( set "BATCH_OUTPUT_DIR_ARG=%~1"
) else ( echo WARNING: Extraneous argument for batch: %~1 )
:next_batch_arg_loop
shift
goto :parse_batch_args_loop

:validate_batch_args
if "!ARGS_OK!"=="false" ( call :show_help_for_sub_command batch & goto :script_error_exit )
if "!BATCH_INPUT_DIR_ARG!"=="" ( echo ERROR: Missing INPUT_DIR for 'batch'. & call :show_help_for_sub_command batch & goto :script_error_exit )
if "!BATCH_REF_FILE_ARG!"=="" ( echo ERROR: Missing REFERENCE_FILE for 'batch'. & call :show_help_for_sub_command batch & goto :script_error_exit )
if "!BATCH_OUTPUT_DIR_ARG!"=="" ( echo ERROR: Missing OUTPUT_DIR for 'batch'. & call :show_help_for_sub_command batch & goto :script_error_exit )
goto :execute_batch_docker

:execute_batch_docker
echo.
echo ===== BATCH REPAIR MP4 (Dockerized) =====
for %%F in ("!BATCH_INPUT_DIR_ARG!") do set "ABS_BATCH_INPUT_DIR=%%~fF"
for %%F in ("!BATCH_REF_FILE_ARG!") do set "ABS_BATCH_REF_FILE=%%~fF"
for %%F in ("!BATCH_OUTPUT_DIR_ARG!") do set "ABS_BATCH_OUTPUT_DIR=%%~fF"

if not exist "!ABS_BATCH_INPUT_DIR!" ( echo ERROR: Batch input directory does not exist: "!ABS_BATCH_INPUT_DIR!" & goto :script_error_exit )
if not exist "!ABS_BATCH_REF_FILE!" ( echo ERROR: Batch reference file does not exist: "!ABS_BATCH_REF_FILE!" & goto :script_error_exit )

if not exist "!ABS_BATCH_OUTPUT_DIR!" (
    echo Creating batch output directory: "!ABS_BATCH_OUTPUT_DIR!"
    mkdir "!ABS_BATCH_OUTPUT_DIR!"
    if errorlevel 1 (echo ERROR: Could not create batch output dir: "!ABS_BATCH_OUTPUT_DIR!" & goto :script_error_exit)
)

for %%F in ("!ABS_BATCH_REF_FILE!") do ( set "BATCH_REF_DIR=%%~dpF" & set "BATCH_REF_FILENAME=%%~nxF" )

echo   Input Directory (Host): "!ABS_BATCH_INPUT_DIR!"
echo   Reference File (Host): "!ABS_BATCH_REF_FILE!"
echo   Output Directory (Host): "!ABS_BATCH_OUTPUT_DIR!"
if defined BATCH_TECHNIQUE_OPTION ( echo   Technique for all: !BATCH_TECHNIQUE_OPTION! )

set "TOTAL_SUCCESS_COUNT=0"
set "TOTAL_FAIL_COUNT=0"
set "TOTAL_PROCESSED_COUNT=0"
set "TOTAL_SKIPPED_COUNT=0"

for %%I_FILE in ("!ABS_BATCH_INPUT_DIR!\*.mp4") do (
    set /a TOTAL_PROCESSED_COUNT+=1
    set "CURRENT_INPUT_FILENAME=%%~nxI_FILE"
    set "CURRENT_OUTPUT_FILENAME=!CURRENT_INPUT_FILENAME!"
    echo.
    echo --- Processing: !CURRENT_INPUT_FILENAME! ---

    if exist "!ABS_BATCH_OUTPUT_DIR!\!CURRENT_OUTPUT_FILENAME!" (
        echo     Skipping, output file already exists: "!ABS_BATCH_OUTPUT_DIR!\!CURRENT_OUTPUT_FILENAME!"
        set /a TOTAL_SKIPPED_COUNT+=1
        goto :next_batch_file_in_loop
    )

    set "DOCKER_VOLUMES=-v "!ABS_BATCH_INPUT_DIR!:/input:ro" -v "!BATCH_REF_DIR!:/reference:ro" -v "!ABS_BATCH_OUTPUT_DIR!:/output""
    set "DOCKER_SCRIPT_ARGS="/input/!CURRENT_INPUT_FILENAME!" "/reference/!BATCH_REF_FILENAME!" "/output/!CURRENT_OUTPUT_FILENAME!""
    if defined BATCH_TECHNIQUE_OPTION ( set "DOCKER_SCRIPT_ARGS=!DOCKER_SCRIPT_ARGS! !BATCH_TECHNIQUE_OPTION!" )

    set "DOCKER_RUN_CMD=docker run --rm !DOCKER_VOLUMES! "%FULL_IMAGE_NAME%" !DOCKER_SCRIPT_ARGS!"
    echo     Running: !DOCKER_RUN_CMD!
    !DOCKER_RUN_CMD!
    if !ERRORLEVEL! EQU 0 (
        echo     SUCCESS: "!CURRENT_INPUT_FILENAME!" repaired.
        set /a TOTAL_SUCCESS_COUNT+=1
    ) else (
        echo     FAILED: "!CURRENT_INPUT_FILENAME!" repair failed (Error Code: !ERRORLEVEL!).
        set /a TOTAL_FAIL_COUNT+=1
    )
    :next_batch_file_in_loop
)

echo.
echo --- Batch Processing Summary ---
echo   Total MP4 files found: !TOTAL_PROCESSED_COUNT!
echo   Successfully repaired: !TOTAL_SUCCESS_COUNT!
echo   Skipped (already exist): !TOTAL_SKIPPED_COUNT!
echo   Failed to repair: !TOTAL_FAIL_COUNT!
goto :script_success_exit


:: ============================================================================
:: Help Display and Script Exit Points
:: ============================================================================
:show_main_help
echo.
echo ===== MP4 Recovery Toolkit =====
echo.
echo Usage: %~n0 COMMAND [OPTIONS] [ARGUMENTS...]
echo.
echo Commands:
echo   setup                      Build the Docker image '%FULL_IMAGE_NAME%'.
echo                              (Dockerfile must be in the current directory).
echo.
echo   list                       Lists available recovery techniques (runs in Docker).
echo.
echo   repair [options] INPUT_FILE REFERENCE_FILE OUTPUT_FILE
echo                              Repairs a single MP4 file.
echo       INPUT_FILE             Path to the damaged MP4 file.
echo       REFERENCE_FILE         Path to a healthy reference MP4 file.
echo       OUTPUT_FILE            Path where the repaired MP4 file will be saved.
echo       Options:
echo         -t N, --technique N  (Optional) Use specific technique number N.
echo                              If omitted, all techniques are tried by the master script.
echo.
echo   info [options] MP4_FILE
echo                              Analyzes a single MP4_FILE.
echo       MP4_FILE               Path to the MP4 file to analyze.
echo       Options:
echo         --detailed           (Optional) Provides more detailed analysis output.
echo.
echo   batch [options] INPUT_DIR REFERENCE_FILE OUTPUT_DIR
echo                              Repairs all *.mp4 files in INPUT_DIR.
echo       INPUT_DIR              Directory containing damaged MP4 files.
echo       REFERENCE_FILE         Path to a single healthy reference MP4 for all files.
echo       OUTPUT_DIR             Directory where repaired files will be saved.
echo       Options:
echo         -t N, --technique N  (Optional) Apply specific technique N to all files.
echo                              If omitted, all techniques are tried for each file.
echo.
echo   --help, -h                 Show this help message.
echo.
echo Example usage:
echo   %~n0 setup
echo   %~n0 list
echo   %~n0 repair "C:\videos\damaged.mp4" "C:\ref\good.mp4" "C:\out\repaired.mp4"
echo   %~n0 repair damaged.mp4 reference.mp4 output.mp4 -t 2
echo   %~n0 info "my video.mp4" --detailed
echo   %~n0 batch "C:\damaged_files" "C:\ref\global_ref.mp4" "C:\repaired_batch_output" -t 10
echo.
goto :end_script_no_error_exit

:: Helper for showing command-specific help hints on error
:show_help_for_sub_command
echo For correct usage of the '%1' command, see general help:
echo   %~n0 --help
goto :eof


:script_error_exit
echo.
echo SCRIPT EXITED WITH ERROR.
exit /b 1

:script_error_exit_no_cleanup
exit /b 1

:end_script_with_code
echo.
if "%SCRIPT_RUN_ERRORLEVEL%" EQU "0" (
    echo SCRIPT COMMAND COMPLETED SUCCESSFULLY.
) else (
    echo SCRIPT COMMAND COMPLETED WITH ERROR (Code: %SCRIPT_RUN_ERRORLEVEL%).
)
exit /b %SCRIPT_RUN_ERRORLEVEL%

:script_success_exit
echo.
echo SCRIPT COMMAND COMPLETED SUCCESSFULLY.
exit /b 0

:end_script_no_error_exit
exit /b 0
