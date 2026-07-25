import os
import sqlite3
import sqlite_vec
from datasets import load_dataset

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(SCRIPT_DIR, "recipes_vector_scale.db")

def create_tables(db: sqlite3.Connection):
    db.execute("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, recipe_text TEXT);")
    db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS vec_items USING vec0(id INTEGER PRIMARY KEY, embedding float[768]);")
    db.commit()

def ingest_all(db: sqlite3.Connection, batch_size: int = 500):
    dataset = load_dataset("corbt/all-recipes", split="train")
    total = len(dataset)
    print(f"Dataset has {total} records.")
    rows = []
    for i, row in enumerate(dataset):
        text = row.get("input", "")
        if not text.strip():
            continue
        rows.append((i, text))
        if len(rows) == batch_size:
            db.executemany("INSERT INTO items (id, recipe_text) VALUES (?, ?);", rows)
            db.commit()
            print(f"  Inserted {rows[-1][0] + 1}/{total}...")
            rows.clear()
    if rows:
        db.executemany("INSERT INTO items (id, recipe_text) VALUES (?, ?);", rows)
        db.commit()
    print(f"Ingestion complete: {total} records in 'items' table.")

def main():
    print("Loading dataset...")
    db = sqlite3.connect(DB_FILE)
    db.enable_load_extension(True)
    sqlite_vec.load(db)

    create_tables(db)
    print("Tables created. Starting full-dataset ingestion...")
    ingest_all(db)
    db.close()
    print(f"All data stored in '{DB_FILE}'.")

if __name__ == "__main__":
    main()
