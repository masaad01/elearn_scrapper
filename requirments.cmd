@echo off

echo "Making necessary directories..."
mkdir tmp
mkdir logs
echo "Making necessary directories... Done"

echo "Installing required packages..."
python -m pip install --upgrade pip

python -m pip install python-dotenv
python -m pip install python-telegram-bot -U --pre
python -m pip install sqlalchemy
python -m pip install pymysql

python -m pip install selenium
python -m pip install webdriver_manager
python -m pip install cryptography
echo "Installing required packages... Done"

echo "Please make sure you have installed the following packages:"
echo "1. Firefox"
echo "2. Geckodriver"

echo "Please make sure you have the environment variables set as in the .env.example file"
