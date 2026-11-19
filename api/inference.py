"""Visão computacional (RF02): detecta a boca de lobo e classifica a obstrução.

Classes do modelo treinado (model/train_yolo.py):
    boca_lobo_limpa, boca_lobo_total    (e opcionalmente boca_lobo_parcial)
    lixo, entulho, folhas, sedimento    (tipo de resíduo, se o modelo tiver)

Ordem de preferência do modelo:
    1. model/best.onnx com ONNX Runtime: leve (~150 MB de RAM), sem PyTorch. É o usado na nuvem.
    2. model/best.pt com ultralytics: precisa de PyTorch, útil no desenvolvimento.
    3. modo demo: classificação determinística derivada do hash da imagem,
       para desenvolver o resto do sistema sem modelo treinado.
"""
from __future__ import annotations

import ast
import hashlib
import time
from dataclasses import asdict, dataclass, field
from functools import lru_cache

import cv2
import numpy as np

from . import config

SEVERIDADE = {"limpa": 0.0, "parcial": 0.5, "total": 1.0}
TIPOS = ("lixo", "entulho", "folhas", "sedimento")
CONF_MIN = 0.25
IOU_NMS = 0.7      # mesmo padrão do ultralytics
IMGSZ = 640


@dataclass
class Deteccao:
    detectado: bool
    classe: str | None = None          # limpa | parcial | total
    confianca: float = 0.0
    tipo_residuo: str | None = None
    gravidade: float = 0.0             # fator G
    modo: str = "onnx"                 # onnx | yolo | demo
    ms: float = 0.0
    caixas: list[dict] = field(default_factory=list)

    def dict(self) -> dict:
        return asdict(self)


def _normalizar(nome: str) -> str:
    n = nome.lower().strip().replace("-", "_").replace(" ", "_")
    for prefixo in ("boca_lobo_", "boca_de_lobo_", "bueiro_"):
        if n.startswith(prefixo):
            return n[len(prefixo):]
    return n


# ------------------------------------------------------------------ backend ONNX
class _ModeloOnnx:
    modo = "onnx"

    def __init__(self, caminho):
        import onnxruntime as ort

        opcoes = ort.SessionOptions()
        opcoes.intra_op_num_threads = config.NUM_THREADS or 2
        opcoes.inter_op_num_threads = 1
        opcoes.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self.sessao = ort.InferenceSession(str(caminho), opcoes, providers=["CPUExecutionProvider"])
        self.entrada = self.sessao.get_inputs()[0].name
        meta = self.sessao.get_modelmeta().custom_metadata_map
        self.nomes = ast.literal_eval(meta["names"])

    @staticmethod
    def _letterbox(img: np.ndarray):
        """Redimensiona mantendo a proporção e completa com cinza até 640x640."""
        h, w = img.shape[:2]
        r = min(IMGSZ / h, IMGSZ / w)
        nw, nh = round(w * r), round(h * r)
        px, py = (IMGSZ - nw) / 2, (IMGSZ - nh) / 2
        img = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
        topo, base = round(py - 0.1), round(py + 0.1)
        esq, dir_ = round(px - 0.1), round(px + 0.1)
        img = cv2.copyMakeBorder(img, topo, base, esq, dir_, cv2.BORDER_CONSTANT, value=(114, 114, 114))
        return img, r, esq, topo

    def prever(self, img: np.ndarray, conf: float = CONF_MIN) -> list[dict]:
        quadro, r, esq, topo = self._letterbox(img)
        x = cv2.cvtColor(quadro, cv2.COLOR_BGR2RGB).transpose(2, 0, 1)[None].astype(np.float32) / 255.0
        saida = self.sessao.run(None, {self.entrada: x})[0][0].T     # (8400, 4 + n_classes)
        scores = saida[:, 4:]
        cls = scores.argmax(1)
        confs = scores[np.arange(len(cls)), cls]
        ok = confs >= conf
        if not ok.any():
            return []
        cx, cy, bw, bh = saida[ok, :4].T
        cls, confs = cls[ok], confs[ok]
        # de volta para as coordenadas da imagem original
        x1 = ((cx - bw / 2) - esq) / r
        y1 = ((cy - bh / 2) - topo) / r
        caixas_xywh = np.stack([x1, y1, bw / r, bh / r], 1)
        manter = cv2.dnn.NMSBoxesBatched(caixas_xywh.tolist(), confs.tolist(), cls.tolist(), conf, IOU_NMS)
        h, w = img.shape[:2]
        resultado = []
        for i in np.array(manter).flatten():
            bx, by, bw_, bh_ = caixas_xywh[i]
            resultado.append({
                "classe": _normalizar(self.nomes[int(cls[i])]),
                "conf": round(float(confs[i]), 3),
                "xyxy": [round(max(0, bx)), round(max(0, by)), round(min(w, bx + bw_)), round(min(h, by + bh_))],
            })
        return sorted(resultado, key=lambda c: -c["conf"])


# ------------------------------------------------------------------ backend PyTorch
class _ModeloPt:
    modo = "yolo"

    def __init__(self, caminho):
        from ultralytics import YOLO  # import tardio: só carrega torch se for usado
        self.modelo = YOLO(str(caminho))

    def prever(self, img: np.ndarray, conf: float = CONF_MIN) -> list[dict]:
        r = self.modelo.predict(img, conf=conf, imgsz=IMGSZ, verbose=False)[0]
        return [{"classe": _normalizar(r.names[int(b.cls)]), "conf": round(float(b.conf), 3),
                 "xyxy": [round(v) for v in b.xyxy[0].tolist()]} for b in r.boxes]


@lru_cache(maxsize=1)
def _modelo():
    onnx = config.MODEL_PATH.with_suffix(".onnx")
    if onnx.exists():
        modelo = _ModeloOnnx(onnx)
    elif config.MODEL_PATH.exists():
        modelo = _ModeloPt(config.MODEL_PATH)
    else:
        return None
    # a 1ª predição é lenta (inicialização); aquece aqui para não pesar no 1º relato
    modelo.prever(np.zeros((IMGSZ, IMGSZ, 3), dtype=np.uint8))
    return modelo


def modo_atual() -> str:
    m = _modelo()
    return m.modo if m is not None else "demo"


def _demo(img: np.ndarray) -> Deteccao:
    h = int(hashlib.sha1(img.tobytes()[:200_000]).hexdigest(), 16)
    classe = ("limpa", "parcial", "parcial", "total", "total")[h % 5]
    tipo = None if classe == "limpa" else TIPOS[(h >> 8) % 4]
    conf = 0.70 + ((h >> 16) % 25) / 100
    return Deteccao(True, classe, round(conf, 2), tipo, SEVERIDADE[classe], "demo")


def detectar(img: np.ndarray) -> Deteccao:
    """img em BGR (OpenCV)."""
    modelo = _modelo()  # carga/aquecimento fica fora da medição
    t0 = time.perf_counter()
    if modelo is None:
        det = _demo(img)
    else:
        caixas = modelo.prever(img)
        bocas = [c for c in caixas if c["classe"] in SEVERIDADE]
        residuos = [c for c in caixas if c["classe"] in TIPOS]
        if not bocas:
            det = Deteccao(False, modo=modelo.modo, caixas=caixas)
        else:
            # a boca de lobo mais obstruída manda; empate fica com a maior confiança
            top = max(bocas, key=lambda c: (SEVERIDADE[c["classe"]], c["conf"]))
            tipo = max(residuos, key=lambda c: c["conf"])["classe"] if residuos else None
            det = Deteccao(True, top["classe"], top["conf"], tipo,
                           SEVERIDADE[top["classe"]], modelo.modo, caixas=caixas)
    det.ms = round((time.perf_counter() - t0) * 1000, 1)
    return det
