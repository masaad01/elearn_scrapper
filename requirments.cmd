@echo off

mkdir tmp
mkdir logs


python -m pip install python-telegram-bot -U --pre
python -m pip install sqlalchemy
python -m pip install pymysql

python -m pip install selenium
python -m pip install webdriver_manager
python -m pip install cryptography