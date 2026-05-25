def impl(args):
    count, limit, rolled = args
    if rolled:
        return True
    return count < limit
