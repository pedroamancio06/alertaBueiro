"""IA de risco: Score v1 (RF04), explicável (RNF05).

    Risco = 100 * (0,35 G + 0,30 C + 0,20 H + 0,15 V)

G gravidade (visão computacional), C chuva prevista 24 h, H histórico de
alagamento a até 300 m (CGE), V vulnerabilidade do setor censitário (IBGE).
V é sempre um termo somado: só aumenta a prioridade, nunca a reduz.
"""
from __future__ import annotations

from . import config
from .db import ponto_sql

PESOS = {"G": 0.35, "C": 0.30, "H": 0.20, "V": 0.15}
DESCRICAO = {
    "G": "Gravidade da obstrução (visão computacional)",
    "C": "Chuva prevista nas próximas 24 h",
    "H": "Histórico de alagamento a até 300 m (CGE)",
    "V": "Vulnerabilidade da área (IBGE)",
}
OCORRENCIAS_SATURACAO = 5   # 5+ ocorrências a 300 m => H = 1
V_PADRAO = 0.5              # sem setor censitário carregado


def calcular(G: float, C: float, H: float, V: float, extras: dict | None = None) -> tuple[float, dict]:
    valores = {"G": G, "C": C, "H": H, "V": V}
    fatores = {
        k: {
            "valor": round(min(max(v, 0.0), 1.0), 3),
            "peso": PESOS[k],
            "contribuicao": round(100 * PESOS[k] * min(max(v, 0.0), 1.0), 1),
            "descricao": DESCRICAO[k],
        }
        for k, v in valores.items()
    }
    if extras:
        fatores["_contexto"] = extras
    score = round(sum(f["contribuicao"] for k, f in fatores.items() if k in PESOS), 1)
    return score, fatores


def fator_h(conn, lon: float, lat: float) -> tuple[float, int]:
    row = conn.execute(
        f"SELECT count(*) AS n FROM ocorrencia_cge WHERE ST_DWithin(geom, {ponto_sql()}, %s)",
        (lon, lat, config.RAIO_HISTORICO_M),
    ).fetchone()
    n = int(row["n"])
    return min(n / OCORRENCIAS_SATURACAO, 1.0), n


def fator_v(conn, lon: float, lat: float) -> tuple[float, str | None]:
    row = conn.execute(
        "SELECT cod_setor, vulnerabilidade FROM setor_censitario "
        "WHERE ST_Intersects(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326)) LIMIT 1",
        (lon, lat),
    ).fetchone()
    if not row:
        return V_PADRAO, None
    return float(row["vulnerabilidade"]), row["cod_setor"]
