#!/bin/bash

# Fitness Command Center - Streamlit Dashboard Restart Script
# ============================================================

SCRIPT_DIR="/home/pi/Documents/AI_Fitness"
VENV_PATH="$SCRIPT_DIR/venv/bin"
DASHBOARD_FILE="dashboard_local_server.py"
LOG_FILE="$SCRIPT_DIR/dashboard.log"
PORT=8501

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Fitness Command Center - Restart${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 1. Move to the directory
echo -e "${YELLOW}[1/6]${NC} Changing to project directory..."
cd "$SCRIPT_DIR" || { echo -e "${RED}ERROR: Could not cd to $SCRIPT_DIR${NC}"; exit 1; }
echo -e "      ${GREEN}OK${NC} - Working directory: $(pwd)"
echo ""

# 2. Check if virtual environment exists
echo -e "${YELLOW}[2/6]${NC} Checking virtual environment..."
if [ -f "$VENV_PATH/streamlit" ]; then
    echo -e "      ${GREEN}OK${NC} - Streamlit found in venv"
else
    echo -e "      ${RED}ERROR${NC} - Streamlit not found at $VENV_PATH/streamlit"
    echo -e "      Run: $VENV_PATH/pip install streamlit"
    exit 1
fi
echo ""

# 3. Kill any existing instances
echo -e "${YELLOW}[3/6]${NC} Stopping existing dashboard processes..."
OLD_PIDS=$(pgrep -f "streamlit.*$DASHBOARD_FILE" 2>/dev/null)
if [ -n "$OLD_PIDS" ]; then
    echo -e "      Found running processes: $OLD_PIDS"
    pkill -f "streamlit.*$DASHBOARD_FILE"
    sleep 2
    # Verify they're dead
    REMAINING=$(pgrep -f "streamlit.*$DASHBOARD_FILE" 2>/dev/null)
    if [ -n "$REMAINING" ]; then
        echo -e "      ${YELLOW}WARN${NC} - Force killing stubborn processes..."
        pkill -9 -f "streamlit.*$DASHBOARD_FILE"
        sleep 1
    fi
    echo -e "      ${GREEN}OK${NC} - Old processes terminated"
else
    echo -e "      ${GREEN}OK${NC} - No existing processes found"
fi
echo ""

# 4. Check if port is available
echo -e "${YELLOW}[4/6]${NC} Checking port $PORT availability..."
PORT_CHECK=$(ss -tuln | grep ":$PORT " 2>/dev/null)
if [ -n "$PORT_CHECK" ]; then
    echo -e "      ${YELLOW}WARN${NC} - Port $PORT is in use, attempting to free..."
    fuser -k $PORT/tcp 2>/dev/null
    sleep 2
fi
echo -e "      ${GREEN}OK${NC} - Port $PORT is available"
echo ""

# 5. Start the new Streamlit dashboard
echo -e "${YELLOW}[5/6]${NC} Starting Streamlit dashboard..."
echo -e "      Log file: $LOG_FILE"
nohup "$VENV_PATH/streamlit" run "$DASHBOARD_FILE" \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false \
    > "$LOG_FILE" 2>&1 &

NEW_PID=$!
echo -e "      Started with PID: $NEW_PID"
sleep 4
echo ""

# 6. Verify dashboard is running
echo -e "${YELLOW}[6/6]${NC} Verifying dashboard status..."
RUNNING_PID=$(pgrep -f "streamlit.*$DASHBOARD_FILE" 2>/dev/null | head -1)

if [ -n "$RUNNING_PID" ]; then
    echo -e "      ${GREEN}OK${NC} - Dashboard is running (PID: $RUNNING_PID)"

    # Check if port is listening
    sleep 2
    PORT_LISTEN=$(ss -tuln | grep ":$PORT " 2>/dev/null)
    if [ -n "$PORT_LISTEN" ]; then
        echo -e "      ${GREEN}OK${NC} - Listening on port $PORT"
    else
        echo -e "      ${YELLOW}WARN${NC} - Port not yet listening (may still be starting)"
    fi

    # Get IP address
    IP_ADDR=$(hostname -I | awk '{print $1}')

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Dashboard Started Successfully!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "  Local URL:    ${BLUE}http://localhost:$PORT${NC}"
    echo -e "  Network URL:  ${BLUE}http://$IP_ADDR:$PORT${NC}"
    echo ""
    echo -e "  Log file:     $LOG_FILE"
    echo -e "  To view logs: ${YELLOW}tail -f $LOG_FILE${NC}"
    echo -e "  To stop:      ${YELLOW}pkill -f 'streamlit.*$DASHBOARD_FILE'${NC}"
    echo ""
else
    echo -e "      ${RED}ERROR${NC} - Dashboard failed to start!"
    echo ""
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}  Startup Failed - Check Logs${NC}"
    echo -e "${RED}========================================${NC}"
    echo ""
    echo "  Last 20 lines of log:"
    echo "  ----------------------"
    tail -20 "$LOG_FILE" 2>/dev/null || echo "  (No log file found)"
    echo ""
    exit 1
fi
