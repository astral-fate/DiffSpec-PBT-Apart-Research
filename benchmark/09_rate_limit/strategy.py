from hypothesis import strategies as st

input_strategy = st.tuples(
    st.integers(min_value=0, max_value=20),  # count
    st.integers(min_value=1, max_value=10),  # limit
    st.booleans(),                            # rolled
)
output_strategy = st.booleans()
