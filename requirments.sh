
echo "Making necessary directories..."
mkdir -p tmp
mkdir -p logs
echo "Making necessary directories... Done"

echo "Installing required packages..."
python3 -m pip install --upgrade pip

python3 -m pip install python-dotenv
python3 -m pip install python-telegram-bot -U --pre
python3 -m pip install sqlalchemy
python3 -m pip install pymysql

python3 -m pip install selenium
python3 -m pip install webdriver_manager
python3 -m pip install cryptography
echo "Installing required packages... Done"

echo "Please make sure you have installed the following packages:"
echo "1. Firefox"
echo "2. Geckodriver"

echo "Please make sure you have the environment variables set as in the .env.example file"