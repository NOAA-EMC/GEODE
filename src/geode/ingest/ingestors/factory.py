RegisteredIngestors = {}


def register(id: str):
    """Decorator to register an ingestor class with a given ID."""

    def decorator(ingestor_class: type):
        RegisteredIngestors[id] = ingestor_class
        return ingestor_class

    return decorator


def make(id: str) -> type | None:
    """Returns the appropriate ingestor class for a given ID."""

    if id in RegisteredIngestors:
        return RegisteredIngestors[id]
    else:
        print(f"[-] No ingestor found for ID: {id}")
        return None


def directory() -> list[str]:
    """Returns a list of all registered ingestor IDs."""

    return list(RegisteredIngestors.keys())
