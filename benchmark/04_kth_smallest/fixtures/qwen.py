# Generated via NIM live mode at 2026-05-24T23:10:43Z
# model: qwen/qwen3-coder-480b-a35b-instruct
def pre(i):
    if not isinstance(i, tuple) or len(i) != 2:
        return False
    if not isinstance(i[0], list) or not isinstance(i[1], int):
        return False
    return True

def post(i, o):
    if not pre(i):
        return False
    arr, k = i
    if not isinstance(arr, list) or not all(isinstance(x, int) for x in arr):
        return False
    if k <= 0 or k > len(arr):
        return o is None
    if not arr or k <= 0 or k > len(arr):
        return o is None
    if not arr:
        return False not in [x <= 0 for x in []]
    sorted_arr = sorted(arr)
    if k > len(sorted_arr):
        return o is None
    if k <= 0:
        return o is None
    return o == sorted_arr[k-1] if 1 <= k <= len(sorted_arr) else o is None
