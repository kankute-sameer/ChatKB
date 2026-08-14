from ulid import ULID


def new_id(prefix: str) -> str:
    """Return a prefixed ULID, e.g. conv_01ARZ3NDEKTSV4RRFFQ69G5FAV."""
    return f"{prefix}_{ULID()}"
