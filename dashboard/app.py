"""Painel da subprefeitura (RF05): mapa de calor, fila priorizada, OS e alerta.

    streamlit run dashboard/app.py
API_URL aponta para a API (local ou Render). Ver .env.example.
"""
from __future__ import annotations

import os

import pandas as pd
import pydeck as pdk
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
API = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
CENTRO = (-23.6720, -46.6600)

st.set_page_config(page_title="AlertaBueiro Cidade Ademar", page_icon="🌧️", layout="wide")


# ------------------------------------------------------------------ API helpers
def api(metodo: str, caminho: str, **kw):
    try:
        r = requests.request(metodo, f"{API}{caminho}", timeout=60, **kw)
    except requests.RequestException as e:
        st.error(f"API indisponível em {API}: {e}")
        st.stop()
    if r.status_code >= 400:
        st.error(f"Erro {r.status_code}: {r.text}")
        return None
    return r.json()


@st.cache_data(ttl=15)
def carregar(caminho: str):
    return api("GET", caminho)


def recarregar():
    carregar.clear()


def cor_score(s: float) -> list[int]:
    if s >= 70:
        return [200, 30, 30, 220]
    if s >= 50:
        return [240, 140, 20, 210]
    return [60, 150, 90, 190]


def fatores_df(fatores: dict) -> pd.DataFrame:
    linhas = [{"Fator": k, "Descrição": v["descricao"], "Valor (0 a 1)": v["valor"],
               "Peso": v["peso"], "Pontos no score": v["contribuicao"]}
              for k, v in fatores.items() if k in ("G", "C", "H", "V")]
    return pd.DataFrame(linhas)


# ------------------------------------------------------------------ cabeçalho
st.title("🌧️ AlertaBueiro: Subprefeitura Cidade Ademar")
st.caption("Fotos de moradores → fila de limpeza priorizada por risco de alagamento")

ind = carregar("/indicadores") or {}
prev = carregar("/previsao") or {}
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Pontos abertos", ind.get("abertos", 0))
c2.metric("Alto risco (≥70)", ind.get("alto_risco_abertos", 0))
c3.metric("Chuva prevista 24 h", f'{prev.get("chuva_24h_mm", 0)} mm',
          "ALERTA" if prev.get("alerta") else None, delta_color="inverse")
tm = ind.get("tempo_medio_relato_limpeza_h")
c4.metric("Relato → limpeza", f"{tm} h" if tm else "sem dados")
met = ind.get("metricas_modelo") or {}
c5.metric("F1 do modelo", f'{met["f1"]:.2f}' if "f1" in met else "sem dados",
          help=f'Modo do modelo: {ind.get("modo_modelo", "?")}')
if ind.get("modo_modelo") == "demo":
    st.warning("Modelo em **modo demo** (model/best.pt ausente na API), então a classificação é simulada.")

aba_mapa, aba_relato, aba_os, aba_alerta = st.tabs(
    ["🗺️ Mapa e fila", "📷 Enviar foto", "🧹 Ordens de serviço", "⚠️ Alerta de chuva"])

pontos = pd.DataFrame(carregar("/pontos") or [])
abertos = pontos[pontos["status"] != "limpo"].copy() if not pontos.empty else pontos

# ------------------------------------------------------------------ mapa + fila
with aba_mapa:
    col_mapa, col_fila = st.columns([3, 2])
    with col_mapa:
        mostrar_cge = st.toggle("Ocorrências de alagamento (CGE)", value=True)
        camadas = []
        if not abertos.empty:
            abertos["cor"] = abertos["score"].apply(cor_score)
            camadas.append(pdk.Layer("HeatmapLayer", abertos, get_position=["lon", "lat"],
                                     get_weight="score", radius_pixels=60, opacity=0.6))
            camadas.append(pdk.Layer("ScatterplotLayer", abertos, get_position=["lon", "lat"],
                                     get_fill_color="cor", get_radius=25, pickable=True))
        if mostrar_cge:
            occ = pd.DataFrame(carregar("/ocorrencias") or [])
            if not occ.empty:
                camadas.append(pdk.Layer("ScatterplotLayer", occ, get_position=["lon", "lat"],
                                         get_fill_color=[40, 90, 220, 120], get_radius=40,
                                         stroked=True, get_line_color=[40, 90, 220], pickable=True))
        st.pydeck_chart(pdk.Deck(
            layers=camadas, map_style="light",
            initial_view_state=pdk.ViewState(latitude=CENTRO[0], longitude=CENTRO[1], zoom=13.3),
            tooltip={"text": "Ponto #{id} · score {score}\n{classe} · {tipo_residuo}\n{n_relatos} relato(s)"},
        ))
        st.caption("🔴 70 ou mais: alto risco · 🟠 50 a 69 · 🟢 abaixo de 50 · 🔵 ocorrência histórica do CGE")

    with col_fila:
        st.subheader("Fila priorizada")
        if abertos.empty:
            st.info("Nenhum ponto aberto. Rode `python -m db.seed_simulado` ou envie uma foto.")
        else:
            fila = abertos[["id", "score", "classe", "tipo_residuo", "n_relatos", "status"]].rename(
                columns={"id": "Ponto", "score": "Score", "classe": "Obstrução",
                         "tipo_residuo": "Resíduo", "n_relatos": "Relatos", "status": "Status"})
            st.dataframe(fila, hide_index=True, height=330, column_config={
                "Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f")})
            escolhido = st.selectbox("Por que este score? (explicabilidade)", abertos["id"],
                                     format_func=lambda i: f"Ponto #{i}")
            p = abertos[abertos["id"] == escolhido].iloc[0]
            st.dataframe(fatores_df(p["fatores"]), hide_index=True)
            ctx = p["fatores"].get("_contexto", {})
            st.caption(f'Chuva 24 h: {ctx.get("chuva_24h_mm")} mm · ocorrências a 300 m: '
                       f'{ctx.get("ocorrencias_300m")} · confiança agregada: {ctx.get("confianca")}')
            if pd.notna(p.get("ultimo_relato_com_foto")):
                st.image(f'{API}/relatos/{int(p["ultimo_relato_com_foto"])}/foto',
                         caption="Último relato (rostos e placas borrados)", width=320)
            if p["status"] == "aberto":
                equipe = st.text_input("Equipe", "Equipe Zeladoria 1")
                if st.button("Gerar ordem de serviço", type="primary"):
                    if api("POST", "/os", json={"ponto_id": int(escolhido), "equipe": equipe}):
                        st.success("OS criada.")
                        recarregar()
                        st.rerun()

# ------------------------------------------------------------------ envio de foto
with aba_relato:
    st.subheader("Simular relato do morador (PWA / WhatsApp)")
    col_a, col_b = st.columns(2)
    with col_a:
        foto = st.file_uploader("Foto da boca de lobo", type=["jpg", "jpeg", "png"])
        usar_exif = st.checkbox("Usar GPS da foto (EXIF)", value=False)
        lat = st.number_input("Latitude", value=-23.6745, format="%.6f", disabled=usar_exif)
        lon = st.number_input("Longitude", value=-46.6560, format="%.6f", disabled=usar_exif)
        tel = st.text_input("Telefone (opcional, guardado só como hash)")
        enviar = st.button("Enviar relato", type="primary", disabled=foto is None)
    with col_b:
        if enviar and foto:
            dados = {"origem": "pwa", "telefone": tel or None}
            if not usar_exif:
                dados |= {"lat": lat, "lon": lon}
            with st.spinner("Analisando foto…"):
                r = api("POST", "/relatos", files={"foto": (foto.name, foto.getvalue(), foto.type)},
                        data={k: v for k, v in dados.items() if v is not None})
            if r:
                d = r["deteccao"]
                if not r["aceito"]:
                    st.error(r["motivo"])
                else:
                    st.success(f'Ponto #{r["ponto_id"]} · **risco {r["score"]:.0f}/100**'
                               + (" (novo ponto)" if r["ponto_novo"] else " (agrupado a ponto existente)"))
                    st.write(f'Obstrução **{d["classe"]}** · resíduo **{d["tipo_residuo"] or "não identificado"}** · '
                             f'confiança {d["confianca"]:.0%}')
                    st.dataframe(fatores_df(r["fatores"]), hide_index=True)
                    st.image(f'{API}/relatos/{r["relato_id"]}/foto', caption="Foto armazenada (anonimizada)")
                an = r["anonimizacao"]
                st.caption(f'Inferência {d["ms"]:.0f} ms · tempo total {r.get("tempo_total_ms", "?")} ms · '
                           f'modo {d["modo"]} · rostos borrados {an["rostos"]} · placas borradas {an["placas"]}')
                recarregar()

# ------------------------------------------------------------------ OS e validação
with aba_os:
    st.subheader("Ordens de serviço")
    ordens = pd.DataFrame(carregar("/os") or [])
    if ordens.empty:
        st.info("Nenhuma OS. Gere uma pela fila priorizada.")
    else:
        st.dataframe(ordens[["id", "ponto_id", "equipe", "status", "score", "aberta_em", "fechada_em"]],
                     hide_index=True)
        pendentes = ordens[ordens["status"] != "concluida"]
        if not pendentes.empty:
            st.markdown("**Validar limpeza com a foto do depois (RF06)**")
            os_id = st.selectbox("OS", pendentes["id"], format_func=lambda i: f"OS #{i}")
            depois = st.file_uploader("Foto do depois", type=["jpg", "jpeg", "png"], key="depois")
            if st.button("Validar", disabled=depois is None):
                with st.spinner("Verificando desobstrução…"):
                    r = api("POST", f"/os/{os_id}/depois",
                            files={"foto": (depois.name, depois.getvalue(), depois.type)})
                if r:
                    (st.success if r["validada"] else st.error)(r["mensagem"])
                    recarregar()
        concluidas = ordens[ordens["status"] == "concluida"]
        if not concluidas.empty:
            ver = st.selectbox("Antes × depois", concluidas["id"], format_func=lambda i: f"OS #{i}")
            a, b = st.columns(2)
            linha = concluidas[concluidas["id"] == ver].iloc[0]
            if linha["tem_foto_antes"]:
                a.image(f"{API}/os/{ver}/foto/antes", caption="Antes")
            b.image(f"{API}/os/{ver}/foto/depois", caption="Depois (validada pelo modelo)")

# ------------------------------------------------------------------ alerta
with aba_alerta:
    st.subheader("Alerta preventivo")
    st.write("Quando a previsão passa de **30 mm/24 h**, a fila é recalculada e a zeladoria "
             "recebe os 10 pontos de maior risco.")
    col_x, col_y = st.columns(2)
    if col_x.button("Recalcular com a previsão real (Open-Meteo)"):
        st.session_state["recalc"] = api("POST", "/recalcular")
        recarregar()
    mm = col_y.slider("Simular chuva (mm/24 h)", 0, 100, 40)
    if col_y.button(f"⛈️ Simular chuva forte ({mm} mm)", type="primary"):
        st.session_state["recalc"] = api("POST", "/recalcular", params={"chuva_mm": mm})
        recarregar()
    res = st.session_state.get("recalc")
    if res:
        st.info(f'{res["pontos_recalculados"]} pontos recalculados com {res["chuva_24h_mm"]} mm previstos.')
        if res["alerta"]:
            st.error(f'🚨 ALERTA #{res["alerta"]["id"]}: limpar antes do temporal')
            atual = pd.DataFrame(api("GET", "/pontos") or [])  # scores já recalculados
            if not atual.empty:
                top = atual[atual["id"].isin(res["alerta"]["pontos"])]
                st.dataframe(top[["id", "score", "classe", "tipo_residuo", "n_relatos"]], hide_index=True)
    hist = pd.DataFrame(carregar("/alertas") or [])
    if not hist.empty:
        st.markdown("**Histórico de alertas**")
        st.dataframe(hist, hide_index=True)
