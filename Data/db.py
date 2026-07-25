import os
import sqlite3
import sqlite_vec

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(SCRIPT_DIR, "recipes_vector_scale.db")


class DbHelper:
    """
    Initialises a database connection 
    :param auto_load_vec : True or False will enable the sqlite vectorization plugin
    """

    def __init__(self, auto_load_vec: bool = False):
        self._db_path = DB_FILE
        self._conn: sqlite3.Connection | None = None
        self._auto_load_vec = auto_load_vec

    def __enter__(self):
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute("PRAGMA cache_size = -10000000")
        self._conn.execute("PRAGMA mmap_size = 10737418240")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA temp_store = MEMORY")
        if self._auto_load_vec:
            self._conn.enable_load_extension(True)
            sqlite_vec.load(self._conn)
        return self

    def __exit__(self, *args):
        if self._conn:
            self._conn.close()

    def _require_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Database connection has not been opened")
        return self._conn

    def query(self, sql: str, params: tuple | None = None) -> list[tuple]:
        if params:
            return self._conn.execute(sql, params).fetchall()
        return self._conn.execute(sql).fetchall()

    def stream(self, sql: str, params: tuple | None = None):
        connection = self._require_connection()
        cursor = connection.execute(sql, params or ())
        for row in cursor:
            yield row

    def execute(self, sql: str, params: tuple | None = None, *, commit: bool = True):
        connection = self._require_connection()
        connection.execute(sql, params or ())
        if commit:
            connection.commit()

    def executemany(self, sql: str, params: list[tuple], *, commit: bool = True):
        connection = self._require_connection()
        connection.executemany(sql, params)
        if commit:
            connection.commit()

    def commit(self):
        self._require_connection().commit()

    def rollback(self):
        self._require_connection().rollback()
