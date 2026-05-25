from hypothesis import strategies as st

input_strategy = st.lists(st.integers(min_value=-10, max_value=10), max_size=10)
output_strategy = st.lists(st.integers(min_value=-10, max_value=10), max_size=10)
