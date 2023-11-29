from _db import Database
from settings import CONFIG

database = Database()


def main():
    tables = CONFIG.INSERT.keys()
    for table in tables:
        database.delete_from(table=table)


if __name__ == "__main__":
    main()
