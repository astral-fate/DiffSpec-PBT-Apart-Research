from hypothesis import strategies as st

# Path-like strings drawn from a small alphabet including the danger chars.
chars = st.sampled_from(list("abcd/.") + ["\x00"])
input_strategy = st.lists(chars, max_size=12).map("".join)
output_strategy = st.lists(chars, max_size=12).map("".join)
