import json, os, argparse
import numpy as np
import psycopg
from pgvector.psycopg import register_vector
from pgvector import Vector
from db import DbHelper
from concurrent.futures import ThreadPoolExecutor, as_completed

EMBED_DIM = 768
DEFAULT_BATCH_SIZE = 1000


def get_connection_string() -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.normpath(
        os.path.join(script_dir, "..", "Foodie", "appsettings.Development.json")
    )

    with open(config_path) as f:
        config = json.load(f)

    password = config["ConnectionStrings"]["DB_PASSWORD"]
    return f"postgresql://postgres:{password}@localhost:5430/foodiedb"


def build_sqlite_vector_query(limit: int | None, min_id: int = 0) -> tuple[str, tuple]:
    conditions = ["v.id > ?"]
    params: list[int] = [min_id]
    limit_clause = ""
    if limit is not None:
        limit_clause = "LIMIT ?"
        params.append(limit)
    return (
        f"""
        SELECT v.id, i.recipe_text, v.embedding
        FROM vec_items v
        JOIN items i ON i.id = v.id
        WHERE {' AND '.join(conditions)}
        ORDER BY v.id
        {limit_clause}
        """,
        tuple(params),
    )


def build_sqlite_vector_query_range(min_id: int, max_id: int, limit: int | None) -> tuple[str, tuple]:
    conditions = ["v.id >= ?", "v.id < ?"]
    params: list[int] = [min_id, max_id]
    limit_clause = ""
    if limit is not None:
        limit_clause = "LIMIT ?"
        params.append(limit)
    return (
        f"""
        SELECT v.id, i.recipe_text, v.embedding
        FROM vec_items v
        JOIN items i ON i.id = v.id
        WHERE {' AND '.join(conditions)}
        ORDER BY v.id
        {limit_clause}
        """,
        tuple(params),
    )


def count_sqlite_vectors(database: DbHelper, limit: int | None = None, min_id: int = 0) -> int:
    if limit is not None:
        row = database.query(
            "SELECT COUNT(*) FROM (SELECT 1 FROM vec_items WHERE id > ? ORDER BY id LIMIT ?)",
            (min_id, limit),
        )[0]
        return int(row[0])

    row = database.query("SELECT COUNT(*) FROM vec_items WHERE id > ?", (min_id,))[0]
    return int(row[0])


def get_id_bounds(database: DbHelper) -> tuple[int, int]:
    row = database.query("SELECT MIN(id), MAX(id) FROM vec_items")[0]
    return int(row[0]), int(row[1])


def deserialize_embedding(embedding_blob: bytes) -> Vector:
    embedding = np.frombuffer(embedding_blob, dtype=np.float32)
    if embedding.size != EMBED_DIM:
        raise ValueError(
            f"Expected embedding dimension {EMBED_DIM}, received {embedding.size}"
        )
    return Vector(embedding.tolist())


def sqlite_batches(
    database: DbHelper,
    *,
    limit: int | None,
    batch_size: int,
    min_id: int = 0,
):
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")

    query, params = build_sqlite_vector_query(limit, min_id=min_id)
    pending_rows: list[tuple[int, str, bytes]] = []

    for recipe_id, recipe_text, embedding_blob in database.stream(query, params):
        pending_rows.append((recipe_id, recipe_text, embedding_blob))
        if len(pending_rows) >= batch_size:
            yield pending_rows
            pending_rows = []

    if pending_rows:
        yield pending_rows


def ensure_table(conn: psycopg.Connection):
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id          SERIAL PRIMARY KEY,
                original_id INTEGER UNIQUE NOT NULL,
                recipe_text TEXT NOT NULL,
                embedding   VECTOR(768)
            )
        """)
        conn.commit()


def truncate_items_table(conn: psycopg.Connection):
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE items RESTART IDENTITY")
    conn.commit()


def get_max_original_id(conn: psycopg.Connection) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(original_id), 0) FROM items")
        return cur.fetchone()[0]


def insert_batch(conn: psycopg.Connection, batch: list[tuple[int, str, bytes]]):
    rows_to_insert = [
        (recipe_id, recipe_text.replace("\x00", ""), deserialize_embedding(embedding_blob))
        for recipe_id, recipe_text, embedding_blob in batch
    ]

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO items (original_id, recipe_text, embedding)
            VALUES (%s, %s, %s)
            ON CONFLICT (original_id) DO NOTHING
            """,
            rows_to_insert,
        )
    conn.commit()


def migrate_worker(
    worker_id: int,
    id_min: int,
    id_max: int,
    batch_size: int,
    connection_string: str,
    limit: int | None,
) -> int:
    count = 0
    with DbHelper(auto_load_vec=True) as database:
        conn = psycopg.connect(connection_string)
        register_vector(conn)
        try:
            query, params = build_sqlite_vector_query_range(id_min, id_max, limit)
            pending: list[tuple[int, str, bytes]] = []
            for recipe_id, recipe_text, embedding_blob in database.stream(query, params):
                pending.append((recipe_id, recipe_text, embedding_blob))
                if len(pending) >= batch_size:
                    insert_batch(conn, pending)
                    count += len(pending)
                    pending = []
            if pending:
                insert_batch(conn, pending)
                count += len(pending)
        finally:
            conn.close()
    print(f"  Worker {worker_id} finished: {count} rows")
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of recipes to migrate (for testing)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Number of rows to insert into PostgreSQL per worker per batch",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Truncate the table and re-migrate all rows from scratch",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)",
    )
    args = parser.parse_args()

    if args.batch_size <= 0:
        raise ValueError("--batch-size must be greater than 0")

    connection_string = get_connection_string()

    print("Reading vectors from sqlite-vec...")
    with DbHelper(auto_load_vec=True) as database:
        min_id, max_id = get_id_bounds(database)
        total = count_sqlite_vectors(database, limit=args.limit)
        print(f"  Found {total} vectorized recipes (id range: {min_id} - {max_id})")
        if total == 0:
            print("  Nothing to migrate. Run vectorize.py first to populate vec_items.")
            return

        print("Connecting to PostgreSQL...")
        conn = psycopg.connect(connection_string)

        try:
            ensure_table(conn)
            register_vector(conn)

            global_min = 0
            if args.force:
                truncate_items_table(conn)
                print("  Truncated items table, migrating all rows")
            else:
                global_min = get_max_original_id(conn)
                print(f"  Resuming from original_id > {global_min}")

            if global_min >= max_id:
                print("  All rows already migrated, nothing to do.")
                return

            total = count_sqlite_vectors(database, limit=args.limit, min_id=global_min)
            print(f"  {total} rows remaining to migrate")

            if global_min < min_id:
                global_min = min_id

            id_range = max_id - global_min
            chunk_size = id_range // args.workers
            if chunk_size == 0:
                args.workers = 1
                chunk_size = id_range

            limits_per_worker = None
            if args.limit is not None:
                limits_per_worker = [args.limit // args.workers] * args.workers
                for i in range(args.limit % args.workers):
                    limits_per_worker[i] += 1

            chunks = []
            for i in range(args.workers):
                start = global_min + i * chunk_size
                end = max_id if i == args.workers - 1 else global_min + (i + 1) * chunk_size
                if start >= end:
                    break
                lmt = limits_per_worker[i] if limits_per_worker else None
                chunks.append((i + 1, start, end, lmt))

            print(f"  Launching {len(chunks)} workers...")

        finally:
            conn.close()

    total_inserted = 0
    with ThreadPoolExecutor(max_workers=len(chunks)) as executor:
        futures = [
            executor.submit(
                migrate_worker, wid, start, end, args.batch_size, connection_string, lmt
            )
            for wid, start, end, lmt in chunks
        ]
        for f in as_completed(futures):
            total_inserted += f.result()

    print(f"  Done! {total_inserted} rows migrated.")


if __name__ == "__main__":
    main()
