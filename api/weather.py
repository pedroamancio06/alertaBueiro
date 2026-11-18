"""Previsão de chuva (fator C) via Open-Meteo, gratuita e sem chave."""
from __future__ import annotations

import logging
import time

import httpx

from . import config

log = logging.getLogger(__name__)
_cache: dict[tuple, tuple[float, float]] = {}
_TTL_S = 30 * 60


def chuva_24h_mm(lat: float = config.REGIAO_LAT, lon: float = config.REGIAO_LON) -> float:
    """Soma da precipitação prevista nas próximas 24 h (mm). 0 se a API falhar."""
    chave = (round(lat, 2), round(lon, 2))
    agora = time.time()
    if chave in _cache and agora - _cache[chave][0] < _TTL_S:
        return _cache[chave][1]
    try:
        r = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "hourly": "precipitation",
                    "forecast_hours": 24, "timezone": "America/Sao_Paulo"},
            timeout=5,
        )
        r.raise_for_status()
        mm = float(sum(v or 0 for v in r.json()["hourly"]["precipitation"][:24]))
    except Exception as e:  # sem rede não derruba o relato
        log.warning("Open-Meteo indisponível: %s", e)
        return _cache.get(chave, (0, 0.0))[1]
    _cache[chave] = (agora, mm)
    return mm


def fator_c(chuva_mm: float) -> float:
    return min(max(chuva_mm, 0) / config.CHUVA_REF_MM, 1.0)
