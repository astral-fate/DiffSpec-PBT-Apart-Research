from hypothesis import strategies as st

sorted_list = st.lists(st.integers(min_value=-20, max_value=20), max_size=6).map(sorted)
input_strategy = st.tuples(sorted_list, sorted_list)
output_strategy = st.lists(st.integers(min_value=-20, max_value=20), max_size=12)
