"""Section 2.6: what `create-admin` tells the operator for each kind of database failure."""

import pytest
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.cli import database_problem


class _DriverError(Exception):
    def __init__(self, sqlstate: object = None) -> None:
        super().__init__("driver error")
        self.sqlstate = sqlstate


def _wrapped(orig: BaseException) -> ProgrammingError:
    return ProgrammingError("SELECT 1", {}, orig)


def _with_cause(sqlstate: str) -> Exception:
    adapter = Exception("adapter error")  # no sqlstate of its own, like SQLAlchemy's adapter
    adapter.__cause__ = _DriverError(sqlstate)
    return adapter


@pytest.mark.parametrize(
    "error",
    [_wrapped(_DriverError("42P01")), _wrapped(_with_cause("42P01"))],
)
def test_s2_6_13_missing_table_says_to_run_migrations(error: ProgrammingError) -> None:
    assert "run migrations first" in database_problem(error)


@pytest.mark.parametrize(
    "error",
    [
        _wrapped(_DriverError("42501")),  # insufficient privilege
        _wrapped(_with_cause("42601")),  # syntax error
        _wrapped(_DriverError()),  # no SQLSTATE at all
        _wrapped(_DriverError(42)),  # not a string
        OperationalError("SELECT 1", {}, _DriverError("08006")),
        ConnectionRefusedError("refused"),
    ],
)
def test_s2_6_13_other_database_errors_get_the_generic_message(
    error: OSError | ProgrammingError,
) -> None:
    message = database_problem(error)
    assert message.startswith("error: cannot use the database (")
    assert "migrations" not in message
