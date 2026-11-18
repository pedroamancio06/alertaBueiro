"""Deduplicação (RF03): relatos a menos de 30 m viram o mesmo ponto."""
from __future__ import annotations

from . import config
from .db import ponto_sql


def ponto_proximo(conn, lon: float, lat: float, raio_m: float = config.RAIO_DEDUP_M) -> int | None:
    """Ponto não limpo mais próximo dentro do raio, ou None."""
    p = ponto_sql()
    row = conn.execute(
        f"""SELECT id FROM ponto
            WHERE status <> 'limpo' AND ST_DWithin(geom, {p}, %s)
            ORDER BY ST_Distance(geom, {p}) LIMIT 1""",
        (lon, lat, raio_m, lon, lat),
    ).fetchone()
    return row["id"] if row else None


def confianca_agregada(confiancas: list[float]) -> float:
    """Mais relatos => mais confiança: 1 - Π(1 - c_i)."""
    resto = 1.0
    for c in confiancas:
        resto *= 1 - min(max(c or 0, 0), 0.99)
    return round(1 - resto, 3)
