from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api_service.app.core.config import settings

engine = create_engine(settings.sync_database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
