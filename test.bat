@echo off
setlocal enabledelayedexpansion

:: Test script for MP4 Repair Docker container on Windows
:: This version relies on the Docker container for all operations

:: Create test directory
if not exist tests mkdir tests

:: Color codes for output
set "RED=[91m"
set "GREEN=[92m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "NC=[0m"

echo %BLUE%===== MP4 REPAIR TOOL TEST SCRIPT =====%NC%

:: Check if Docker is installed and running
echo %BLUE%===== CHECKING DOCKER INSTALLATION =====%NC%
where docker >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo %RED%Docker not found. Please install Docker Desktop to run this test.%NC%
    exit /b 1
)

:: Check if Docker is running
docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo %RED%Docker is installed but not running or not responding.%NC%
    echo Please start Docker Desktop and try again.
    exit /b 1
)

echo %GREEN%Docker is installed and running.%NC%

:: Build the Docker image if it doesn't exist
echo.
echo %BLUE%===== CHECKING/BUILDING DOCKER IMAGE =====%NC%
docker image inspect mp4-recovery-toolkit >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo %YELLOW%Docker image 'mp4-recovery-toolkit' not found. Building it now...%NC%
    
    :: Check if Dockerfile exists
    if not exist Dockerfile (
        echo %RED%Error: Dockerfile not found in the current directory.%NC%
        echo Please ensure the Dockerfile is in the same directory as this script.
        exit /b 1
    )
    
    :: Build the Docker image
    echo Building Docker image 'mp4-recovery-toolkit'...
    docker build -t mp4-recovery-toolkit .
    
    :: Check if build was successful
    if %ERRORLEVEL% NEQ 0 (
        echo %RED%Failed to build Docker image. Please check the Dockerfile for errors.%NC%
        exit /b 1
    ) else (
        echo %GREEN%Successfully built Docker image 'mp4-recovery-toolkit'.%NC%
    )
) else (
    echo %GREEN%Docker image 'mp4-recovery-toolkit' already exists.%NC%
)

:: Generate a test "good" MP4 file if it doesn't exist
if not exist tests\good.mp4 (
    echo.
    echo %YELLOW%Generating test 'good' MP4 file using Docker container...%NC%
    :: Use FFmpeg from the container to create a test video
    docker run --rm -v "%cd%\tests:/data" --entrypoint ffmpeg mp4-recovery-toolkit -f lavfi -i testsrc=duration=5:size=1280x720:rate=30 -c:v libx264 -profile:v baseline /data/good.mp4
    
    :: Check if file was created successfully
    if not exist tests\good.mp4 (
        echo %RED%Failed to create test video file.%NC%
        exit /b 1
    ) else (
        echo %GREEN%Successfully created test video.%NC%
    )
) else (
    echo.
    echo %GREEN%Using existing test 'good' MP4 file%NC%
)

:: Generate a "bad" MP4 file by truncating the good one
if not exist tests\truncated.mp4 (
    echo.
    echo %YELLOW%Generating test 'truncated' MP4 file...%NC%
    :: Get file size
    for %%F in (tests\good.mp4) do set "filesize=%%~zF"
    :: Calculate 90%% of the file size
    set /a "truncsize=!filesize! * 9 / 10"
    :: Create truncated file using PowerShell
    powershell -Command "& {$file = [System.IO.File]::OpenRead('tests\good.mp4'); $buffer = New-Object byte[] !truncsize!; $file.Read($buffer, 0, !truncsize!); $file.Close(); [System.IO.File]::WriteAllBytes('tests\truncated.mp4', $buffer)}"
) else (
    echo.
    echo %GREEN%Using existing test 'truncated' MP4 file%NC%
)

:: Create another corrupt file with a different corruption method
if not exist tests\corrupted_data.mp4 (
    echo.
    echo %YELLOW%Generating a corrupted data MP4 file with different corruption type...%NC%
    :: Copy the good file
    copy tests\good.mp4 tests\corrupted_data.mp4 >nul
    :: Corrupt the middle of the file using PowerShell
    powershell -Command "& {$file = [System.IO.File]::OpenWrite('tests\corrupted_data.mp4'); $file.Position = 10000; $zeros = New-Object byte[] 1000; $file.Write($zeros, 0, 1000); $file.Close()}"
) else (
    echo.
    echo %GREEN%Using existing corrupted data test file%NC%
)

:: Run tests using Docker container
echo.
echo %BLUE%===== TEST 1: CHECKING GOOD FILE INFO =====%NC%
docker run --rm -v "%cd%\tests:/data" mp4-recovery-toolkit --info /data/good.mp4
if %ERRORLEVEL% NEQ 0 (
    echo %YELLOW%Warning: Info check of good file returned non-zero exit code.%NC%
    echo This might indicate an issue with the file or the container setup.
)

echo.
echo %BLUE%===== TEST 2: REPAIRING TRUNCATED FILE =====%NC%
echo Running repair on truncated file...
docker run --rm -v "%cd%\tests:/data" mp4-recovery-toolkit /data/truncated.mp4 /data/good.mp4 /data/repaired_truncated.mp4
if %ERRORLEVEL% NEQ 0 (
    echo %YELLOW%Warning: Repair process for truncated file returned non-zero exit code.%NC%
    echo The repair might still have produced usable output.
)

echo.
echo %BLUE%===== TEST 3: REPAIRING CORRUPTED DATA FILE =====%NC%
echo Running repair on corrupted data file...
docker run --rm -v "%cd%\tests:/data" mp4-recovery-toolkit /data/corrupted_data.mp4 /data/good.mp4 /data/repaired_corrupted.mp4
if %ERRORLEVEL% NEQ 0 (
    echo %YELLOW%Warning: Repair process for corrupted data file returned non-zero exit code.%NC%
    echo The repair might still have produced usable output.
)

:: Verify results using ffprobe from Docker container
echo.
echo %BLUE%===== VERIFYING REPAIR RESULTS =====%NC%

:: Check repaired files
if exist tests\repaired_truncated.mp4 (
    for %%F in (tests\repaired_truncated.mp4) do set "size=%%~zF"
    echo %GREEN%Repaired truncated file (size: !size! bytes)%NC%
    
    :: Check if ffprobe can read the file using Docker
    docker run --rm -v "%cd%\tests:/data" --entrypoint ffprobe_tool mp4-recovery-toolkit -v error /data/repaired_truncated.mp4
    if !ERRORLEVEL! EQU 0 (
        echo %GREEN%✓ Repaired truncated file is valid%NC%
    ) else (
        echo %RED%✗ Repaired truncated file validation failed%NC%
    )
) else (
    echo %RED%✗ Failed to repair truncated file%NC%
)

if exist tests\repaired_corrupted.mp4 (
    for %%F in (tests\repaired_corrupted.mp4) do set "size=%%~zF"
    echo %GREEN%Repaired corrupted data file (size: !size! bytes)%NC%
    
    :: Check if ffprobe can read the file using Docker
    docker run --rm -v "%cd%\tests:/data" --entrypoint ffprobe_tool mp4-recovery-toolkit -v error /data/repaired_corrupted.mp4
    if !ERRORLEVEL! EQU 0 (
        echo %GREEN%✓ Repaired corrupted data file is valid%NC%
    ) else (
        echo %RED%✗ Repaired corrupted data file validation failed%NC%
    )
) else (
    echo %RED%✗ Failed to repair corrupted data file%NC%
)

:: Final summary
echo.
echo %BLUE%===== TEST SUMMARY =====%NC%

:: Count successful repairs
set success_count=0
set total_tests=2

if exist tests\repaired_truncated.mp4 (
    docker run --rm -v "%cd%\tests:/data" --entrypoint ffprobe_tool mp4-recovery-toolkit -v error /data/repaired_truncated.mp4
    if !ERRORLEVEL! EQU 0 set /a success_count+=1
)

if exist tests\repaired_corrupted.mp4 (
    docker run --rm -v "%cd%\tests:/data" --entrypoint ffprobe_tool mp4-recovery-toolkit -v error /data/repaired_corrupted.mp4
    if !ERRORLEVEL! EQU 0 set /a success_count+=1
)

:: Print summary
echo %BLUE%Successful repairs: !success_count! / !total_tests!%NC%

if !success_count! EQU !total_tests! (
    echo.
    echo %GREEN%ALL TESTS PASSED! MP4 Repair Tool is working correctly.%NC%
) else if !success_count! GTR 0 (
    echo.
    echo %YELLOW%PARTIAL SUCCESS: Some tests passed, but not all.%NC%
    echo The tool is working but may have limitations with certain types of corruption.
) else (
    echo.
    echo %RED%ALL TESTS FAILED: The repair tool is not functioning correctly.%NC%
    echo Please check the logs above for more details.
    exit /b 1
)

:: Additional functionality - show tool information
echo.
echo %BLUE%===== MP4 REPAIR TOOL INFORMATION =====%NC%
echo.
echo %YELLOW%Available Commands:%NC%
echo Running the recovery tool with --help to show available options:
docker run --rm mp4-recovery-toolkit --help

echo.
echo %YELLOW%Available Repair Techniques:%NC%
echo Running the recovery tool with --list to show available techniques:
docker run --rm mp4-recovery-toolkit --list

echo.
echo %YELLOW%Sample Usage:%NC%
echo docker run --rm -v "C:\path\to\videos:/data" mp4-recovery-toolkit /data/damaged.mp4 /data/reference.mp4 /data/output.mp4
echo.
echo For analyzing a file without repair:
echo docker run --rm -v "C:\path\to\videos:/data" --entrypoint mp4info mp4-recovery-toolkit /data/video.mp4
echo.
echo For using FFmpeg directly:
echo docker run --rm -v "C:\path\to\videos:/data" --entrypoint ffmpeg_tool mp4-recovery-toolkit [ffmpeg options]
echo.
echo For using FFprobe directly:
echo docker run --rm -v "C:\path\to\videos:/data" --entrypoint ffprobe_tool mp4-recovery-toolkit [ffprobe options]

echo.
echo %GREEN%Tests completed. MP4 Repair Tool is ready to use.%NC%
exit /b 0