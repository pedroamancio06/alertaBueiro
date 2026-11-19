"""AlertaBueiro: API de ingestão, visão computacional e risco.

Rodar local:  uvicorn api.main:app --reload
Docs:         http://localhost:8000/docs
"""
from __future__ import annotations

import json
import logging
import time

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from . import config, db, inference, privacy, services, weather

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("alertabueiro")

app = FastAPI(title="AlertaBueiro API", version="0.1.0",
              description="Fotos de moradores → fila de limpeza priorizada por risco de alagamento.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

MAX_UPLOAD = 15 * 1024 * 1024


@app.on_event("startup")
def carregar_modelo():
    """Carrega e aquece o YOLO na subida, não no primeiro relato."""
    log.info("Modelo: %s", inference.modo_atual())


@app.middleware("http")
async def latencia(request: Request, call_next):
    """Registra o tempo de cada requisição (evidência do RNF01: < 3 s)."""
    t0 = time.perf_counter()
    resp = await call_next(request)
    ms = (time.perf_counter() - t0) * 1000
    resp.headers["X-Process-Time-ms"] = f"{ms:.0f}"
    log.info("%s %s -> %s em %.0f ms", request.method, request.url.path, resp.status_code, ms)
    return resp


def _ler_foto(foto: UploadFile) -> bytes:
    raw = foto.file.read(MAX_UPLOAD + 1)
    if not raw:
        raise HTTPException(400, "Foto vazia")
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(413, "Foto maior que 15 MB")
    return raw


def _processar(raw: bytes):
    """Decodifica, anonimiza (LGPD) e roda a visão computacional."""
    etapas = {}
    t = time.perf_counter()
    try:
        img = privacy.decodificar(raw)
    except ValueError as e:
        raise HTTPException(400, str(e))
    etapas["decodificar"] = round((time.perf_counter() - t) * 1000)
    t = time.perf_counter()
    img_anon, borrados = privacy.anonimizar(img)
    etapas["anonimizar"] = round((time.perf_counter() - t) * 1000)
    det = inference.detectar(img)  # detecção na imagem original (melhor qualidade)
    etapas["inferencia"] = round(det.ms)
    borrados = {**borrados, "etapas_ms": etapas}
    return img_anon, borrados, det


# ---------------------------------------------------------------- status
@app.get("/health")
def health():
    """Use antes de gravar a demo para acordar a instância (cold start)."""
    with db.conn() as c:
        c.execute("SELECT 1")
    chuva = weather.chuva_24h_mm()  # aquece o cache da previsão
    return {"ok": True, "modelo": inference.modo_atual(), "chuva_24h_mm": round(chuva, 1)}


# ---------------------------------------------------------------- RF01-RF04
@app.post("/relatos")
def criar_relato(
    foto: UploadFile = File(...),
    lat: float | None = Form(None),
    lon: float | None = Form(None),
    telefone: str | None = Form(None),
    origem: str = Form("pwa"),
):
    """Recebe foto + localização, detecta a obstrução, agrupa e pontua."""
    t0 = time.perf_counter()
    raw = _ler_foto(foto)
    if lat is None or lon is None:
        gps = privacy.ler_gps_exif(raw)
        if not gps:
            raise HTTPException(422, "Sem localização: envie lat/lon ou uma foto com GPS")
        lat, lon = gps
    img_anon, borrados, det = _processar(raw)
    if not det.detectado:
        return {"aceito": False, "motivo": "Nenhuma boca de lobo detectada na foto",
                "deteccao": det.dict(), "anonimizacao": borrados,
                "tempo_total_ms": round((time.perf_counter() - t0) * 1000)}
    with db.conn() as c:
        res = services.registrar_relato(
            c, lat, lon, det, privacy.para_jpeg(img_anon),
            privacy.hash_telefone(telefone), origem,
        )
    return {"aceito": True, **res, "deteccao": det.dict(), "anonimizacao": borrados,
            "lat": lat, "lon": lon, "tempo_total_ms": round((time.perf_counter() - t0) * 1000)}


@app.get("/relatos/{relato_id}/foto")
def foto_relato(relato_id: int):
    with db.conn() as c:
        row = c.execute("SELECT foto_blur FROM relato WHERE id = %s", (relato_id,)).fetchone()
    if not row or not row["foto_blur"]:
        raise HTTPException(404, "Foto não encontrada")
    return Response(bytes(row["foto_blur"]), media_type="image/jpeg")


# ---------------------------------------------------------------- RF05
@app.get("/pontos")
def listar_pontos(status: str | None = None, limite: int = 500):
    """Fila priorizada: pontos ordenados por score (maior risco primeiro)."""
    filtro, params = "", []
    if status:
        filtro, params = "WHERE p.status = %s", [status]
    with db.conn() as c:
        rows = c.execute(
            f"""SELECT p.id, ST_Y(p.geom::geometry) AS lat, ST_X(p.geom::geometry) AS lon,
                       p.classe, p.tipo_residuo, p.gravidade, p.confianca, p.score,
                       p.fatores, p.status, p.n_relatos, p.criado_em, p.atualizado_em,
                       (SELECT r.id FROM relato r WHERE r.ponto_id = p.id AND r.foto_blur IS NOT NULL
                        ORDER BY r.criado_em DESC LIMIT 1) AS ultimo_relato_com_foto
                FROM ponto p {filtro}
                ORDER BY p.score DESC, p.n_relatos DESC LIMIT %s""",
            [*params, limite],
        ).fetchall()
    return rows


@app.get("/ocorrencias")
def listar_ocorrencias():
    """Ocorrências de alagamento (camada do mapa)."""
    with db.conn() as c:
        return c.execute(
            "SELECT id, ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lon, data, descricao, fonte "
            "FROM ocorrencia_cge ORDER BY data DESC"
        ).fetchall()


# ---------------------------------------------------------------- ordens de serviço / RF06
class NovaOS(BaseModel):
    ponto_id: int
    equipe: str = "Equipe 1"


@app.post("/os")
def criar_os(dados: NovaOS):
    with db.conn() as c:
        ponto = c.execute("SELECT status FROM ponto WHERE id = %s", (dados.ponto_id,)).fetchone()
        if not ponto:
            raise HTTPException(404, "Ponto não encontrado")
        if ponto["status"] == "limpo":
            raise HTTPException(409, "Ponto já está limpo")
        os_ = c.execute(
            """INSERT INTO ordem_servico (ponto_id, equipe, foto_antes)
               VALUES (%s, %s, (SELECT foto_blur FROM relato WHERE ponto_id = %s
                                AND foto_blur IS NOT NULL ORDER BY criado_em DESC LIMIT 1))
               RETURNING id, ponto_id, equipe, status, aberta_em""",
            (dados.ponto_id, dados.equipe, dados.ponto_id),
        ).fetchone()
        c.execute("UPDATE ponto SET status = 'em_servico' WHERE id = %s", (dados.ponto_id,))
    return os_


@app.get("/os")
def listar_os(status: str | None = None):
    filtro, params = "", []
    if status:
        filtro, params = "WHERE o.status = %s", [status]
    with db.conn() as c:
        return c.execute(
            f"""SELECT o.id, o.ponto_id, o.equipe, o.status, o.classe_depois, o.confianca_depois,
                       o.aberta_em, o.fechada_em, p.score,
                       o.foto_antes IS NOT NULL AS tem_foto_antes,
                       o.foto_depois IS NOT NULL AS tem_foto_depois
                FROM ordem_servico o JOIN ponto p ON p.id = o.ponto_id {filtro}
                ORDER BY o.aberta_em DESC""",
            params,
        ).fetchall()


@app.post("/os/{os_id}/depois")
def validar_limpeza(os_id: int, foto: UploadFile = File(...)):
    """A equipe envia a foto do depois; o modelo confirma a desobstrução."""
    raw = _ler_foto(foto)
    img_anon, _, det = _processar(raw)
    limpo = det.detectado and det.classe == "limpa"
    with db.conn() as c:
        os_ = c.execute("SELECT ponto_id, status FROM ordem_servico WHERE id = %s", (os_id,)).fetchone()
        if not os_:
            raise HTTPException(404, "OS não encontrada")
        if os_["status"] == "concluida":
            raise HTTPException(409, "OS já concluída")
        c.execute(
            """UPDATE ordem_servico SET foto_depois = %s, classe_depois = %s, confianca_depois = %s,
                   status = %s, fechada_em = CASE WHEN %s THEN now() END
               WHERE id = %s""",
            (privacy.para_jpeg(img_anon), det.classe, det.confianca,
             "concluida" if limpo else "reprovada", limpo, os_id),
        )
        c.execute("UPDATE ponto SET status = %s, atualizado_em = now() WHERE id = %s",
                  ("limpo" if limpo else "em_servico", os_["ponto_id"]))
    return {"os_id": os_id, "validada": limpo, "deteccao": det.dict(),
            "mensagem": "Limpeza confirmada, chamado fechado" if limpo
            else "O modelo ainda vê obstrução: envie nova foto após concluir"}


@app.get("/os/{os_id}/foto/{qual}")
def foto_os(os_id: int, qual: str):
    if qual not in ("antes", "depois"):
        raise HTTPException(400, "Use 'antes' ou 'depois'")
    with db.conn() as c:
        row = c.execute(f"SELECT foto_{qual} AS f FROM ordem_servico WHERE id = %s", (os_id,)).fetchone()
    if not row or not row["f"]:
        raise HTTPException(404, "Foto não encontrada")
    return Response(bytes(row["f"]), media_type="image/jpeg")


# ---------------------------------------------------------------- chuva / alerta
@app.get("/previsao")
def previsao():
    mm = weather.chuva_24h_mm()
    return {"chuva_24h_mm": round(mm, 1), "fator_c": round(weather.fator_c(mm), 3),
            "alerta": mm >= config.LIMIAR_ALERTA_MM}


@app.post("/recalcular")
def recalcular(chuva_mm: float | None = None):
    """Reordena a fila. Passe chuva_mm para simular um temporal na demo."""
    with db.conn() as c:
        return services.recalcular_todos(c, chuva_mm)


@app.get("/alertas")
def listar_alertas(limite: int = 10):
    with db.conn() as c:
        return c.execute(
            "SELECT id, criado_em, chuva_mm, pontos FROM alerta ORDER BY criado_em DESC LIMIT %s",
            (limite,),
        ).fetchall()


# ---------------------------------------------------------------- indicadores
@app.get("/indicadores")
def indicadores():
    with db.conn() as c:
        k = c.execute(
            f"""SELECT
                  count(*) FILTER (WHERE status <> 'limpo') AS abertos,
                  count(*) FILTER (WHERE status <> 'limpo' AND score >= {config.ALTO_RISCO}) AS alto_risco_abertos,
                  count(*) FILTER (WHERE status = 'limpo') AS limpos,
                  -- pontos limpos saem do recálculo, então o score fica congelado no fechamento
                  count(*) FILTER (WHERE status = 'limpo' AND score >= {config.ALTO_RISCO}) AS alto_risco_limpos,
                  (SELECT count(*) FROM relato) AS relatos
                FROM ponto"""
        ).fetchone()
        t = c.execute(
            """SELECT avg(EXTRACT(EPOCH FROM (o.fechada_em - r.primeiro)) / 3600) AS horas
               FROM ordem_servico o
               JOIN (SELECT ponto_id, min(criado_em) AS primeiro FROM relato GROUP BY ponto_id) r
                 ON r.ponto_id = o.ponto_id
               WHERE o.status = 'concluida'"""
        ).fetchone()
    modelo = json.loads(config.METRICS_PATH.read_text()) if config.METRICS_PATH.exists() else None
    return {**k, "tempo_medio_relato_limpeza_h": round(t["horas"], 1) if t["horas"] else None,
            "modo_modelo": inference.modo_atual(), "metricas_modelo": modelo}
