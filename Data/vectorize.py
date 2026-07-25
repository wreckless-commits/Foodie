import ollama
import numpy as np
import argparse
from typing import List,Tuple


from db import DbHelper

BATCH_SIZE = 80

parser = argparse.ArgumentParser()
parser.add_argument("--limit",type=int,default=None,help="Limit the number of recipes to process")
args = parser.parse_args()

def _vectorize_and_insert(
        database:DbHelper,
        batch_identifiers:List[int],
        batch_recipes:List[str]
) -> None:
    response = ollama.embed(model="nomic-embed-text",input=batch_recipes)
    
    for recipe_id,embedding in zip(batch_identifiers,response["embeddings"]):
        # convert the 768 floats from model response and convert into a 32 bit floating point
        # for the sqlvec plugin to work
        embedding_bytes = np.array(embedding,dtype=np.float32).tobytes()
       
       # save to db 
        database.execute(
            "insert into vec_items (id,embedding) values (?,?)",
            (recipe_id,embedding_bytes)
        )
        
def vectorize_all_recipes() -> None:
    pending_ids = []
    pending_recipes = []
    total_processed = 0
    
    with DbHelper(auto_load_vec=True) as database:
        # Load IDs already vectorized (empty on first run)
        existing = set(row[0] for row in database.query("SELECT id FROM vec_items"))
        skipped = 0
       
        if args.limit:
            query = f"select id, recipe_text from items order by id limit {args.limit};"
        else:
            query = "select id, recipe_text from items order by id"
           
        for record_id,recipe_text in database.stream(query):
            # skip if we have vectorized this already
            if record_id in existing:
                skipped += 1
                continue
                
            pending_ids.append(record_id)
            pending_recipes.append(recipe_text)
           
            # Batch size met, vectorize recipes 
            if len(pending_recipes) >= BATCH_SIZE:
                _vectorize_and_insert(database, pending_ids,pending_recipes)
                total_processed += len(pending_ids)
                print(f"Processed and vectorized {total_processed} recipes...")
                pending_ids.clear()
                pending_recipes.clear()
                
        # Catch the remaining recipes 
        if pending_ids:
            _vectorize_and_insert(database, pending_ids,pending_recipes)
            total_processed += len(pending_ids)
       
        print(f"Skipped {skipped} already vectorized recipes.") 
        print(f"Processed and vectorized {total_processed} in total")
        
if __name__ == "__main__":
    vectorize_all_recipes()