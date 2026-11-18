"""Pool de conexões com o Neon (use a URL *pooled* do painel do Neon)."""
from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from . import config

_pool: ConnectionPool | None = None


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        if not config.DATABASE_URL:
            raise RuntimeError("DATABASE_URL não definida (veja .env.example)")
        _pool = ConnectionPool(
            config.DATABASE_URL,
            min_size=1,
            max_size=5,
            kwargs={"row_factory": dict_row},
            check=ConnectionPool.check_connection,  # Neon derruba conexões ociosas
            open=True,
        )
    return _pool


@contextmanager
def conn():
    """Conexão transacional: commit no fim, rollback em erro."""
    with pool().connection() as c:
        yield c


def ponto_sql() -> str:
    """Expressão SQL para criar geography a partir de (lon, lat)."""
    return "ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography"
