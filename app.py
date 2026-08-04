import streamlit as st
import os
import base64
import json
import pandas as pd
from datetime import datetime
import requests  # Trocando urllib por requests para melhor compatibilidade

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
    st.caption("Powered by Groq (Llama 3.2 Vision) · **100% GRATUITO**")

    # Tenta obter a chave da API de st.secrets, depois de variáveis de ambiente
    api_key_stored = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))

    api_key = st.text_input(
        "Chave da API Groq (gratuita)",
        type="password",
        value=api_key_stored,
        help="Obtenha GRATUITAMENTE em: console.groq.com/keys"
    )

    st.info("🆓 O Groq oferece um nível gratuito generoso e extremamente rápido para o modelo Llama 3.2 Vision.")

    st.divider()
    st.markdown("""
**Como funciona:**
1. Cole sua chave gratuita do Groq acima.
2. Faça upload do **lote completo** de fotos.
3. O sistema ordena cronologicamente pelo nome do arquivo.
4. A IA identifica as **fotos de Fogo** (lateral com número) como âncoras.
5. As fotos seguintes são agrupadas como danos daquele pneu.
6. Um laudo é gerado para cada pneu.
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
MODEL_NAME = "llama-3.2-11b-vision-preview"

def image_to_base64(file_bytes: bytes) -> str:
    return base64.standard_b64encode(file_bytes).decode("utf-8")

def groq_request(api_key: str, messages: list, max_tokens: int = 500) -> str:
    """Faz uma chamada à API do Groq (Llama 3.2 Vision) usando requests."""
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
        
        if response.status_code == 403:
            raise Exception("Erro 403 (Forbidden): Acesso negado. Verifique se sua chave da API é válida e se o modelo Llama 3.2 Vision está disponível na sua conta.")
        elif response.status_code != 200:
            raise Exception(f"Erro na API do Groq ({response.status_code}): {response.text}")
            
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        raise Exception(f"Falha na comunicação: {str(e)}")

def classificar_fogo(api_key: str, img_bytes: bytes, media_type: str) -> bool:
    """Retorna True se a foto for de FOGO (âncora de novo pneu)."""
    base64_image = image_to_base64(img_bytes)
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Esta é uma foto de pneu de caminhão. "
                        "Verifique se ela mostra a LATERAL do pneu com um número de identificação "
                        "pintado ou gravado (chamado 'número de Fogo', geralmente em tinta amarela ou branca). "
                        "Responda APENAS com a palavra FOGO se for a lateral com o número de identificação, "
                        "ou DANO se for foto de banda de rodagem, sulco, desgaste ou avaria. "
                        "Responda somente FOGO ou DANO, sem mais nada."
                    )
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{media_type};base64,{base64_image}"
                    }
                }
            ]
        }
    ]
    answer = groq_request(api_key, messages, max_tokens=10).upper()
    return "FOGO" in answer and "DANO" not in answer

def analisar_pneu(api_key: str, block: list, modo: str) -> str:
    """Gera laudo JSON para um bloco de fotos do mesmo pneu."""
    content = [
        {
            "type": "text",
            "text": f"""Você é um inspetor especialista em pneus de frota de logística (SMART-LOG).
Estas {len(block)} imagens pertencem ao MESMO pneu (agrupadas cronologicamente):
- Primeira imagem: lateral com número de Fogo (âncora).
- Demais: banda de rodagem, sulcos e possíveis danos.

Modo de análise: {modo}

Responda SOMENTE com o JSON abaixo (sem markdown, sem texto extra):
{{
  "fogo": "<número gravado/pintado na lateral, ou Desconhecido>",
  "marca": "<Michelin/Bridgestone/Pirelli/Firestone/Goodyear/Outra/Não identificada>",
  "sulco": "<Bom (>=4mm) / Desgastado (2-4mm) / Crítico (<2mm)>",
  "danos": "<danos encontrados ou Nenhum>",
  "acao": "<Manter em serviço / Enviar para recapagem / Sucatear imediatamente / Inspecionar detalhadamente>",
  "confianca": "<Alto / Médio / Baixo>",
  "observacoes": "<notas adicionais>"
}}"""
        }
    ]
    
    for item in block:
        base64_image = image_to_base64(item["bytes"])
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{item['media_type']};base64,{base64_image}"
            }
        })

    messages = [{"role": "user", "content": content}]
    return groq_request(api_key, messages, max_tokens=500)

def parse_laudo(raw: str) -> dict:
    try:
        clean = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except Exception:
        return {
            "fogo": "Erro ao interpretar",
            "marca": "—", "sulco": "—",
            "danos": raw,
            "acao": "Inspecionar detalhadamente",
            "confianca": "Baixo",
            "observacoes": "Resposta inesperada da IA.",
        }

def status_badge(acao: str) -> str:
    a = acao.lower()
    if "serviço" in a or "manter" in a:
        return '<span class="badge-ok">✅ Manter em Serviço</span>'
    elif "recapagem" in a:
        return '<span class="badge-recap">🔄 Recapagem</span>'
    elif "sucatear" in a:
        return '<span class="badge-scrap">⛔ Sucatear</span>'
    else:
        return '<span class="badge-review">🔍 Revisar</span>'

# ── Execução principal ────────────────────────────────────────────────────────
if uploaded_files:
    st.markdown(f"### 📂 Lote carregado: **{len(uploaded_files)} imagens**")

    if "results" not in st.session_state:
        st.session_state.results = []

    if st.button("🚀 Executar Varredura Inteligente", type="primary"):
        if not api_key:
            st.error("⚠️ Insira sua chave da API Groq na barra lateral. Obtenha gratuitamente em console.groq.com/keys")
            st.stop()

        sorted_files = sorted(uploaded_files, key=lambda f: f.name)
        status_txt = st.empty()
        progress = st.progress(0)
        total = len(sorted_files)

        # Passo 1: Classificar FOGO ou DANO
        status_txt.info("Passo 1/2 · Identificando âncoras de Fogo…")
        classificadas = []

        for idx, f in enumerate(sorted_files):
            raw_bytes = f.read()
            media_type = f.type or "image/jpeg"
            try:
                is_fogo = classificar_fogo(api_key, raw_bytes, media_type)
            except Exception as e:
                st.warning(f"Erro ao classificar '{f.name}': {e}. Assumindo DANO.")
                is_fogo = False

            classificadas.append({"name": f.name, "bytes": raw_bytes, "media_type": media_type, "is_fogo": is_fogo})
            progress.progress((idx + 1) / total * 0.45)

        # Passo 2: Agrupar em blocos por âncora de Fogo
        blocks, current = [], []
        for item in classificadas:
            if item["is_fogo"]:
                if current:
                    blocks.append(current)
                current = []
            current.append(item)
        if current:
            blocks.append(current)

        # Passo 3: Gerar laudos
        status_txt.info(f"Passo 2/2 · Gerando laudos para {len(blocks)} pneu(s)…")
        results = []

        for b_idx, block in enumerate(blocks):
            status_txt.info(f"Analisando pneu {b_idx+1} de {len(blocks)} ({len(block)} foto(s))…")
            try:
                raw_laudo = analisar_pneu(api_key, block, modo_analise)
                laudo = parse_laudo(raw_laudo)
            except Exception as e:
                laudo = {"fogo": "Erro", "marca": "—", "sulco": "—", "danos": str(e),
                         "acao": "Inspecionar detalhadamente", "confianca": "Baixo", "observacoes": ""}

            results.append({
                "id": b_idx + 1,
                "files": [i["name"] for i in block],
                "bytes_list": [i["bytes"] for i in block],
                "media_types": [i["media_type"] for i in block],
                "laudo": laudo,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status_manual": "Aprovado",
                "fogo_manual": "",
            })
            progress.progress(0.45 + (b_idx + 1) / len(blocks) * 0.55)

        st.session_state.results = results
        progress.empty()
        status_txt.success(f"✅ Varredura concluída! {len(blocks)} pneu(s) identificado(s).")

    # ── Resultados ────────────────────────────────────────────────────────────
    if st.session_state.results:
        st.divider()
        st.subheader("📊 Laudos por Pneu")

        for res in st.session_state.results:
            laudo = res["laudo"]
            with st.expander(
                f"🛞 Pneu #{res['id']}  ·  Fogo: {laudo.get('fogo','?')}  ·  {len(res['files'])} foto(s)",
                expanded=(res["id"] == 1),
            ):
                cols = st.columns(min(len(res["bytes_list"]), 4))
                for i, img_b in enumerate(res["bytes_list"]):
                    with cols[i % 4]:
                        st.image(img_b, caption=res["files"][i], use_container_width=True)

                st.divider()
                col_id, col_marca, col_sulco, col_acao = st.columns(4)
                with col_id:
                    st.markdown("**ID Fogo**")
                    st.markdown(f'<span class="fogo-id">{laudo.get("fogo","?")}</span>', unsafe_allow_html=True)
                with col_marca:
                    st.markdown("**Marca**")
                    st.markdown(f"#### {laudo.get('marca','—')}")
                with col_sulco:
                    st.markdown("**Sulco**")
                    st.markdown(f"#### {laudo.get('sulco','—')}")
                with col_acao:
                    st.markdown("**Ação Recomendada**")
                    st.markdown(status_badge(laudo.get("acao", "")), unsafe_allow_html=True)

                if laudo.get("danos"):
                    st.markdown(f"**Danos / Anomalias:** {laudo['danos']}")
                if laudo.get("observacoes"):
                    st.caption(f"📝 {laudo['observacoes']}")
                st.caption(f"Confiança: {laudo.get('confianca','—')}  ·  {res['timestamp']}")

                st.divider()
                c1, c2, c3 = st.columns(3)
                with c1:
                    fogo_edit = st.text_input("Confirmar / Corrigir ID Fogo", value=laudo.get("fogo", ""), key=f"fogo_{res['id']}")
                with c2:
                    status_edit = st.selectbox("Status Final", ["Aprovado", "Precisa Recapagem", "Sucata", "Revisão Pendente"], key=f"status_{res['id']}")
                with c3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button(f"💾 Salvar Pneu #{res['id']}", key=f"save_{res['id']}"):
                        res["fogo_manual"] = fogo_edit
                        res["status_manual"] = status_edit
                        st.success(f"Pneu #{res['id']} saved · Fogo: {fogo_edit} · Status: {status_edit}")

        st.divider()
        st.subheader("📥 Exportar Relatório")
        if st.button("Gerar CSV"):
            rows = []
            for res in st.session_state.results:
                l = res["laudo"]
                rows.append({
                    "Pneu ID": res["id"],
                    "ID Fogo (IA)": l.get("fogo", ""),
                    "ID Fogo (Confirmado)": res.get("fogo_manual", ""),
                    "Marca": l.get("marca", ""),
                    "Sulco": l.get("sulco", ""),
                    "Danos": l.get("danos", ""),
                    "Ação Recomendada": l.get("acao", ""),
                    "Confiança": l.get("confianca", ""),
                    "Status Final": res.get("status_manual", ""),
                    "Observações": l.get("observacoes", ""),
                    "Arquivos": ", ".join(res["files"]),
                    "Timestamp": res["timestamp"],
                })
            df = pd.DataFrame(rows)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Baixar CSV",
                data=csv,
                file_name=f"relatorio_pneus_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
            )
