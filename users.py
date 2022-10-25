import json
import logging
import re
from random import randrange
from uuid import uuid4

import sqlalchemy as db
from cryptography.fernet import Fernet

from database_connection import DatabaseConnection


def main():
    logging.basicConfig(level=logging.ERROR, encoding="utf-8",
                        filename="./logs/users.log", format=f"%(levelname)s   %(asctime)s  \n%(message)s \n{'='*100}\n", filemode="w")


def encrypt_password(password: str) -> bytes:
    with open("config.json", "r") as f:
        config = json.load(f)
        key = config["encryption_key"].encode()
        salt = str(randrange(0, int(1e10))).zfill(10)
        encPassword = Fernet(key).encrypt(f"{password}{salt}".encode())
        return encPassword


def dycrypt_password(encPassword: bytes) -> str:
    if type(encPassword) != bytes:
        return None
    with open("config.json", "r") as f:
        config = json.load(f)
        key = config["encryption_key"].encode()
        decPassword = Fernet(key).decrypt(encPassword).decode()
        decPassword = decPassword[:-10]
        return decPassword


class User:
    def __init__(self, **kwargs):
        self.set_user_id(str(uuid4()))

        self.set_email(kwargs.get("email", None))
        self.set_password(kwargs.get("password", None))
        self.set_is_active(kwargs.get("active", False))
        self.set_chat_id(kwargs.get("chat_id", None))
        
    def __repr__(self):
        return f"User({self._user_id}, {self._email}, {self._is_active}, {self._chat_id})"

    def __str__(self):
        return f"User ID: {self._user_id}\nEmail: {self._email},\nIs Active: {self._is_active}, \nChat ID: {self._chat_id}"

    def __enter__(self):
        return self

    def save_to_db(self):
        old_user = User.get_user(self._user_id)
        if old_user is None:
            User.insert_user(self)
        else:
            User.update_user(self)

    def set_user_id(self, user_id):
        if type(user_id) is not str or len(user_id) != 36:
            raise TypeError("User ID must be a string of length 36. (UUID)")
        self._user_id = user_id

    def get_user_id(self):
        return self._user_id

    def set_email(self, email):
        email_pat = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]*just\.edu\.jo\b'

        if email is None:
            self._email = None
            return
        if type(email) is not str:
            raise TypeError("Email must be a string.")
        if re.match(email_pat, email):
            self._email = email
        else:
            raise ValueError("Please enter a valid email address. \nEmail must be from (just.edu.jo)")

    def get_email(self):
        return self._email

    def set_password(self, password: str):

        if password is None:
            self._password = None
            return
        if type(password) is bytes:
            self.set_encrypted_password(password)
            return
        if type(password) is not str:
            raise TypeError("Password must be a string.")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if len(password) > 100:
            raise ValueError("Password must be less than 100 characters long.")
        self._password = encrypt_password(password)

    def set_encrypted_password(self, password: bytes):
        if type(password) is not bytes:
            raise TypeError("Password must be a bytes object.")
        if len(password) < 20:
            raise ValueError("Password too short.")
        self._password = password

    def get_password(self):
        return dycrypt_password(self._password)

    def set_is_active(self, is_active):
        if is_active in [0, 1]:
            self._is_active = bool(is_active)
        elif type(is_active) is not bool:
            raise TypeError("Is Active must be a boolean.")
        self._is_active = is_active

    def get_is_active(self):
        return self._is_active

    def set_chat_id(self, chat_id):
        if chat_id is None:
            self._chat_id = None
            return
        if type(chat_id) is not int:
            raise TypeError("Chat ID must be an integer.")
        self._chat_id = chat_id
    
    def get_chat_id(self):
        return self._chat_id

    @staticmethod
    def get_all_users():
        with DatabaseConnection() as connection:
            users = connection.get_table("user")
            query = db.select([users])
            result_proxy = connection.execute(query)
            if result_proxy is None:
                return []
            result_set = result_proxy.fetchall()

        user_list = []
        for row in result_set:
            user = User(**row)
            user.set_user_id(row["user_id"])
            user_list.append(user)
        return user_list

    @staticmethod
    def get_user(user_id):
        with DatabaseConnection() as connection:
            users = connection.get_table("user")
            query = db.select([users]).where(users.columns.user_id == user_id)
            result_proxy = connection.execute(query)
            if result_proxy is None:
                return None
            row = result_proxy.fetchone()
            if row is None:
                return None

        user = User(**row)
        user.set_user_id(row["user_id"])
        return user

    @staticmethod
    def get_users_by(key, value):
        with DatabaseConnection() as connection:
            users = connection.get_table("user")
            query = db.select([users]).where(users.columns[key] == value)
            result_proxy = connection.execute(query)
            if result_proxy is None:
                return None
            result_set = result_proxy.fetchall()

        user_list = []
        for row in result_set:
            user = User(**row)
            user.set_user_id(row["user_id"])
            user_list.append(user)
        return user_list

    @staticmethod
    def insert_user(user):
        with DatabaseConnection() as connection:
            users = connection.get_table("user")
            query = db.insert(users).values(
                user_id=user._user_id, email=user._email, password=user._password, active=user._is_active, chat_id=user._chat_id)
            result = connection.execute(query)

        if result is None:
            return False
        return True

    @staticmethod
    def update_user(user) -> int:
        with DatabaseConnection() as connection:
            users = connection.get_table("user")
            query = db.update(users).where(users.columns.user_id == user._user_id).values(
                email=user._email, password=user._password, active=user._is_active, chat_id=user._chat_id)
            result = connection.execute(query)

        if result is None:
            return 0
        return result.rowcount


if __name__ == "__main__":
    main()
    # for i in range(10):
    #     user = User(email=f"email{randrange(0,20)}@abc.com", password=f"dsf5131dfg", is_active=True, chat_id=randrange(1000000000, 9999999999))
    #     if User.insert_user(user):
    #         print("User inserted.", i)
    