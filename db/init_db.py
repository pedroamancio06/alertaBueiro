"""Cria as tabelas no Neon.   python -m db.init_db [--reset]"""
import sys
from pathlib import Path

import psycopg

from api import config

SCHEMA = Path(__file__).with_name("schema.sql")
TABELAS = "alerta, ordem_servico, relato, ponto, ocorrencia_cge, setor_censitario"


def main():
    with psycopg.connect(config.DATABASE_URL) as c:
        if "--reset" in sys.argv:
            c.execute(f"DROP TABLE IF EXISTS {TABELAS} CASCADE")
            print("Tabelas apagadas.")
        c.execute(SCHEMA.read_text(encoding="utf-8"))
        versao = c.execute("SELECT postgis_version()").fetchone()[0]
    print(f"Schema aplicado. PostGIS {versao}")


if __name__ == "__main__":
    main()
