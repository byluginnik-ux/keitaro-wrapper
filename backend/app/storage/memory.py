from app.storage.ports import Storage


def create_memory_storage() -> Storage:
    """Keep everything in process memory: for tests and for running without a database."""
    raise NotImplementedError
