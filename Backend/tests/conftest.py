import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app import main
import tempfile
import os
import atexit

# Use a temporary file for testing instead of in-memory
# to avoid connection pool issues with in-memory SQLite
_test_db_fd, _test_db_path = tempfile.mkstemp(suffix=".db")
os.close(_test_db_fd)
TEST_DATABASE_URL = f"sqlite:///{_test_db_path}"
atexit.register(lambda: os.path.exists(_test_db_path) and os.remove(_test_db_path))


@pytest.fixture
def db_session():
    test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(test_engine)
    TestingSessionLocal = sessionmaker(bind=test_engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(test_engine)


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    # Override on the main app
    main.app.dependency_overrides[get_db] = override_get_db

    # Use the main app with the override
    client = TestClient(main.app)
    yield client
    main.app.dependency_overrides.clear()
