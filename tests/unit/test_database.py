from sqlalchemy import text
from tourism_pulse_api.db.session import engine


def test_database_connection() -> None:
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        assert result.scalar_one() == 1