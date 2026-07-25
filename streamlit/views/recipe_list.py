import streamlit as st
import time
from views.recipe_details import show_recipe_details
from query import find_food


def _open_dialog(recipe):
    """
    Opens the recipe details in a dialog box
    :param recipe:
    """
    st.session_state.selected_recipe = recipe
    show_recipe_details()


def get_results(query: str):
    """
    Makes calls to the selected backend to obtain recipes
    :param query:
    :return:
    """

    t0 = time.perf_counter()
    results = find_food(query)
    elapsed = time.perf_counter() - t0

    # Extract whole seconds and convert the remaining fractional part to milliseconds
    seconds = int(elapsed)
    milliseconds = int((elapsed - seconds) * 1000)

    st.subheader(f":green[Found {len(results)} results in {seconds}s {milliseconds}ms]")

    _render_results(results)


def _render_results(results):
    """
    Processes result data and renders layout
    :param results:
    :return:
    """
    number_of_columns = 3
    for recipe in range(0, len(results), number_of_columns):
        row_recipes = results[recipe:recipe + number_of_columns]
        cols = st.columns(number_of_columns)  # Generate fresh columns for this row

        for idx, recipe in enumerate(row_recipes):
            with cols[idx]:
                with st.container(border=True, height=388, autoscroll=False):
                    layout_cols = st.columns(2)
                    with layout_cols[0]:
                        img_url = "https://images.unsplash.com/photo-1495521821757-a1efb6729352?q=80&w=400"
                        st.image(img_url, width=219)

                    with layout_cols[1]:
                        # header
                        st.subheader(recipe[0])
                        st.caption("Key Ingredients")

                        # Get max 4 ingredients
                        ingredients = list(recipe[1][:4])

                        # Get total ingreients
                        total_ingredients = len(recipe[1])

                        if (total_ingredients > 4):
                            remaining = total_ingredients - 4
                            ingredients.append(f"+{remaining} more")

                        st.pills(
                            label="Ingredients List",
                            options=ingredients,
                            disabled=True,
                            label_visibility="collapsed"
                        )

                    st.button(label="View Recipe", key=f"btn_{recipe[3]}", use_container_width=True,
                              on_click=_open_dialog, args=(recipe,))
