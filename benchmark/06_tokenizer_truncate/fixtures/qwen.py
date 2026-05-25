# Generated via NIM live mode at 2026-05-24T23:16:35Z
# model: qwen/qwen3-coder-480b-a35b-instruct
def pre(i):
    tokens, N = i
    if not isinstance(tokens, list):
        return False
    if not isinstance(N, int) or N < 0:
        return False
    return True

def post(i, o):
    tokens, N = i
    if not isinstance(o, list):
        return False
    if len(o) > N:
        return False
    return True
