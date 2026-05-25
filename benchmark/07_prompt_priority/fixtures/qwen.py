# Generated via NIM live mode at 2026-05-24T23:14:59Z
# model: qwen/qwen3-coder-480b-a35b-instruct
def pre(i):
    if not isinstance(i, tuple) or len(i) != 3:
        return False
    system_prompt, user_prompt, retrieved_sources = i
    if not isinstance(system_prompt, str):
        return False
    if not isinstance(user_prompt, str):
        return False
    if not isinstance(retrieved_sources, list):
        return False
    if not all(isinstance(source, str) for source in retrieved_sources):
        return False
    return True

def post(i, o):
    if not pre(i):
        return False
    system_prompt, user_prompt, retrieved_sources = i
    expected_output = [system_prompt, user_prompt] + retrieved_sources
    return o == expected_output or o == [str(item) for item in expected_output]
