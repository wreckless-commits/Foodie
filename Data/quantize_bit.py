import argparse, time
import numpy as np
from db import DbHelper

EMBED_DIM = 768
BATCH_SIZE = 1000


def quantize_to_bit(embedding_blob: bytes) -> bytes:
    floats = np.frombuffer(embedding_blob, dtype=np.float32)
    bits = (floats > 0).astype(np.uint8)
    packed = np.packbits(bits).tobytes()
    return packed


def ensure_bit_table(database):
    database.execute("""
        CREATE TABLE IF NOT EXISTS vec_items_bq (
            id            INTEGER PRIMARY KEY,
            embedding_bit BLOB    NOT NULL
        )
    """)


def quantize_all(limit: int | None = None):
    with DbHelper(auto_load_vec=True) as database:
        ensure_bit_table(database)

        total = database.query("SELECT COUNT(*) FROM vec_items")[0][0]
        print(f"Total vectors: {total}")

        query = "SELECT v.id, v.embedding FROM vec_items v"
        params: tuple = ()
        if limit:
            query = "SELECT v.id, v.embedding FROM vec_items v ORDER BY v.id LIMIT ?"
            params = (limit,)

        pending: list[tuple[int, bytes]] = []
        processed = 0
        t0 = time.time()

        for row_id, emb_blob in database.stream(query, params):
            pending.append((row_id, quantize_to_bit(emb_blob)))
            if len(pending) >= BATCH_SIZE:
                database.executemany(
                    "INSERT OR REPLACE INTO vec_items_bq (id, embedding_bit) VALUES (?, ?)",
                    [(rid, bit) for rid, bit in pending],
                )
                processed += len(pending)
                elapsed = time.time() - t0
                rate = processed / elapsed if elapsed > 0 else 0
                print(f"  Quantized {processed}/{total}  ({rate:.0f} rows/s)")
                pending.clear()

        if pending:
            database.executemany(
                "INSERT OR REPLACE INTO vec_items_bq (id, embedding_bit) VALUES (?, ?)",
                [(rid, bit) for rid, bit in pending],
            )
            processed += len(pending)

        elapsed = time.time() - t0
        print(f"  Done! {processed} vectors quantized in {elapsed:.1f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    quantize_all(limit=args.limit)
