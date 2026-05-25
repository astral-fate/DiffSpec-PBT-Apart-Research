from hypothesis import strategies as st

short_text = st.text(alphabet="abcdefghij", min_size=1, max_size=6)

input_strategy = st.tuples(
    short_text, short_text,
    st.lists(short_text, max_size=4),
)
output_strategy = st.lists(short_text, max_size=8)
