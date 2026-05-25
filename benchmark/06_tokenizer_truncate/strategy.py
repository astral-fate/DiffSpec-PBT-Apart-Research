from hypothesis import strategies as st

input_strategy = st.tuples(
    st.lists(st.integers(min_value=0, max_value=99), max_size=10),
    st.integers(min_value=0, max_value=12),
)
output_strategy = st.lists(st.integers(min_value=0, max_value=99), max_size=10)
