from hypothesis import strategies as st

input_strategy = st.tuples(
    st.lists(st.integers(min_value=-20, max_value=20), max_size=8).map(sorted),
    st.integers(min_value=-25, max_value=25),
)
output_strategy = st.integers(min_value=-2, max_value=10)
