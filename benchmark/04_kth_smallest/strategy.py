from hypothesis import strategies as st

input_strategy = st.tuples(
    st.lists(st.integers(min_value=-30, max_value=30), max_size=8),
    st.integers(min_value=0, max_value=10),
)
output_strategy = st.one_of(st.none(), st.integers(min_value=-50, max_value=50))
