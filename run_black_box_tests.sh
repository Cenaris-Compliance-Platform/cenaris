#!/bin/bash
# Automated Black Box Testing Script for Linux/Mac

echo "========================================"
echo "Cenaris Phase 1 - Black Box Testing"
echo "========================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install test dependencies
echo "Installing test dependencies..."
pip install -r tests/requirements-test.txt

# Check if application is running
echo ""
echo "Checking if application is running at http://localhost:5000..."
if ! curl -s http://localhost:5000 > /dev/null 2>&1; then
    echo ""
    echo "WARNING: Application is not running!"
    echo "Please start the application first: python run.py"
    echo ""
    exit 1
fi

echo "Application is running!"
echo ""

# Create test report directory
mkdir -p test-reports

# Run tests
echo "========================================"
echo "Running Black Box Tests..."
echo "========================================"
echo ""

# Run all tests with HTML report
pytest tests/test_black_box_phase1.py \
    -v \
    --tb=short \
    --html=test-reports/black-box-report.html \
    --self-contained-html \
    -s

echo ""
echo "========================================"
echo "Test Execution Complete!"
echo "========================================"
echo ""
echo "Test report saved to: test-reports/black-box-report.html"
echo ""
