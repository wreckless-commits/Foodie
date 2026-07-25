import requests
import streamlit as st

from Data.search import like_search, binary_semantic_search, faiss_semantic_search, semantic_search


def _parse_recipe_text(recipe_text: str) -> tuple[str, str,str]:
    lines = recipe_text.split("\n")
    title = lines[0]
    ingredients = []
    directions = ""
    in_ingredients = False
    for i, line in enumerate(lines):
        if line.startswith("Ingredients:"):
            in_ingredients = True
            continue
        if line.startswith("Directions:"):
            directions = "\n".join(l for l in lines[i+1:] if l.strip())
            break
        if in_ingredients and line.strip():
            ingredients.append(line.lstrip("- "))
    return title, ", ".join(ingredients), directions


def _to_result(recipe_id: int, recipe_text: str) -> tuple[str, list[str],str, int]:
    title, ingredients, directions = _parse_recipe_text(recipe_text)
    return title, ingredients.split(","),directions, recipe_id


def find_food(query: str):
    result = []

    if query:

        backend = st.session_state.backend

        if backend == "semantic (pgvector)" or backend == "semantic (pgvector HNSW)":
            use_index: str = ""

            if not backend == "semantic (pgvector HNSW)":
                use_index="&exact=true"

            response = requests.get(f"https://localhost:7184/api/search?query={query}&topK=9{use_index}")
            for item in response.json():
                result.append(_to_result(item["id"], item["recipeText"]))

        elif backend == "keyword (SQL keyword)":
            for recipe_id, recipe_text, _ in like_search(query, 9):
                result.append(_to_result(recipe_id, recipe_text))

        elif backend == "semantic (sqlite-vec binary)":
            for recipe_id, recipe_text, _ in binary_semantic_search(query, 9):
                result.append(_to_result(recipe_id, recipe_text))

        elif backend == "semantic (sqlite-vec FAISS)":
            for recipe_id, recipe_text, _ in faiss_semantic_search(query, 9):
                result.append(_to_result(recipe_id, recipe_text))

        else:
            for recipe_id, recipe_text, _ in semantic_search(query, 9):
                result.append(_to_result(recipe_id, recipe_text))

    return result