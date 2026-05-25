def impl(args):
    user, allowed, active = args
    return user in allowed and active
