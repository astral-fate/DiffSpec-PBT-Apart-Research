def impl(records):
    # Sort by: total desc, gameplay desc, platforms desc, timestamp asc.
    return sorted(
        records,
        key=lambda r: (-r[0], -r[1], -r[2], r[3]),
    )
