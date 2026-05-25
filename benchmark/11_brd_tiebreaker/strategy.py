from hypothesis import strategies as st

record = st.tuples(
    st.integers(min_value=0, max_value=1000),    # total_score
    st.integers(min_value=0, max_value=1000),    # gameplay_points
    st.integers(min_value=0, max_value=6),       # unique_platforms (Instagram+TikTok+X+FB+YT+Twitch)
    st.integers(min_value=1_700_000_000, max_value=1_800_000_000),  # submission ts
)
input_strategy = st.lists(record, min_size=2, max_size=4)
output_strategy = st.lists(record, min_size=2, max_size=4)
