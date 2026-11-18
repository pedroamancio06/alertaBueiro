# %% [markdown]
# # AlertaBueiro: treino do YOLOv8 (Google Colab, GPU T4)
# Ambiente de execução > Alterar tipo > GPU T4. Cole cada célula `# %%` no Colab.
#
# Fluxo:
#  1. baixa o dataset público (Universe) direto, sem fork
#  2. conta as classes e mantém só as de bueiro, remapeando para 2 classes:
#       0 boca_lobo_limpa     1 boca_lobo_total (obstruída)
#  3. junta com as suas fotos da Cidade Ademar (projeto próprio no Roboflow)
#  4. treina, avalia e exporta best.pt + metrics.json + confusion_matrix.png
#
# A API (api/inference.py) já entende esses nomes: limpa -> G=0, total -> G=1.

# %%
# !pip install -q ultralytics==8.3.40 roboflow

# %%
ROBOFLOW_API_KEY = "SUA_CHAVE"   # app.roboflow.com > Settings > API Keys

# Datasets públicos (CC BY 4.0, cite no vídeo). versao=None pega a mais recente.
# "todas": força todas as classes daquele dataset para 0 (limpa) ou 1 (obstruída).
# "mapa":  mapeamento explícito {nome_da_classe: 0 | 1 | None}; classes ausentes são descartadas.
PUBLICOS = {
    # drain (242), manhole, pothole -> drain vira "limpa", resto descartado
    "pub": {"ws": "najwadatasetpart2", "proj": "pothole_manhole_drain_detection", "versao": 2},
    # grelhas abertas vs. bloqueadas 30/60/90%
    "sdo": {"ws": "storm-drain", "proj": "storm_drain_od-oql60", "versao": 2,
            "mapa": {"grid_open": 0, "grid_block_30": 1, "grid_block_60": 1, "grid_block_90": 1}},
}

# Suas fotos rotuladas (deixe None se ainda não tiver). Classes no seu projeto:
#   boca_lobo_limpa  e  boca_lobo_total
# Ao gerar a versão no Roboflow use split 70/20/10 (train/valid/test).
LOCAL = None  # ex.: {"ws": "pedro-henrique-amancio-lopes", "proj": "alertabueiro", "versao": 1}

from roboflow import Roboflow

rf = Roboflow(api_key=ROBOFLOW_API_KEY)


def baixar(cfg, destino):
    p = rf.workspace(cfg["ws"]).project(cfg["proj"])
    v = cfg.get("versao") or max(int(str(x.version).split("/")[-1]) for x in p.versions())
    print(f"{cfg['proj']}: versão {v}")
    return p.version(v).download("yolov8", location=destino).location


fontes, config_fonte = {}, {}
for chave, cfg in {**PUBLICOS, **({"loc": LOCAL} if LOCAL else {})}.items():
    try:
        fontes[chave], config_fonte[chave] = baixar(cfg, f"/content/{chave}"), cfg
    except Exception as e:  # um dataset fora do ar não trava o resto
        print(f"!! {chave} ({cfg['proj']}) não baixou: {e}")
print(fontes)

# %%
# Conta as caixas por classe em cada dataset
import collections
import pathlib

import yaml

SPLITS = ("train", "valid", "test")


def nomes(ds):
    n = yaml.safe_load(open(f"{ds}/data.yaml"))["names"]
    return n if isinstance(n, list) else [n[k] for k in sorted(n)]


def contar(ds):
    cont = collections.Counter()
    for s in SPLITS:
        for f in pathlib.Path(ds, s, "labels").glob("*.txt"):
            for linha in f.read_text().splitlines():
                if linha.strip():
                    cont[int(linha.split()[0])] += 1
    return cont


for chave, ds in fontes.items():
    ns, c = nomes(ds), contar(ds)
    print(f"\n== {chave} ==")
    for i, n in enumerate(ns):
        print(f"  {i:2d} {n:30s} {c[i]:6d} caixas")

# %%
# Mapeamento automático -> 0 limpa | 1 obstruída | None descarta.
# CONFIRA o que foi impresso; se algo estiver errado, corrija em MAPA_MANUAL.
MAPA_MANUAL = {}  # ex.: {"drain": 0, "drain-not clean": 1}

SUJO = ("not clean", "unclean", "dirty", "clog", "block", "chok", "total", "obstru", "parcial", "sujo")


def mapear(nome):
    if nome in MAPA_MANUAL:
        return MAPA_MANUAL[nome]
    n = nome.lower().replace("_", " ").replace("-", " ")
    if not any(k in n for k in ("drain", "bueiro", "boca")):
        return None
    return 1 if any(k in n for k in SUJO) else 0


mapas = {}
for chave, ds in fontes.items():
    cfg = config_fonte[chave]
    if cfg.get("todas") is not None:
        mapas[chave] = {i: cfg["todas"] for i, _ in enumerate(nomes(ds))}
    elif "mapa" in cfg:
        mapas[chave] = {i: cfg["mapa"].get(n) for i, n in enumerate(nomes(ds))}
    else:
        mapas[chave] = {i: mapear(n) for i, n in enumerate(nomes(ds))}
    print(chave, {n: mapas[chave][i] for i, n in enumerate(nomes(ds))})

# Balanço final (caixas): idealmente limpa e obstruída na mesma ordem de grandeza
total = collections.Counter()
for chave, ds in fontes.items():
    for cls, n in contar(ds).items():
        if mapas[chave].get(cls) is not None:
            total[mapas[chave][cls]] += n
print("caixas limpa:", total[0], "| caixas obstruída:", total[1])

# %%
# Monta o dataset combinado, REDIVIDINDO tudo em 70/20/10 estratificado por classe
# (a divisão original deixava o teste sem nenhum bueiro obstruído).
# As cópias aumentadas da mesma foto (nome "<foto>.rf.<hash>") ficam no mesmo split: sem vazamento
# Imagens sem bueiro viram "negativos" (até 15% dos positivos de cada fonte pública)
import random
import shutil

random.seed(42)
OUT = pathlib.Path("/content/combinado")
shutil.rmtree(OUT, ignore_errors=True)
for s in SPLITS:
    (OUT / s / "images").mkdir(parents=True)
    (OUT / s / "labels").mkdir(parents=True)
PROPORCAO = {"train": 0.7, "valid": 0.2, "test": 0.1}
resumo = collections.Counter()


def ler(chave, ds, s, img):
    lbl = pathlib.Path(ds, s, "labels", img.stem + ".txt")
    linhas = []
    if lbl.exists():
        for l in lbl.read_text().splitlines():
            p = l.split()
            if p and mapas[chave].get(int(p[0])) is not None:
                linhas.append(" ".join([str(mapas[chave][int(p[0])]), *p[1:]]))
    return linhas


def dividir(grupos):
    """grupos: lista de listas de (img, linhas). Retorna {split: [grupos]}."""
    random.shuffle(grupos)
    n = len(grupos)
    n_test = max(1, round(n * PROPORCAO["test"])) if n >= 3 else 0
    n_val = max(1, round(n * PROPORCAO["valid"])) if n >= 3 else 0
    return {"test": grupos[:n_test], "valid": grupos[n_test:n_test + n_val],
            "train": grupos[n_test + n_val:]}


for chave, ds in fontes.items():
    grupos = collections.defaultdict(list)  # foto original -> cópias
    for s in SPLITS:
        for img in pathlib.Path(ds, s, "images").glob("*"):
            grupos[img.stem.split(".rf.")[0]].append((img, ler(chave, ds, s, img)))
    com_obstr, so_limpa, negativos = [], [], []
    for g in grupos.values():
        classes = {l.split()[0] for _, linhas in g for l in linhas}
        (com_obstr if "1" in classes else so_limpa if classes else negativos).append(g)
    limite = len(negativos) if chave == "loc" else int(0.15 * (len(com_obstr) + len(so_limpa)))
    negativos = random.sample(negativos, min(limite, len(negativos)))
    for estrato in (com_obstr, so_limpa, negativos):  # estratifica: cada classe em todo split
        for s, gs in dividir(estrato).items():
            for g in gs:
                for img, linhas in g:
                    nome = f"{chave}_{img.stem}"
                    shutil.copy(img, OUT / s / "images" / f"{nome}{img.suffix}")
                    (OUT / s / "labels" / f"{nome}.txt").write_text("\n".join(linhas))
                    resumo[(s, "pos" if linhas else "neg")] += 1

caixas = collections.Counter()
for s in SPLITS:
    for f in (OUT / s / "labels").glob("*.txt"):
        for l in f.read_text().splitlines():
            caixas[(s, ["limpa", "obstruída"][int(l.split()[0])])] += 1
print("imagens:", dict(sorted(resumo.items())))
print("caixas: ", dict(sorted(caixas.items())))

yaml.safe_dump({"path": str(OUT), "train": "train/images", "val": "valid/images",
                "test": "test/images", "names": ["boca_lobo_limpa", "boca_lobo_total"]},
               open(OUT / "data.yaml", "w"))

# %%
# NumPy 2 (Colab atual) removeu np.trapz, ainda usado pelo ultralytics 8.3.40 nas métricas
import numpy as np
np.trapz = getattr(np, "trapz", None) or np.trapezoid

from ultralytics import YOLO

modelo = YOLO("yolov8n.pt")  # nano: CPU < 3 s na API (RNF01)
modelo.train(
    data=str(OUT / "data.yaml"),
    epochs=50, imgsz=640, batch=16, patience=15,
    hsv_v=0.5, degrees=10, fliplr=0.5, mosaic=1.0,  # fotos de celular, luz variada
    project="runs", name="alertabueiro", exist_ok=True,
)

# %%
import json


def avaliar(data_yaml):
    v = melhor.val(data=data_yaml, split="test", plots=True, verbose=False)
    p, r = float(v.box.mp), float(v.box.mr)
    return v, {
        "precisao": round(p, 3), "recall": round(r, 3),
        "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0,
        "map50": round(float(v.box.map50), 3), "map50_95": round(float(v.box.map), 3),
        "por_classe_map50": {melhor.names[int(i)]: round(float(m), 3)
                             for i, m in zip(v.box.ap_class_index, v.box.ap50)},
    }


melhor = YOLO("runs/alertabueiro/weights/best.pt")
val, metricas = avaliar(str(OUT / "data.yaml"))
metricas["split"] = "test (combinado)"
metricas["datasets_publicos"] = [f"{c['ws']}/{c['proj']} (CC BY 4.0)" for k, c in config_fonte.items() if k != "loc"]

# Métrica só nas fotos da Cidade Ademar, a mais honesta para o pitch
if LOCAL and any((OUT / "test" / "images").glob("loc_*")):
    sub = pathlib.Path("/content/teste_local")
    shutil.rmtree(sub, ignore_errors=True)
    for d in ("images", "labels"):
        (sub / "test" / d).mkdir(parents=True)
        for f in (OUT / "test" / d).glob("loc_*"):
            shutil.copy(f, sub / "test" / d / f.name)
    yaml.safe_dump({"path": str(sub), "train": "test/images", "val": "test/images",
                    "test": "test/images", "names": ["boca_lobo_limpa", "boca_lobo_total"]},
                   open(sub / "data.yaml", "w"))
    metricas["cidade_ademar"] = avaliar(str(sub / "data.yaml"))[1]

print(json.dumps(metricas, indent=2, ensure_ascii=False))
json.dump(metricas, open("metrics.json", "w"), indent=2, ensure_ascii=False)
shutil.copy("runs/alertabueiro/weights/best.pt", "best.pt")
shutil.copy(f"{val.save_dir}/confusion_matrix.png", "confusion_matrix.png")  # print para o vídeo

# %%
# Latência em CPU (aproxima o ambiente da API)
import time

cpu = YOLO("best.pt")  # instância nova: a usada na GPU não pode ir para a CPU
imgs = list((OUT / "test" / "images").glob("*"))[:30]
cpu.predict(str(imgs[0]), device="cpu", imgsz=640, verbose=False)  # aquecimento
t = time.perf_counter()
for i in imgs:
    cpu.predict(str(i), device="cpu", imgsz=640, verbose=False)
print(f"Latência média em CPU: {(time.perf_counter() - t) / len(imgs):.2f} s")

# %%
from google.colab import files

# ONNX: formato usado pela API na nuvem (sem PyTorch, ~150 MB de RAM)
YOLO("best.pt").export(format="onnx", imgsz=640, opset=12, simplify=False, dynamic=False)

for f in ("best.pt", "best.onnx", "metrics.json", "confusion_matrix.png"):
    files.download(f)  # salve em AlertaBueiro/model/
