# Generated via NIM live mode at 2026-05-24T23:12:26Z
# model: qwen/qwen3-coder-480b-a35b-instruct
def pre(i):
    if not isinstance(i, tuple) or len(i) != 2:
        return False
    list1, list2 = i
    return (isinstance(list1, list) and isinstance(list2, list) and 
            all(isinstance(x, int) for x in list1) and 
            all(isinstance(x, int) for x in list2) and
            list1 == sorted(list1) and list2 == sorted(list2))

def post(i, o):
    if not isinstance(o, list) or not all(isinstance(x, int) for x in o):
        return False
    list1, list2 = i
    if not pre(i):
        return False
    expected = sorted(list1 + list2)
    return o == expected
