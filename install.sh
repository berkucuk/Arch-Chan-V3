#!/bin/bash
# Groq AI API anahtarı
read -p "Gemini AI API key: " gemini_api_key
if [ -f .env ]; then
    if grep -q "GEMINI_API_KEY=" .env; then
        sed -i "s/^GEMINI_API_KEY=.*/GEMINI_API_KEY=${gemini_api_key}/" .env
        echo "Gemini API anahtarı güncellendi."
    else
        echo "GEMINI_API_KEY=${gemini_api_key}" >> .env
        echo "Gemini API anahtarı .env dosyasına eklendi."
    fi
else
    echo "GEMINI_API_KEY=${gemini_api_key}" > .env
    echo ".env dosyası oluşturuldu ve Groq API anahtarı eklendi."
fi

# WeatherAPI anahtarı
read -p "WeatherAPI key: " weather_api_key
if [ -f .env ]; then
    if grep -q "Weather_Api_Key=" .env; then
        sed -i "s/^Weather_Api_Key=.*/Weather_Api_Key=${weather_api_key}/" .env
        echo "WeatherAPI anahtarı güncellendi."
    else
        echo "Weather_Api_Key=${weather_api_key}" >> .env
        echo "WeatherAPI anahtarı .env dosyasına eklendi."
    fi
else
    echo "Weather_Api_Key=${weather_api_key}" > .env
    echo ".env dosyası oluşturuldu ve WeatherAPI anahtarı eklendi."
fi

sudo pacman -S python-virtualenv libpng --noconfirm --needed
sudo apt install python3-venv
chmod +x Arch-Chan-AI.desktop
mkdir -p ~/.local/share/applications/
cp Arch-Chan-AI.desktop ~/.local/share/applications/
sudo mkdir /usr/share/Arch-Chan-AI
sudo cp .env /usr/share/Arch-Chan-AI
sudo python3 -m venv /usr/share/Arch-Chan-AI/python-env
sudo /usr/share/Arch-Chan-AI/python-env/bin/pip3 install -r requirements.txt
sudo cp mcp_server.py /usr/share/Arch-Chan-AI
sudo cp arch-chan.py /usr/share/Arch-Chan-AI
sudo cp run.sh /usr/share/Arch-Chan-AI
sudo cp -r icons /usr/share/Arch-Chan-AI
sudo mkdir /usr/share/Arch-Chan-AI/temp_voice
