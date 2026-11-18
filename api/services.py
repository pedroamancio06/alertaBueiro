"""Regras de negócio compartilhadas pela API e pelos scripts de carga."""
from __future__ import annotations

from datetime import datetime

from psycopg.types.json import Jsonb

from . import config, dedup, risk, weather
from .db import ponto_sql
from .inference import SEVERIDADE, Deteccao


def atualizar_score(conn, ponto_id: int, chuva_mm: float | None = None) -> dict:
    """Recalcula gravidade, confiança e score de um ponto."""
    if chuva_mm is None:
        chuva_mm = weather.chuva_24h_mm()
    p = conn.execute(
        "SELECT id, ST_X(geom::geometry) AS lon, ST_Y(geom::geometry) AS lat FROM ponto WHERE id = %s",
        (ponto_id,),
    ).fetchone()
    relatos = conn.execute(
        "SELECT classe, tipo_residuo, confianca FROM relato "
        "WHERE ponto_id = %s ORDER BY criado_em DESC",
        (ponto_id,),
    ).fetchall()
    ultimo = relatos[0] if relatos else {"classe": None, "tipo_residuo": None}
    G =SEVERIDADE.get(ultimo["classe"], 0.0)  # estado mais recente da boca de lobo
    conf = dedup.confianca_agregada([r["confianca"] for r in relatos])
    H, n_ocorr = risk.fator_h(conn, p["lon"], p["lat"])
    V, setor = risk.fator_v(conn, p["lon"], p["lat"])
    score, fatores = risk.calcular(
        G, weather.fator_c(chuva_mm), H, V,
        extras={"chuva_24h_mm": round(chuva_mm, 1), "ocorrencias_300m": n_ocorr,
                "setor_censitario": setor, "n_relatos": len(relatos), "confianca": conf},
    )
    conn.execute(
        """UPDATE ponto SET classe = %s, tipo_residuo = %s, gravidade = %s, confianca = %s,
               score = %s, fatores = %s, n_relatos = %s, atualizado_em = now()
           WHERE id = %s""",
        (ultimo["classe"], ultimo["tipo_residuo"], G, conf, score, Jsonb(fatores),
         len(relatos), ponto_id),
    )
    return {"ponto_id": ponto_id, "score": score, "fatores": fatores}


def registrar_relato(conn, lat: float, lon: float, det: Deteccao, foto: bytes | None,
                     tel_hash: str | None, origem: str = "pwa",
                     chuva_mm: float | None = None, criado_em: datetime | None = None) -> dict:
    """Grava o relato, agrupa no ponto (RF03) e recalcula o score (RF04)."""
    ponto_id = dedup.ponto_proximo(conn, lon, lat)
    novo = ponto_id is None
    if novo:
        ponto_id = conn.execute(
            f"INSERT INTO ponto (geom) VALUES ({ponto_sql()}) RETURNING id", (lon, lat)
        ).fetchone()["id"]
    relato_id = conn.execute(
        f"""INSERT INTO relato (ponto_id, geom, foto_blur, classe, tipo_residuo, confianca,
                                tel_hash, origem, criado_em)
            VALUES (%s, {ponto_sql()}, %s, %s, %s, %s, %s, %s, COALESCE(%s, now()))
            RETURNING id""",
        (ponto_id, lon, lat, foto, det.classe, det.tipo_residuo, det.confianca,
         tel_hash, origem, criado_em),
    ).fetchone()["id"]
    resultado = atualizar_score(conn, ponto_id, chuva_mm)
    return {"relato_id": relato_id, "ponto_novo": novo, **resultado}


def recalcular_todos(conn, chuva_mm: float | None = None) -> dict:
    """Reordena a fila com a previsão atual (ou simulada) e emite alerta se preciso."""
    if chuva_mm is None:
        chuva_mm = weather.chuva_24h_mm()
    ids = [r["id"] for r in conn.execute("SELECT id FROM ponto WHERE status <> 'limpo'").fetchall()]
    for pid in ids:
        atualizar_score(conn, pid, chuva_mm)
    alerta = None
    if chuva_mm >= config.LIMIAR_ALERTA_MM:
        top = [r["id"] for r in conn.execute(
            "SELECT id FROM ponto WHERE status <> 'limpo' ORDER BY score DESC LIMIT 10"
        ).fetchall()]
        alerta = conn.execute(
            "INSERT INTO alerta (chuva_mm, pontos) VALUES (%s, %s) RETURNING id, criado_em",
            (chuva_mm, top),
        ).fetchone() | {"pontos": top, "chuva_mm": chuva_mm}
    return {"chuva_24h_mm": round(chuva_mm, 1), "pontos_recalculados": len(ids), "alerta": alerta}
