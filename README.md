# AlertaBueiro

Fotos de moradores → fila de limpeza de bocas de lobo priorizada por risco de alagamento.
Piloto: Subprefeitura Cidade Ademar (zona sul de SP). A spec completa está na raiz do projeto.

```
foto (PWA/WhatsApp) → API FastAPI (Render) → LGPD: borra rostos/placas
                    → YOLOv8: limpa | parcial | total + tipo de resíduo
                    → Neon (PostGIS): agrupa a 30 m, score de risco de 0 a 100
                    → Painel Streamlit: mapa de calor, fila, OS, alerta de chuva
```

| Pasta | Conteúdo |
| --- | --- |
| `api/` | FastAPI: `main.py` (rotas), `inference.py` (YOLOv8), `privacy.py` (LGPD), `dedup.py` (30 m), `risk.py` (score v1), `weather.py` (Open-Meteo), `services.py` |
| `db/` | `schema.sql`, `init_db.py`, `seed_simulado.py`, `load_dados.py` (CGE e IBGE) |
| `dashboard/` | Painel Streamlit |
| `model/` | `train_yolo.py` (Colab) → coloque aqui `best.pt` e `metrics.json` |
| `data/` | `ocorrencias_cge.csv` (preencha com as ocorrências reais) |

## Score de risco (v1)

`Risco = 100 · (0,35 G + 0,30 C + 0,20 H + 0,15 V)`.
Cada ponto guarda os fatores em `ponto.fatores`, e o painel mostra o detalhamento (RNF05).

## Rodar localmente

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
copy .env.example .env        # preencha DATABASE_URL (Neon) e TEL_SALT

python -m db.init_db                          # cria as tabelas + PostGIS
python -m db.load_dados cge data/ocorrencias_cge.csv   # ocorrências reais do CGE
python -m db.seed_simulado --relatos 150 --cge-simulado  # dados simulados (use --cge-simulado só sem o CSV real)

uvicorn api.main:app --reload                 # http://localhost:8000/docs
streamlit run dashboard/app.py                # http://localhost:8501
pytest -q                                     # testes do núcleo
```

Sem `model/best.pt`, a API roda em **modo demo**: a classificação é simulada e o painel avisa. Isso permite desenvolver tudo antes do treino.

## Treinar o modelo (17/11)

1. Fotografe de 30 a 50 bocas de lobo com o GPS do celular ligado e rotule no Roboflow junto com um dataset público.
2. Use as classes `boca_lobo_limpa`, `boca_lobo_parcial`, `boca_lobo_total`, `lixo`, `entulho`, `folhas` e `sedimento`.
3. Rode `model/train_yolo.py` no Colab (GPU T4) e baixe `best.pt`, `metrics.json` e `confusion_matrix.png` para `model/`.

## Deploy

**Neon:** crie o projeto, copie a *pooled connection string* para `DATABASE_URL` e rode `python -m db.init_db` localmente.

**Modelo em ONNX.** Na nuvem a API usa `model/best.onnx` com ONNX Runtime, sem PyTorch:
cerca de 230 MB de RAM no pico (com PyTorch eram 470 MB) e inferência de ~140 ms.
As saídas são idênticas às do ultralytics. Ao trocar o `best.pt`, rode `python model/exportar_onnx.py`.

**API no Render** (grátis, 512 MB): suba o repositório no GitHub e, no Render, use
*New → Blueprint* apontando para o repositório. O `render.yaml` já define Docker, plano free,
região Ohio (a mesma do Neon) e o health check. Preencha `DATABASE_URL` e `TEL_SALT` quando o Render pedir.
O plano free hiberna após 15 min sem uso: antes de gravar, abra `https://<app>.onrender.com/health`
e espere responder (cerca de 1 min na primeira vez).

**Painel no Streamlit Community Cloud** (grátis): *Create app → Deploy a public app from GitHub*,
arquivo `dashboard/app.py`. Em *Advanced settings → Secrets*, coloque `API_URL = "https://<app>.onrender.com"`.

## Roteiro da demo

1. Mockup do WhatsApp.
2. Aba *Enviar foto*: o painel mostra detecção, score e fatores.
3. O ponto aparece no mapa.
4. Aba *Alerta*: "Simular chuva forte (40 mm)" reordena a fila e gera o top 10.
5. Gerar a OS.
6. Aba *OS*: a foto do depois é validada e o chamado fecha.
