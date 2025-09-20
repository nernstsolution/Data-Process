#!/bin/bash
# Startup script for Electrolyzer Data Analyzer with Python 3.12

echo "Starting Electrolyzer Data Analyzer..."
echo "Using Python 3.12 with latest packages"

# Activate Python 3.12 virtual environment
source venv312/bin/activate

# Check Python version
echo "Python version: $(python --version)"
echo "Pip version: $(pip --version)"

# Run the application
echo "Launching application..."
python electrolyzer_data_analyzer.py
