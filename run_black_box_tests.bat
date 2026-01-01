@echo off
REM Automated Black Box Testing Script for Windows

echo ========================================
echo Cenaris Phase 1 - Black Box Testing
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install test dependencies
echo Installing test dependencies...
pip install -r tests\requirements-test.txt

REM Check if application is running
echo.
echo Checking if application is running at http://localhost:5000...
curl -s http://localhost:5000 >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo WARNING: Application is not running!
    echo Please start the application first: python run.py
    echo.
    pause
    exit /b 1
)

echo Application is running!
echo.

REM Create test report directory
if not exist "test-reports\" mkdir test-reports

REM Run tests
echo ========================================
echo Running Black Box Tests...
echo ========================================
echo.

REM Run all tests with HTML report
pytest tests\test_black_box_phase1.py ^
    -v ^
    --tb=short ^
    --html=test-reports\black-box-report.html ^
    --self-contained-html ^
    -s

echo.
echo ========================================
echo Test Execution Complete!
echo ========================================
echo.
echo Test report saved to: test-reports\black-box-report.html
echo.

pause
