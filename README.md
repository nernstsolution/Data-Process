# Electrolyzer Data Analyzer

A Python application for analyzing and visualizing electrolyzer test data from InfluxDB exports.

## Features

### Step 1: Raw Data Navigation

- **Directory Navigation**: Browse and select data folders
- **File List Reader**: View and select multiple CSV files
- **Data Loading**: Load selected files into pandas DataFrames

### Future Steps (To be implemented)

- Data Processing
- Data Visualization
- Export/Report Generation

## Installation

### Option 1: Quick Start (Recommended)

Use the provided startup script:

```bash
./run_app.sh
```

### Option 2: Manual Setup

1. **Install Python 3.12** (if not already installed):

```bash
brew install python@3.12 python-tk@3.12
```

2. **Create virtual environment**:

```bash
python3.12 -m venv venv312
source venv312/bin/activate
```

3. **Install dependencies**:

```bash
pip install -r requirements.txt
```

4. **Run the application**:

```bash
python electrolyzer_data_analyzer.py
```

### System Requirements

- **Python**: 3.12.11 (latest)
- **macOS**: Optimized for macOS with touchpad responsiveness fixes
- **Packages**: pandas 2.3.2, numpy 2.3.3, matplotlib 3.10.6, seaborn 0.13.2

## Usage

1. **Select Data Directory**: Use the "Browse" button to select your data folder (defaults to "InfluxDB raw data")
2. **Read Files**: Click "Read Files" to scan for CSV files in the directory
3. **Select Files**: Choose one or multiple files from the list
4. **Load Data**: The selected files will be loaded into DataFrames for further processing

## Data Format

The application expects CSV files exported from InfluxDB with the following structure:

- First 3 rows contain metadata (group, datatype, default)
- Data starts from row 4
- Columns include various electrolyzer parameters (voltage, current, temperature, etc.)

## Project Structure

```
Data Process/
├── InfluxDB raw data/          # Raw data files
├── electrolyzer_data_analyzer.py  # Main application
├── requirements.txt            # Dependencies
└── README.md                  # This file
```
