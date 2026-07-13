"""
DEPRECATED for greenfield deploys — prefer Alembic (`alembic upgrade head`).

Legacy utility to bootstrap a Neon (or any PostgreSQL) database using the
existing SQLAlchemy models. It can optionally copy data from a MySQL source
database so staging environments can be hydrated quickly.

Canonical scripts
-----------------
* MySQL CI / local seed: ``scripts/ci_bootstrap_db.py``
* MySQL migrate-only: ``scripts/bootstrap_local_db.py``
* Postgres: set ``DATABASE_URL`` + ``alembic upgrade head`` (this script remains for
  one-off ``create_all`` + optional data copy only)

Usage examples:
    # Create schema only
    python scripts/bootstrap_neon.py --target-url $DATABASE_URL

    # Create schema and copy data from MySQL
    python scripts/bootstrap_neon.py ^
        --source-url mysql+pymysql://root:pass@localhost:3306/fastapi_users ^
        --target-url postgresql://...neon.tech/neondb?sslmode=require ^
        --copy-data
"""

from __future__ import annotations

import argparse
import os
from typing import Iterable, List, Sequence, Type

from sqlalchemy import create_engine, insert, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from models.user_model import (
    ApiKey,
    AuditLog,
    LoginAttempt,
    Organization,
    PasswordHistory,
    RefreshToken,
    User,
    UserGroup,
    UserGroupMembership,
    UserPermission,
    UserSession,
)
from utils.database import Base

# Order matters for data copy to satisfy FK relationships.
TABLE_IMPORT_ORDER: Sequence[Type[Base]] = [
    Organization,
    User,
    RefreshToken,
    UserSession,
    AuditLog,
    PasswordHistory,
    LoginAttempt,
    UserPermission,
    UserGroup,
    UserGroupMembership,
    ApiKey,
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap Neon/PostgreSQL with the SQLAlchemy schema."
    )
    parser.add_argument(
        "--target-url",
        default=os.getenv("TARGET_DATABASE_URL") or os.getenv("DATABASE_URL"),
        help="SQLAlchemy URL for the Neon/PostgreSQL database.",
    )
    parser.add_argument(
        "--source-url",
        default=os.getenv("SOURCE_DATABASE_URL"),
        help="Optional SQLAlchemy URL for the legacy MySQL database.",
    )
    parser.add_argument(
        "--copy-data",
        action="store_true",
        help="Copy data from the source database after creating tables.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Rows per batch when copying data.",
    )
    parser.add_argument(
        "--skip-delete",
        action="store_true",
        help="Do not delete existing rows in the target tables before copying.",
    )
    return parser.parse_args()


def create_schema(engine: Engine) -> None:
    Base.metadata.create_all(bind=engine)


def chunked(iterable: Iterable, size: int) -> Iterable[List]:
    chunk: List = []
    for item in iterable:
        chunk.append(item)
        if len(chunk) >= size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def model_to_dict(instance: Base) -> dict:
    return {
        column.name: getattr(instance, column.name)
        for column in instance.__table__.columns  # type: ignore[attr-defined]
    }


def reset_identity(engine: Engine, model: Type[Base]) -> None:
    if engine.dialect.name != "postgresql":
        return
    seq_name = f"{model.__tablename__}_id_seq"  # type: ignore[attr-defined]
    stmt = text(
        "SELECT setval(:seq, COALESCE((SELECT MAX(id) FROM "
        f"{model.__tablename__}), 0))"  # type: ignore[attr-defined]
    )
    with engine.begin() as connection:
        connection.execute(stmt, {"seq": seq_name})


def copy_table_data(
    model: Type[Base],
    source_session: Session,
    target_session: Session,
    batch_size: int,
    clear_table: bool,
) -> int:
    if clear_table:
        target_session.execute(model.__table__.delete())  # type: ignore[attr-defined]
        target_session.commit()

    total_rows = 0
    query = source_session.query(model)
    for rows in chunked(query.yield_per(batch_size), batch_size):
        payload = [model_to_dict(row) for row in rows]
        target_session.execute(insert(model), payload)
        target_session.commit()
        total_rows += len(rows)
    return total_rows


def copy_data(
    source_engine: Engine,
    target_engine: Engine,
    batch_size: int,
    skip_delete: bool,
) -> None:
    SourceSession = sessionmaker(bind=source_engine)
    TargetSession = sessionmaker(bind=target_engine)

    with SourceSession() as source_session, TargetSession() as target_session:
        for model in TABLE_IMPORT_ORDER:
            total = copy_table_data(
                model,
                source_session,
                target_session,
                batch_size=batch_size,
                clear_table=not skip_delete,
            )
            reset_identity(target_engine, model)
            print(f"[OK] {model.__tablename__}: {total} rows copied")  # type: ignore


def main() -> None:
    args = parse_args()
    if not args.target_url:
        raise SystemExit(
            "Target database URL is required. Set --target-url or DATABASE_URL."
        )

    try:
        target_engine = create_engine(args.target_url, pool_pre_ping=True, future=True)
        print("Creating schema on target database...")
        create_schema(target_engine)
        print("[OK] Schema ensured on target database.")

        if args.copy_data:
            if not args.source_url:
                raise SystemExit(
                    "Source database URL is required when --copy-data is set."
                )
            source_engine = create_engine(args.source_url, pool_pre_ping=True, future=True)
            print("Copying data from source to target...")
            copy_data(
                source_engine,
                target_engine,
                batch_size=args.batch_size,
                skip_delete=args.skip_delete,
            )
            print("[OK] Data copy complete.")
    except SQLAlchemyError as exc:
        raise SystemExit(f"Database operation failed: {exc}") from exc


if __name__ == "__main__":
    main()

