import streamlit as st
import os
import base64
import json
import pandas as pd
from datetime import datetime
import requests
from io import BytesIO
from PIL import Image

# ── Configuração da página ──────────────────────────────────────────────────
st.set_page_config(
    page_title="SMART-LOG · Inspetor de Pneus",
    page_icon="🛞",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.main { background-color: #0f1117; }
[data-testid="stSidebar"] { background-color: #1a1d27; }
.badge-ok     { background:#16a34a22; color:#4ade80; border:1px solid #16a34a; border-radius:6px; padding:2px 10px; font-size:12px; font-weight:700; }
.badge-recap  { background:#d9770622; color:#fb923c; border:1px solid #d97706; border-radius:6px; padding:2px 10px; font-size:12px; font-weight:700; }
.badge-scrap  { background:#dc262622; color:#f87171; border:1px solid #dc2626; border-radius:6px; padding:2px 10px; font-size:12px; font-weight:700; }
.badge-review { background:#7c3aed22; color:#c084fc; border:1px solid #7c3aed; border-radius:6px; padding:2px 10px; font-size:12px; font-weight:700; }
.fogo-id { font-size:28px; font-weight:900; color:#facc15; letter-spacing:2px; font-family:monospace; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛞 SMART-LOG IA")
    st.markdown("**Inspetor Inteligente de Pneus**")
    st.caption("Powered by Groq (Qwen 3.6 27B Vision) · **100% GRATUITO**")

    # Tenta obter a chave da API de st.secrets, depois de variáveis de ambiente
    api_key_stored = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))

    api_key = st.text_input(
        "Chave da API Groq (gratuita)",
        type="password",
        value=api_key_stored,
        help="Obtenha GRATUITAMENTE em: console.groq.com/keys"
    )

    st.info("🆓 O Groq oferece um nível gratuito generoso e extremamente rápido para o modelo Qwen 3.6 27B Vision.")

    st.divider()
    st.markdown("""
**Como funciona:**
1. Cole sua chave gratuita do Groq acima.
2. Faça upload do **lote completo** de fotos.
3. O sistema ordena cronologicamente pelo nome do arquivo.
4. A IA identifica as **fotos de Fogo** (lateral com número) como âncoras.
5. As fotos seguintes são agrupadas como danos daquele pneu.
6. Um laudo consolidado é gerado para cada pneu, analisando todas as fotos individualmente.
""")

# ── Cabeçalho ────────────────────────────────────────────────────────────────
st.title("🛞 SMART-LOG: Inspeção de Pneus por IA")
st.markdown("Agrupamento automático por **âncora de Fogo** · Análise cronológica · Laudos individuais · 🆓 100% Gratuito")
st.divider()

# ── Uploader ─────────────────────────────────────────────────────────────────
uploaded_files = st.file_uploader(
    "📁 Envie o lote completo de fotos dos pneus",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True,
    help="As fotos serão ordenadas automaticamente pelo nome (timestamp)."
)

modo_analise = st.selectbox(
    "Modo de Análise",
    [
        "Inspeção Completa (ID Fogo + Sulco + Danos)",
        "Apenas Extrair Número de Fogo",
        "Análise Profunda de Danos e Desgaste",
    ]
)

# ── Funções ───────────────────────────────────────────────────────────────────

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
# Atualizado para o modelo Qwen 3.6 27B que é o atual suportado para visão
MODEL_NAME = "qwen/qwen3.6-27b"

def optimize_image(file_bytes: bytes, max_size=(1024, 1024)) -> bytes:
    """Redimensiona e comprime a imagem para reduzir o tamanho do payload."""
    try:
        img = Image.open(BytesIO(file_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=80, optimize=True)
        return buffer.getvalue()
    except Exception as e:
        return file_bytes

def image_to_base64(file_bytes: bytes) -> str:
    optimized_bytes = optimize_image(file_bytes)
    return base64.standard_b64encode(optimized_bytes).decode("utf-8")

def groq_request(api_key: str, messages: list, max_tokens: int = 500) -> str:
    """Faz uma chamada à API do Groq usando requests."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": max_tokens,
        "top_p": 1,
        "stream": False
    }
    try:
        response = requests.post(GROQ_URL, headers=headers, json=payload, timeout=60)
        if response.status_code != 200:
            raise Exception(f"Erro na API ({response.status_code}): {response.text}")
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        raise Exception(f"Falha na comunicação: {str(e)}")

def classificar_fogo(api_key: str, img_bytes: bytes) -> bool:
    """Retorna True se a foto for de FOGO."""
    base64_image = image_to_base64(img_bytes)
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Esta foto mostra a LATERAL de um pneu com um NÚMERO DE FOGO (identificação pintada/gravada)? Responda apenas FOGO ou DANO."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]
        }
    ]
    answer = groq_request(api_key, messages, max_tokens=10).upper()
    return "FOGO" in answer

def analisar_foto_individual(api_key: str, img_bytes: bytes) -> str:
    """Analisa uma única foto e retorna uma descrição do que foi visto."""
    base64_image = image_to_base64(img_bytes)
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Descreva brevemente o que você vê nesta foto de pneu (Número de Fogo, Marca, estado do sulco, ou danos específicos como cortes/bolhas). Seja conciso."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]
        }
    ]
    return groq_request(api_key, messages, max_tokens=150)

def consolidar_laudo(api_key: str, descricoes: list, modo: str) -> str:
    """Gera o laudo JSON final baseado nas descrições de todas as fotos do bloco."""
    prompt = f"""Você é um inspetor de pneus. Com base nas seguintes descrições de várias fotos do MESMO pneu, gere um laudo final em JSON.

Descrições das fotos:
{chr(10).join(descricoes)}

Modo de análise: {modo}

Responda SOMENTE o JSON:
{{
  "fogo": "<número de identificação encontrado>",
  "marca": "<marca do pneu>",
  "sulco": "<Bom/Desgastado/Crítico>",
  "danos": "<resumo dos danos encontrados>",
  "acao": "<Manter em serviço/Recapagem/Sucatear/Revisar>",
  "confianca": "<Alto/Médio/Baixo>",
  "observacoes": "<notas finais>"
}}"""
    
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    return groq_request(api_key, messages, max_tokens=500)

def parse_laudo(raw: str) -> dict:
    try:
        # Limpeza para garantir que apenas o JSON seja processado
        clean = raw.strip()
        if "```json" in clean:
            clean = clean.split("```json")[1].split("```")[0].strip()
        elif "```" in clean:
            clean = clean.split("```")[1].split("```")[0].strip()
        return json.loads(clean)
    except Exception:
        return {"fogo": "Erro", "marca": "—", "sulco": "—", "danos": raw, "acao": "Revisar", "confianca": "Baixo", "observacoes": ""}

def status_badge(acao: str) -> str:
    a = acao.lower()
    if "serviço" in a or "manter" in a: return '<span class="badge-ok">✅ Manter em Serviço</span>'
    elif "recapagem" in a: return '<span class="badge-recap">🔄 Recapagem</span>'
    elif "sucatear" in a: return '<span class="badge-scrap">⛔ Sucatear</span>'
    else: return '<span class="badge-review">🔍 Revisar</span>'

# ── Execução principal ────────────────────────────────────────────────────────
if uploaded_files:
    st.markdown(f"### 📂 Lote carregado: **{len(uploaded_files)} imagens**")

    if "results" not in st.session_state:
        st.session_state.results = []

    if st.button("🚀 Executar Varredura Inteligente", type="primary"):
        if not api_key:
            st.error("⚠️ Insira sua chave da API Groq na barra lateral.")
            st.stop()

        sorted_files = sorted(uploaded_files, key=lambda f: f.name)
        status_txt = st.empty()
        progress = st.progress(0)
        total = len(sorted_files)

        # Passo 1: Classificar e Agrupar
        status_txt.info("Passo 1/3 · Identificando âncoras de Fogo…")
        blocks, current = [], []
        
        for idx, f in enumerate(sorted_files):
            raw_bytes = f.read()
            try:
                is_fogo = classificar_fogo(api_key, raw_bytes)
            except:
                is_fogo = False
            
            item = {"name": f.name, "bytes": raw_bytes, "is_fogo": is_fogo}
            if is_fogo and current:
                blocks.append(current)
                current = []
            current.append(item)
            progress.progress((idx + 1) / total * 0.3)
        if current: blocks.append(current)

        # Passo 2 e 3: Analisar fotos e Consolidar
        results = []
        for b_idx, block in enumerate(blocks):
            status_txt.info(f"Analisando pneu {b_idx+1} de {len(blocks)} ({len(block)} fotos)…")
            
            descricoes = []
            for img_idx, item in enumerate(block):
                try:
                    desc = analisar_foto_individual(api_key, item["bytes"])
                    descricoes.append(f"Foto {img_idx+1} ({item['name']}): {desc}")
                except Exception as e:
                    descricoes.append(f"Foto {img_idx+1}: Erro na análise individual.")
            
            try:
                raw_laudo = consolidar_laudo(api_key, descricoes, modo_analise)
                laudo = parse_laudo(raw_laudo)
            except Exception as e:
                laudo = {"fogo": "Erro", "marca": "—", "sulco": "—", "danos": str(e), "acao": "Revisar", "confianca": "Baixo", "observacoes": ""}

            results.append({
                "id": b_idx + 1,
                "files": [i["name"] for i in block],
                "bytes_list": [i["bytes"] for i in block],
                "laudo": laudo,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status_manual": "Aprovado",
                "fogo_manual": "",
            })
            progress.progress(0.3 + (b_idx + 1) / len(blocks) * 0.7)

        st.session_state.results = results
        progress.empty()
        status_txt.success(f"✅ Concluído! {len(blocks)} pneu(s) analisado(s).")

    # ── Resultados ────────────────────────────────────────────────────────────
    if st.session_state.results:
        for res in st.session_state.results:
            laudo = res["laudo"]
            with st.expander(f"🛞 Pneu #{res['id']} · Fogo: {laudo.get('fogo','?')} · {len(res['files'])} fotos", expanded=(res["id"] == 1)):
                cols = st.columns(min(len(res["bytes_list"]), 4))
                for i, img_b in enumerate(res["bytes_list"]):
                    with cols[i % 4]: st.image(img_b, use_container_width=True)
                
                st.divider()
                c1, c2, c3, c4 = st.columns(4)
                c1.markdown(f"**ID Fogo**\n### {laudo.get('fogo','?')}")
                c2.markdown(f"**Marca**\n#### {laudo.get('marca','—')}")
                c3.markdown(f"**Sulco**\n#### {laudo.get('sulco','—')}")
                c4.markdown(f"**Ação**\n{status_badge(laudo.get('acao', ''))}", unsafe_allow_html=True)
                
                if laudo.get("danos"): st.info(f"**Danos:** {laudo['danos']}")
                if laudo.get("observacoes"): st.caption(f"📝 {laudo['observacoes']}")

        st.divider()
        if st.button("📥 Gerar Relatório CSV"):
            df = pd.DataFrame([{**r["laudo"], "Pneu ID": r["id"], "Timestamp": r["timestamp"]} for r in st.session_state.results])
            st.download_button("Baixar CSV", df.to_csv(index=False).encode('utf-8'), "relatorio.csv", "text/csv")
