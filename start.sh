#!/bin/bash
# TOPGEE Investment Management System Startup

cd "$(dirname "$0")"

echo "============================================================"
echo "🚀 Starting TOPGEE Investment Management System..."
echo "============================================================"

# Check dependencies
if ! python3 -c "import flask" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    pip3 install -q -r requirements.txt
fi

# Create data directory
mkdir -p data reports

# Start the system
python3 app.py
