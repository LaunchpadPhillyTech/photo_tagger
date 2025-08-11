#!/bin/bash
# SQLite3 Installation Script for Photo Tagger

echo "📦 Installing SQLite3 dependencies..."

# For Ubuntu/Debian systems
if command -v apt-get &> /dev/null; then
    echo "🔧 Installing via apt-get..."
    sudo apt-get update
    sudo apt-get install -y sqlite3 libsqlite3-dev python3-dev
fi

# For CentOS/RHEL/Fedora systems
if command -v yum &> /dev/null; then
    echo "🔧 Installing via yum..."
    sudo yum install -y sqlite sqlite-devel python3-devel
fi

# For Alpine Linux (commonly used in Docker)
if command -v apk &> /dev/null; then
    echo "🔧 Installing via apk..."
    apk add --no-cache sqlite sqlite-dev python3-dev
fi

# Verify SQLite3 installation
if command -v sqlite3 &> /dev/null; then
    echo "✅ SQLite3 installed successfully!"
    echo "📋 SQLite3 version: $(sqlite3 --version)"
else
    echo "❌ SQLite3 installation failed!"
    exit 1
fi

# Test Python SQLite3 import
python3 -c "import sqlite3; print('✅ Python SQLite3 import successful!')" || {
    echo "❌ Python SQLite3 import failed!"
    echo "🔄 Installing pysqlite3 as fallback..."
    pip3 install pysqlite3-binary
}

echo "🎉 SQLite3 setup complete!"
