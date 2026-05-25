def impl(i):
    seen = []
    for x in i:
        if x not in seen:
            seen.append(x)
    return seen
