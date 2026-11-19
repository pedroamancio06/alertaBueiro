"""LGPD (RNF03) e preparo da imagem (RNF02).

Lê o GPS do EXIF antes de descartar os metadados, corrige a orientação,
reduz o tamanho e grava de novo em JPEG, o que remove o EXIF. Borra rostos
e placas com os classificadores do OpenCV, que são leves e rodam em CPU.
O telefone é guardado apenas como HMAC-SHA256.
"""
from __future__ import annotations

import hashlib
import hmac
import io

import cv2
import numpy as np
from PIL import Image, ImageOps

from . import config

_GPS_IFD = 0x8825
if config.NUM_THREADS:
    cv2.setNumThreads(config.NUM_THREADS)
_face = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
_placa = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_russian_plate_number.xml")


def _dms_para_graus(dms, ref) -> float:
    g, m, s = (float(x) for x in dms)
    valor = g + m / 60 + s / 3600
    return -valor if ref in ("S", "W") else valor


def ler_gps_exif(raw: bytes) -> tuple[float, float] | None:
    """Retorna (lat, lon) do EXIF, se a foto tiver GPS."""
    try:
        gps = Image.open(io.BytesIO(raw)).getexif().get_ifd(_GPS_IFD)
        if not gps or 2 not in gps or 4 not in gps:
            return None
        return _dms_para_graus(gps[2], gps.get(1, "N")), _dms_para_graus(gps[4], gps.get(3, "E"))
    except Exception:
        return None


def decodificar(raw: bytes) -> np.ndarray:
    """Bytes -> imagem BGR orientada e reduzida para no máximo MAX_LADO_IMG."""
    try:
        img = Image.open(io.BytesIO(raw))
        # JPEG: decodifica já reduzido (escala DCT), bem mais rápido em fotos de 12 MP
        img.draft("RGB", (config.MAX_LADO_IMG, config.MAX_LADO_IMG))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Exception as e:
        raise ValueError("Arquivo não é uma imagem válida") from e
    img.thumbnail((config.MAX_LADO_IMG, config.MAX_LADO_IMG))
    return cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)


def _borrar(img: np.ndarray, caixas) -> None:
    for (x, y, w, h) in caixas:
        roi = img[y:y + h, x:x + w]
        k = max(15, (w // 3) | 1)  # kernel ímpar proporcional ao tamanho
        img[y:y + h, x:x + w] = cv2.GaussianBlur(roi, (k, k), 0)


def anonimizar(img: np.ndarray) -> tuple[np.ndarray, dict]:
    """Borra rostos e placas. Retorna a imagem (cópia) e a contagem."""
    out = img.copy()
    # Detecta numa cópia reduzida e reescala as caixas: bem mais rápido que na foto inteira
    escala = min(1.0, config.ANON_LADO / max(img.shape[:2]))
    pequena = cv2.resize(img, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA) if escala < 1 else img
    cinza = cv2.equalizeHist(cv2.cvtColor(pequena, cv2.COLOR_BGR2GRAY))
    rostos = _face.detectMultiScale(cinza, scaleFactor=1.2, minNeighbors=5, minSize=(14, 14))
    placas = _placa.detectMultiScale(cinza, scaleFactor=1.2, minNeighbors=4, minSize=(20, 7))

    def reescalar(caixas):
        return [tuple(int(v / escala) for v in c) for c in caixas]

    _borrar(out, reescalar(rostos))
    _borrar(out, reescalar(placas))
    return out, {"rostos": len(rostos), "placas": len(placas)}


def para_jpeg(img: np.ndarray, qualidade: int = 80) -> bytes:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, qualidade])
    if not ok:
        raise ValueError("Falha ao codificar JPEG")
    return buf.tobytes()


def hash_telefone(telefone: str | None) -> str | None:
    if not telefone:
        return None
    digitos = "".join(c for c in telefone if c.isdigit())
    return hmac.new(config.TEL_SALT.encode(), digitos.encode(), hashlib.sha256).hexdigest()
