from __future__ import annotations

import threading
from collections.abc import Iterator

from fastapi import Request
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from bailoteca_api.config import Settings


class DatabaseUnavailable(Exception):
    """La base de datos no está configurada o no responde."""


_pool: ConnectionPool | None = None
_pool_lock = threading.Lock()


def _get_pool(settings: Settings) -> ConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                pool = ConnectionPool(
                    conninfo=settings.database_url_readonly,
                    min_size=0,
                    max_size=settings.db_pool_max_size,
                    timeout=5,
                    max_idle=60,
                    kwargs={
                        "row_factory": dict_row,
                        "prepare_threshold": None,
                        # Defensa en profundidad: aunque el rol de solo
                        # lectura perdiera su único barrier (GRANT), la sesión
                        # rechaza escrituras a nivel de transacción.
                        "options": "-c default_transaction_read_only=on",
                    },
                    open=False,
                )
                pool.open()
                _pool = pool
    return _pool


def get_conn(request: Request) -> Iterator[object]:
    settings = request.app.state.settings
    if not settings.database_url_readonly:
        raise DatabaseUnavailable()
    try:
        conn = _get_pool(settings).getconn()
    except Exception as exc:
        raise DatabaseUnavailable() from exc
    try:
        yield conn
    finally:
        _get_pool(settings).putconn(conn)


def check_db(settings: Settings) -> bool:
    if not settings.database_url_readonly:
        return False
    try:
        with _get_pool(settings).connection() as conn:
            conn.execute("select 1")
        return True
    except Exception:
        return False
