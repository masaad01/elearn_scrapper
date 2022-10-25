import json
import logging
from urllib.parse import quote_plus as qp

import sqlalchemy as db
from pymysql import err as sqlError


def main():
    logging.basicConfig(level=logging.ERROR, encoding="utf-8",
                        filename="./logs/database.log", format=f"%(levelname)s   %(asctime)s  \n%(message)s \n{'='*100}\n", filemode="w")


class DatabaseConnection:
    with open("config.json", "r") as f:
        config = json.load(f)
        _db_login = {key: qp(value)
                     for key, value in config["database_connection"].items()}
        del config
    _engine = db.create_engine(
        f"mysql+pymysql://{_db_login['user']}:{_db_login['password']}@{_db_login['host']}:{_db_login['port']}/{_db_login['database']}")
    _metadata = db.MetaData()
    del _db_login

    def __init__(self):
        self._connection = self._engine.connect()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._connection.close()

    def __del__(self):
        self._connection.close()

    def execute(self, query):
        try:
            result_proxy = self._connection.execute(query)
        except Exception as e:
            logging.error(e)
            return None
        return result_proxy

    def get_table(self, table_name) -> db.Table | None:
        try:
            table = db.Table(table_name, self._metadata,
                             autoload=True, autoload_with=self._engine)
        except Exception as e:
            logging.error(e)
            return None
        return table

    def get_table_names(self):
        return self._engine.table_names()

    def get_table_columns(self, table_name) -> list | None:
        table = self.get_table(table_name)
        if table is None:
            return None
        return table.columns.keys()


if __name__ == "__main__":
    main()
