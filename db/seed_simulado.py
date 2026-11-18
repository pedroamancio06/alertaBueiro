"""Gera relatos simulados na Cidade Ademar para popular mapa e fila.

    python -m db.seed_simulado --relatos 150 [--cge-simulado] [--limpar]

Os relatos se concentram em "focos" (fundos de vale) para exercitar a
deduplicação de 30 m. --cge-simulado cria ocorrências de alagamento fictícias
(fonte='simulado') enquanto as reais do CGE não forem carregadas.
"""
from __future__ import annotations

import argparse
import math
import random
from datetime import datetime, timedelta, timezone

from api import db, services, weather
from api.inference import SEVERIDADE, TIPOS, Deteccao

# Cidade Ademar (aprox.): focos próximos a córregos e fundos de vale
BBOX = (-23.700, -46.685, -23.650, -46.635)  # lat_min, lon_min, lat_max, lon_max
FOCOS = [(-23.6745, -46.6560), (-23.6830, -46.6650), (-23.6620, -46.6480),
         (-23.6905, -46.6420), (-23.6700, -46.6750), (-23.6560, -46.6610)]


def _ponto_aleatorio(rng: random.Random) -> tuple[float, float]:
    if rng.random() < 0.7:  # 70% perto de um foco
        lat0, lon0 = rng.choice(FOCOS)
        r_m, ang = abs(rng.gauss(0, 250)), rng.uniform(0, 2 * math.pi)
        lat = lat0 + (r_m * math.cos(ang)) / 111_320
        lon = lon0 + (r_m * math.sin(ang)) / (111_320 * math.cos(math.radians(lat0)))
        return lat, lon
    return rng.uniform(BBOX[0], BBOX[2]), rng.uniform(BBOX[1], BBOX[3])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--relatos", type=int, default=150)
    ap.add_argument("--cge-simulado", action="store_true")
    ap.add_argument("--limpar", action="store_true", help="apaga relatos/pontos simulados antes")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    chuva = weather.chuva_24h_mm()
    agora = datetime.now(timezone.utc)

    with db.conn() as c:
        if args.limpar:
            c.execute("DELETE FROM ponto WHERE id IN (SELECT ponto_id FROM relato WHERE origem = 'simulado')")
        if args.cge_simulado:
            c.execute("DELETE FROM ocorrencia_cge WHERE fonte = 'simulado'")
            for i in range(40):
                lat, lon = _ponto_aleatorio(rng)
                c.execute(
                    "INSERT INTO ocorrencia_cge (geom, data, descricao, fonte) VALUES "
                    "(ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s, %s, 'simulado')",
                    (lon, lat, (agora - timedelta(days=rng.randint(30, 700))).date(),
                     f"Alagamento simulado #{i + 1}"),
                )
        novos = 0
        for _ in range(args.relatos):
            lat, lon = _ponto_aleatorio(rng)
            classe = rng.choices(list(SEVERIDADE), weights=[1, 3, 3])[0]
            det = Deteccao(True, classe, round(rng.uniform(0.55, 0.95), 2),
                           None if classe == "limpa" else rng.choice(TIPOS),
                           SEVERIDADE[classe], "simulado")
            r = services.registrar_relato(
                c, lat, lon, det, None, None, "simulado", chuva_mm=chuva,
                criado_em=agora - timedelta(hours=rng.uniform(1, 24 * 14)),
            )
            novos += r["ponto_novo"]
    print(f"{args.relatos} relatos simulados -> {novos} pontos novos (chuva 24 h: {chuva:.1f} mm)")


if __name__ == "__main__":
    main()
