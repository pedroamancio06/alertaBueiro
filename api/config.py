"""Configuração via variáveis de ambiente (.env local ou painel do Render)."""
import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "")
MODEL_PATH = Path(os.getenv("MODEL_PATH", RAIZ / "model" / "best.pt"))
METRICS_PATH = Path(os.getenv("METRICS_PATH", RAIZ / "model" / "metrics.json"))
TEL_SALT = os.getenv("TEL_SALT", "troque-este-salt")

# Centro da Subprefeitura Cidade Ademar (previsão de chuva regional)
REGIAO_LAT = float(os.getenv("REGIAO_LAT", "-23.6720"))
REGIAO_LON = float(os.getenv("REGIAO_LON", "-46.6600"))

RAIO_DEDUP_M = 30          # RF03
RAIO_HISTORICO_M = 300     # fator H
CHUVA_REF_MM = 50.0        # normalização do fator C
LIMIAR_ALERTA_MM = 30.0    # RF07
ALTO_RISCO = 70            # score a partir do qual o ponto é "alto risco"
MAX_LADO_IMG = 1280        # RNF02: reduz fotos grandes antes de guardar
ANON_LADO = 512            # lado da cópia reduzida usada para achar rostos e placas

# Threads de CPU para OpenCV e ONNX Runtime (0 = automático). No Render free a CPU
# é uma fração de núcleo: muitas threads disputando a cota deixam tudo mais lento.
NUM_THREADS = int(os.getenv("NUM_THREADS", "0"))
