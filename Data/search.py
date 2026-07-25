import os
import numpy as np
import ollama
import faiss

from db import DbHelper
from typing import List, Tuple

POPCNT_LUT = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint8)

_binary_cache: tuple[np.ndarray, np.ndarray] | None = None  # (ids, packed_bits)
_faiss_index: faiss.IndexBinary | None = None
_faiss_ids: np.ndarray | None = None


def _load_binary_vectors():
    global _binary_cache
    if _binary_cache is not None:
        return _binary_cache
    with DbHelper() as db:
        rows = db.query("SELECT id, embedding_bit FROM vec_items_bq ORDER BY id")
        ids = np.array([r[0] for r in rows], dtype=np.int32)
        bits = np.frombuffer(b"".join(r[1] for r in rows), dtype=np.uint8).reshape(-1, 96)
    _binary_cache = (ids, bits)
    return _binary_cache


def binary_semantic_search(query: str, top_k: int = 5) -> List[Tuple[int, str, float]]:
    query_embedding = ollama.embed(model="nomic-embed-text", input=query)
    query_floats = np.array(query_embedding["embeddings"][0], dtype=np.float32)
    query_packed = np.packbits((query_floats > 0).astype(np.uint8))

    ids, bits = _load_binary_vectors()
    xor = np.bitwise_xor(bits, query_packed)
    hamming = POPCNT_LUT[xor].sum(axis=1)
    top_idx = np.argpartition(hamming, top_k)[:top_k]
    top_idx = top_idx[np.argsort(hamming[top_idx])]

    with DbHelper() as db:
        placeholders = ",".join("?" for _ in top_idx)
        id_list = [int(ids[i]) for i in top_idx]
        rows = db.query(
            f"SELECT id, recipe_text FROM items WHERE id IN ({placeholders})",
            tuple(id_list),
        )
        row_map = {r[0]: r[1] for r in rows}
        results = [
            (id_list[i], row_map.get(id_list[i], ""), float(hamming[top_idx[i]]))
            for i in range(len(top_idx))
        ]
    return results

def _ensure_faiss_index():
    global _faiss_index, _faiss_ids
    if _faiss_index is not None:
        return
    ids, bits = _load_binary_vectors()
    print(f"  Building FAISS binary IVF index ({len(ids)} vectors)...")
    d = 768
    nlist = 100
    quantizer = faiss.IndexBinaryFlat(d)
    index = faiss.IndexBinaryIVF(quantizer, d, nlist)
    index.train(bits)
    index.add(bits)
    index.nprobe = 5
    _faiss_index = index
    _faiss_ids = ids
    print("  FAISS index ready.")


def faiss_semantic_search(query: str, top_k: int = 5) -> List[Tuple[int, str, float]]:
    query_embedding = ollama.embed(model="nomic-embed-text", input=query)
    query_floats = np.array(query_embedding["embeddings"][0], dtype=np.float32)
    query_packed = np.packbits((query_floats > 0).astype(np.uint8)).reshape(1, -1)

    _ensure_faiss_index()
    distances, indices = _faiss_index.search(query_packed, top_k)

    recipe_ids = [int(_faiss_ids[i]) for i in indices[0]]
    with DbHelper() as db:
        placeholders = ",".join("?" for _ in recipe_ids)
        rows = db.query(
            f"SELECT id, recipe_text FROM items WHERE id IN ({placeholders})",
            tuple(recipe_ids),
        )
        row_map = {r[0]: r[1] for r in rows}
        results = [
            (rid, row_map.get(rid, ""), float(distances[0][j]))
            for j, rid in enumerate(recipe_ids)
        ]
    return results


def like_search(query: str, top_k: int = 5) -> List[Tuple[int, str, float]]:
    with DbHelper() as database:
        results = database.query("""
            SELECT id, recipe_text, 0.0 as distance
            FROM items
            WHERE recipe_text LIKE ?
            LIMIT ?
        """, (f"%{query}%", top_k))
        return results


def semantic_search(query:str, top_k: int = 5) -> List[Tuple[int,str,float]]:
   # convert search query into embedding 
    query_embedding = ollama.embed(model="nomic-embed-text", input=query)
  
   # convert into 32 bit floating point for vec plugin
    query_bytes = np.array(query_embedding["embeddings"][0],dtype=np.float32).tobytes()
 
    with DbHelper(auto_load_vec=True) as database:  
        results = database.query("""
            SELECT i.id, i.recipe_text,v.distance
            from vec_items v
            join items i on i.id = v.id
            where v.embedding match ?
                and k = ?
            order by v.distance
        """,(query_bytes, top_k))
        
        return results
  
if __name__ == "__main__":
    import sys
    query_text = " ".join(sys.argv[1:]) or "pecan dessert"
    print(f"Searching for {query_text}\n")
    
    for recipe_id, text, distance in semantic_search(query_text):
        title = text.split("\n")[0]
        print(f"[{recipe_id}] distance={distance:.4f} {title}")
    
