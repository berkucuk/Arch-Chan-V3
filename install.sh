#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "Starting Arch Chan AI Assistant Setup..."

# --- API Key Management ---
echo "Please enter your API keys. These keys will be saved to the .env file."

# Gemini AI API Key
read -p "Gemini AI API key: " gemini_api_key
if [ -f .env ]; then
    if grep -q "GEMINI_API_KEY=" .env; then
        sed -i "s/^GEMINI_API_KEY=.*/GEMINI_API_KEY=${gemini_api_key}/" .env
        echo "Gemini API key updated."
    else
        echo "GEMINI_API_KEY=${gemini_api_key}" >> .env
        echo "Gemini API key added to .env file."
    fi
else
    echo "GEMINI_API_KEY=${gemini_api_key}" > .env
    echo ".env file created and Gemini API key added."
fi

# WeatherAPI Key
read -p "WeatherAPI key: " weather_api_key
if [ -f .env ]; then
    if grep -q "WEATHER_API_KEY=" .env; then # Ensure consistent casing for env vars
        sed -i "s/^WEATHER_API_KEY=.*/WEATHER_API_KEY=${weather_api_key}/" .env
        echo "WeatherAPI key updated."
    else
        echo "WEATHER_API_KEY=${weather_api_key}" >> .env
        echo "WeatherAPI key added to .env file."
    fi
else
    echo "WEATHER_API_KEY=${weather_api_key}" > .env
    echo ".env file created and WeatherAPI key added."
fi

echo "API keys saved to .env file."

# --- System Dependency Installation ---
echo "Installing system dependencies..."

# Detect Linux distribution
if [ -f /etc/arch-release ]; then
    echo "Arch Linux detected. Using Pacman..."
    sudo pacman -Syu --noconfirm --needed python python-pip libpng
elif grep -q ID=debian /etc/os-release || grep -q ID=ubuntu /etc/os-release; then
    echo "Debian/Ubuntu based system detected. Using APT..."
    sudo apt update
    sudo apt install -y python3 python3-venv python3-pip libpng-dev # libpng-dev for build dependencies
else
    echo "Unsupported Linux distribution. Please install python3, python3-venv, and pip manually."
    exit 1
fi

# --- Python Virtual Environment Setup ---
echo "Creating Python virtual environment and installing dependencies..."

# Ensure current directory is where the script is
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment 'venv' created."
else
    echo "Virtual environment 'venv' already exists."
fi

# Activate virtual environment for pip installation
source venv/bin/activate

pip install --no-cache-dir -r requirements.txt
echo "Python dependencies installed into the virtual environment."

deactivate # Deactivate after installation

# --- Desktop Entry Creation ---
echo "Creating desktop shortcut..."

# Create a temporary .desktop file to modify paths
TEMP_DESKTOP=$(mktemp)
cat <<EOF > "$TEMP_DESKTOP"
[Desktop Entry]
Name=Arch Chan AI Assistant
Comment=Your personal AI assistant
Exec=$SCRIPT_DIR/run.sh # Point to the original run.sh location
Icon=$SCRIPT_DIR/icons/arch-chan_mini.png # Point to the original icon location
Terminal=false
Type=Application
Categories=Utility;Education;
EOF

chmod +x "$TEMP_DESKTOP"
cp "$TEMP_DESKTOP" ~/.local/share/applications/Arch-Chan-AI.desktop
rm "$TEMP_DESKTOP"

echo "Desktop shortcut created: ~/.local/share/applications/Arch-Chan-AI.desktop"
echo "Installation complete! To launch the application, use the desktop shortcut or run '$SCRIPT_DIR/run.sh'."