from hypothesis import strategies as st

name = st.sampled_from(["alice", "bob", "carol", "dave"])
input_strategy = st.tuples(
    name,
    st.lists(name, max_size=4, unique=True),
    st.booleans(),
)
output_strategy = st.booleans()
