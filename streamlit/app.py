import streamlit as st
from st_keyup import st_keyup

import query
from views.recipe_list import get_results

# 1. Setup Page
st.set_page_config(
    page_title="Foodie Recipe Search",
    page_icon="🍳",
    layout="wide",
    initial_sidebar_state="collapsed"  # Force sidebar to hide initially
)

st.title("Recipe Search")

# 2. Build the Configuration Menu in the Sidebar
with st.sidebar:
    st.title("⚙️ Settings")
    st.subheader("Recipe Display Options")

    # Filter strategy configuration
    st.session_state.backend = st.selectbox(
        label="Search method",
        options=[
            "keyword (SQL keyword)",
            "semantic (sqlite-vec)",
            "semantic (sqlite-vec binary)",
            "semantic (sqlite-vec FAISS)",
            "semantic (pgvector)",
            "semantic (pgvector HNSW)",
        ]
    )

    st.divider()

if "pill_version" not in st.session_state:
    st.session_state.pill_version = 0
if "pill_counter" not in st.session_state:
    st.session_state.pill_counter = 0

def _set_query():
    key = f"pill_{st.session_state.pill_counter}"
    st.session_state.query = st.session_state[key]
    st.session_state.pill_version += 1
    st.session_state.pill_counter += 1

st.session_state.query = st_keyup(
    "What are you hungry for?",
    value=st.session_state.get("query", ""),
    key=f"search_{st.session_state.pill_version}",
    debounce=300,
    placeholder="eg. Something you would eat in Paris",
)

query = st.session_state.query

st.pills(
    key=f"pill_{st.session_state.pill_counter}",
    label="Quick Picks",
    label_visibility="collapsed",
    options=["Nut-free","Keto / Low-Carb", "What do samurai's eat", "Under 15 Mins", "Aqua Mans dinner","5 Ingredients or Fewer", "Something you would eat in Paris"],
    on_change=_set_query,
)

if query:
    get_results(query)

with st.container(horizontal_alignment="center"):
    st.caption(":orange[**Powered by Calories**]")
