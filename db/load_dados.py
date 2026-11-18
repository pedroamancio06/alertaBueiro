"""Carga de dados reais: ocorrências do CGE (fator H) e setores do IBGE (fator V).

Ocorrências do CGE: CSV com colunas data,lat,lon,descricao (data AAAA-MM-DD).
O CGE não tem API aberta: monte o CSV a partir dos boletins/mapa de pontos de
alagamento do CGE (cgesp.org) para a zona sul. Modelo em data/ocorrencias_cge.csv.

    python -m db.load_dados cge data/ocorrencias_cge.csv

Setores censitários: shapefile/GeoPackage do IBGE (malha de setores SP) já
cruzado com a planilha de agregados (densidade e renda). Informe os nomes das colunas:

    python -m db.load_dados setores setores_sp.gpkg --cod CD_SETOR --densidade dens --renda renda \
        --bbox -46.70 -23.71 -46.62 -23.64

V = 0,5 * densidade_normalizada + 0,5 * (1 - renda_normalizada)
"""
from __future__ import annotations

import argparse
import csv

import psycopg

from api import config


def carregar_cge(caminho: str, fonte: str = "CGE") -> None:
    with open(caminho, encoding="utf-8") as f:
        linhas = [r for r in csv.DictReader(f) if r.get("lat") and r.get("lon")]
    with psycopg.connect(config.DATABASE_URL) as c:
        c.execute("DELETE FROM ocorrencia_cge WHERE fonte = %s", (fonte,))
        with c.cursor() as cur:
            cur.executemany(
                "INSERT INTO ocorrencia_cge (geom, data, descricao, fonte) "
                "VALUES (ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s, %s, %s)",
                [(float(r["lon"]), float(r["lat"]), r["data"], r.get("descricao"), fonte) for r in linhas],
            )
    print(f"{len(linhas)} ocorrências ({fonte}) carregadas.")


def carregar_setores(caminho: str, cod: str, densidade: str, renda: str, bbox: list[float] | None) -> None:
    import geopandas as gpd  # dependência opcional (requirements-dados.txt)

    gdf = gpd.read_file(caminho, bbox=tuple(bbox) if bbox else None).to_crs(4326)
    gdf = gdf[[cod, densidade, renda, "geometry"]].dropna()

    def norm(s):
        return (s - s.min()) / (s.max() - s.min() or 1)

    gdf["vuln"] = 0.5 * norm(gdf[densidade].astype(float)) + 0.5 * (1 - norm(gdf[renda].astype(float)))
    gdf["geometry"] = gdf.geometry.apply(
        lambda g: g if g.geom_type == "MultiPolygon" else __import__("shapely").geometry.MultiPolygon([g])
    )
    with psycopg.connect(config.DATABASE_URL) as c:
        with c.cursor() as cur:
            cur.executemany(
                """INSERT INTO setor_censitario (cod_setor, geom, densidade, renda, vulnerabilidade)
                   VALUES (%s, ST_GeomFromText(%s, 4326), %s, %s, %s)
                   ON CONFLICT (cod_setor) DO UPDATE SET geom = EXCLUDED.geom,
                     densidade = EXCLUDED.densidade, renda = EXCLUDED.renda,
                     vulnerabilidade = EXCLUDED.vulnerabilidade""",
                [(str(r[cod]), r.geometry.wkt, float(r[densidade]), float(r[renda]), float(r.vuln))
                 for r in gdf.itertuples(index=False)],
            )
    print(f"{len(gdf)} setores censitários carregados.")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("cge")
    a.add_argument("csv")
    a.add_argument("--fonte", default="CGE")
    b = sub.add_parser("setores")
    b.add_argument("arquivo")
    b.add_argument("--cod", required=True)
    b.add_argument("--densidade", required=True)
    b.add_argument("--renda", required=True)
    b.add_argument("--bbox", type=float, nargs=4, metavar=("MINX", "MINY", "MAXX", "MAXY"))
    args = ap.parse_args()
    if args.cmd == "cge":
        carregar_cge(args.csv, args.fonte)
    else:
        carregar_setores(args.arquivo, args.cod, args.densidade, args.renda, args.bbox)


if __name__ == "__main__":
    main()
