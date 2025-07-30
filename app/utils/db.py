from contextlib import contextmanager
import logging
from models import db

@contextmanager
def transactional(message="DB transaction failed"):
    """Context manager to wrap a database transaction."""
    try:
        yield
        db.session.commit()
    except Exception as e:
        logging.error(f"{message}: %s", e, exc_info=True)
        db.session.rollback()
        raise
