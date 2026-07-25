import re
import streamlit as st


# Helper to map ingredient words to emojis
def get_ingredient_emoji(ingredient_str):
    ing = ingredient_str.lower()
    if "egg" in ing: return "🥚"
    if "milk" in ing: return "🥛"
    if "flour" in ing: return "🌾"
    if "sugar" in ing: return "🍬"
    if "butter" in ing: return "🧈"
    if "cinnamon" in ing or "spice" in ing or "clove" in ing or "nutmeg" in ing: return "🧂"
    if "raisin" in ing or "fruit" in ing: return "🍇"
    if "nut" in ing or "pecan" in ing: return "🥜"
    return "🥣"


def _split_ingredient(ingredient: str) -> tuple[str, str]:
    unit = (
        r'(?:c\.?|cup[s]?|tsp\.?|teaspoon[s]?|Tbsp\.?|tablespoon[s]?|'
        r'lb\.?|pound[s]?|oz\.?|ounce[s]?|pkg\.?|package[s]?|'
        r'jar[s]?|can[s]?|clove[s]?|dash[es]?|pinch[es]?|'
        r'drop[s]?|stick[s]?|medium|large|small|whole|'
        r'envelope[s]?|head[s]?|loaf|loaves|square[s]?|'
        r'container[s]?|piece[s]?|slice[s]?|bunch[es]?|'
        r'T\.?|t\.?)'
    )
    m = re.match(
        rf'^((?:(?:approx?\.?\s+)?[\d\s\/\–\-to]+(?:\([\d\s\/\.\w]+\))?\s*{unit}?))\s+(.+)$',
        ingredient.strip(),
        re.IGNORECASE
    )
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "", ingredient


@st.dialog("Recipe Details",width="medium")
def show_recipe_details():
    recipe = st.session_state.selected_recipe

    if recipe:
        st.subheader(f"🍰 {recipe[0]}")
        st.divider()

        tab_ing, tab_inst = st.tabs(["🛒 Ingredients", "👨‍🍳 Instructions"])

        with tab_ing:
            st.write("##### What you'll need:")

            rows = []
            for item in recipe[1]:
                qty, name = _split_ingredient(item)
                if not qty and rows:
                    prev_qty, prev_emoji, prev_name = rows[-1]
                    rows[-1] = (prev_qty, prev_emoji, prev_name + ", " + name)
                else:
                    rows.append((qty, get_ingredient_emoji(item), name))

            for qty, emoji, name in rows:
                cols = st.columns([1, 4])
                with cols[0]:
                    st.markdown(f"**{qty}**" if qty else "")
                with cols[1]:
                    st.markdown(f"{emoji} {name}")

        with tab_inst:
            st.info(recipe[2])

        st.divider()
        if st.button("Close", use_container_width=True):
            st.rerun()




