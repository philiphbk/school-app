#!/bin/bash
# ─────────────────────────────────────────────
#  School Management System — Startup Script
#  For Mac / Linux
# ─────────────────────────────────────────────

# Check Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed."
    echo "   Please download it from https://python.org/downloads"
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"

# Move to script directory
cd "$(dirname "$0")"

# Kill any previous instance on port 8080
echo "🔄 Checking for existing server on port 8080..."
OLD_PID=$(lsof -ti tcp:8080 2>/dev/null)
if [ -n "$OLD_PID" ]; then
    echo "⚠️  Stopping old server (PID $OLD_PID)..."
    kill -9 $OLD_PID 2>/dev/null
    sleep 1
fi

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║     GISL Schools Management System     ║"
echo "║     Starting up...                      ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Start server and open browser after 2 seconds
python3 server.py &
SERVER_PID=$!
sleep 2

# Open browser (Mac/Linux)
if command -v open &> /dev/null; then
    open http://localhost:8080
elif command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:8080
fi

echo ""
echo "🌐 App running at: http://localhost:8080"
echo "👤 Login: admin@school.com"
echo "🔑 Password: admin123"
echo ""
echo "Press Ctrl+C to stop the server."
echo ""

wait $SERVER_PID
