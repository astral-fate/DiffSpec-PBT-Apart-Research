def impl(args):
    arr, k = args
    if k < 1 or k > len(arr):
        return None
    return sorted(arr)[k - 1]
