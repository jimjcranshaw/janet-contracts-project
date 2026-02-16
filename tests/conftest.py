import pytest
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unittest.mock import MagicMock
# Mock pgvector for local testing if not installed
try:
    import pgvector
except ImportError:
    sys.modules["pgvector"] = MagicMock()
    sys.modules["pgvector.sqlalchemy"] = MagicMock()
    # Mock vector as JSON for SQLite (list of floats)
    sys.modules["pgvector.sqlalchemy"].Vector = lambda x: sqlalchemy.types.JSON()

# Mock Postgres JSONB for SQLite
from sqlalchemy.dialects import postgresql
import sqlalchemy.types as types
sys.modules["sqlalchemy.dialects.postgresql"] = MagicMock()
sys.modules["sqlalchemy.dialects.postgresql"].JSONB = types.JSON
sys.modules["sqlalchemy.dialects.postgresql"].UUID = types.UUID # Mock UUID too if needed

from sqlalchemy import create_engine
import sqlalchemy
# Patch ARRAY for SQLite
from sqlalchemy.dialects import postgresql
sqlalchemy.ARRAY = sqlalchemy.JSON

from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import Notice, Buyer

# Use SQLite for simple unit tests, or a test Postgres container for full integration that needs vector types.
# For now, using sqlite in-memory for basic logic, noting that vector types might need mocking.
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db():
    # Create tables
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    # Drop tables
    Base.metadata.drop_all(bind=engine)
