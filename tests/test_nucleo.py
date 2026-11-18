"""Testes do núcleo que não dependem de banco nem de modelo treinado."""
import io

import numpy as np
from PIL import Image

from api import dedup, inference, privacy, risk, weather


def test_score_v1_formula():
    score, fatores = risk.calcular(G=1.0, C=0.5, H=0.2, V=0.6)
    # 100 * (0.35*1 + 0.30*0.5 + 0.20*0.2 + 0.15*0.6) = 63
    assert score == 63.0
    assert sum(f["contribuicao"] for k, f in fatores.items() if k in risk.PESOS) == score
    assert set(risk.PESOS) <= set(fatores)


def test_score_limites_e_clamp():
    assert risk.calcular(0, 0, 0, 0)[0] == 0
    assert risk.calcular(1, 1, 1, 1)[0] == 100
    assert risk.calcular(2, -1, 1, 1)[0] == 70  # valores fora de 0..1 são limitados


def test_vulnerabilidade_so_aumenta():
    base, _ = risk.calcular(0.5, 0.5, 0.5, 0.0)
    for v in (0.1, 0.5, 1.0):
        assert risk.calcular(0.5, 0.5, 0.5, v)[0] >= base


def test_fator_c_normaliza_por_50mm():
    assert weather.fator_c(0) == 0
    assert weather.fator_c(25) == 0.5
    assert weather.fator_c(120) == 1.0


def test_confianca_agregada_cresce_com_relatos():
    um = dedup.confianca_agregada([0.6])
    dois = dedup.confianca_agregada([0.6, 0.6])
    assert um == 0.6 and dois > um and dois <= 1


def test_hash_telefone_nao_guarda_numero():
    h = privacy.hash_telefone("(11) 98765-4321")
    assert h == privacy.hash_telefone("11987654321")  # normaliza formatação
    assert "98765" not in h and len(h) == 64
    assert privacy.hash_telefone(None) is None


def _jpeg(w=2000, h=1500) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)).save(buf, "JPEG")
    return buf.getvalue()


def test_imagem_reduzida_e_reencodada():
    img = privacy.decodificar(_jpeg())
    assert max(img.shape[:2]) <= 1280
    anon, cont = privacy.anonimizar(img)
    assert anon.shape == img.shape and set(cont) == {"rostos", "placas"}
    out = privacy.para_jpeg(anon)
    assert out[:2] == b"\xff\xd8"
    assert privacy.ler_gps_exif(out) is None  # EXIF removido


def test_imagem_invalida():
    import pytest
    with pytest.raises(ValueError):
        privacy.decodificar(b"nao sou imagem")


def test_inferencia_modo_demo_deterministico(monkeypatch):
    monkeypatch.setattr(inference, "_modelo", lambda: None)  # força modo demo
    img = privacy.decodificar(_jpeg(640, 480))
    a, b = inference.detectar(img), inference.detectar(img)
    assert a.modo == "demo" and a.detectado and a.classe == b.classe
    assert a.gravidade == inference.SEVERIDADE[a.classe]


def test_inferencia_modelo_real_ruido_sem_boca():
    import pytest
    if inference.modo_atual() == "demo":
        pytest.skip("nenhum modelo em model/")
    det = inference.detectar(privacy.decodificar(_jpeg(640, 480)))
    assert det.modo in ("onnx", "yolo") and det.ms < 3000
    if det.detectado:  # se detectar algo, tem de ser coerente
        assert det.gravidade == inference.SEVERIDADE[det.classe]


def test_normalizar_nomes_de_classe():
    assert inference._normalizar("Boca_Lobo_Total") == "total"
    assert inference._normalizar("bueiro-parcial") == "parcial"
    assert inference._normalizar("lixo") == "lixo"
