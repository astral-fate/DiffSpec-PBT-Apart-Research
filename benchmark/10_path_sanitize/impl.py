def impl(p):
    # Strip null bytes first, then drop ..-components and leading slashes.
    p = p.replace("\x00", "")
    parts = [part for part in p.split("/") if part not in ("", "..")]
    return "/".join(parts)
