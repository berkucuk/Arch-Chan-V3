#!/bin/bash

# --- Configuration ---
# Define log files
SERVER_LOG="mcp_server.log"
GUI_LOG="arch_chan_gui.log" # Renamed log for clarity

# Define log directory
LOG_DIR="logs"

# Define Python executable path within the virtual environment
PYTHON_VENV_EXEC="venv/bin/python3"

# Define Python script names
SERVER_SCRIPT="mcp_server.py"
GUI_SCRIPT="arch_chan.py" # Corrected GUI script name

# --- Pre-flight Checks ---
# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Check if virtual environment exists
if [ ! -f "$PYTHON_VENV_EXEC" ]; then
    echo "Error: Virtual environment 'venv' not found or '$PYTHON_VENV_EXEC' does not exist."
    echo "Please ensure you have created and installed dependencies in your virtual environment."
    echo "Example: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Check if Python scripts exist
if [ ! -f "$SERVER_SCRIPT" ]; then
    echo "Error: Server script '$SERVER_SCRIPT' not found in the current directory."
    exit 1
fi
if [ ! -f "$GUI_SCRIPT" ]; then
    echo "Error: GUI script '$GUI_SCRIPT' not found in the current directory."
    exit 1
fi

# --- Start Server ---
echo "Starting Arch Chan MCP server in the background..."
echo "Server logs will be saved to $LOG_DIR/$SERVER_LOG"

# Start the server using nohup to ensure it runs even if the terminal closes.
# Redirect all output (stdout and stderr) to the server log file.
# The '&' sends the process to the background.
nohup "$PYTHON_VENV_EXEC" "$SERVER_SCRIPT" > "$LOG_DIR/$SERVER_LOG" 2>&1 &

# Get the Process ID (PID) of the last background command (our server)
SERVER_PID=$!
echo "Arch Chan MCP server started with PID: $SERVER_PID"

# Wait a moment for the server to fully initialize
echo "Waiting 3 seconds for the server to initialize..."
sleep 3

# Check if server process is still running after sleep
if ! kill -0 "$SERVER_PID" > /dev/null 2>&1; then
    echo "Error: MCP server (PID $SERVER_PID) might not have started successfully or crashed."
    echo "Please check $LOG_DIR/$SERVER_LOG for errors."
    exit 1
fi

# --- Start GUI ---
echo "Starting Arch Chan GUI chatbot in the foreground..."
echo "GUI logs will be saved to $LOG_DIR/$GUI_LOG"

# Start the GUI in the foreground. Its output is also redirected to a log file.
# The script will wait here until the GUI application is closed.
"$PYTHON_VENV_EXEC" "$GUI_SCRIPT" > "$LOG_DIR/$GUI_LOG" 2>&1

echo "Arch Chan GUI chatbot closed."

# --- Cleanup ---
# Attempt to terminate the background server process
echo "Attempting to terminate MCP server (PID: $SERVER_PID)..."
kill "$SERVER_PID"

# Give the server a moment to shut down gracefully
sleep 1

# Check if the server process is still running after attempting to kill it
if kill -0 "$SERVER_PID" > /dev/null 2>&1; then
    echo "Warning: MCP server (PID $SERVER_PID) did not terminate gracefully. Forcing kill."
    kill -9 "$SERVER_PID" # Force kill if it's still running
fi

echo "Arch Chan session ended."