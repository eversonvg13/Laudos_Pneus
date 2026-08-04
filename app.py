import streamlit as st
import os
import base64
import json
import pandas as pd
from datetime import datetime
import httpx

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
/* Fundo geral */
.main { background-color: #0f1117; }
[data-testid="stSidebar"] { background-color: #1a1d27; }

/* Cards de pneu */
.tire-card {
    background: #1e2130;
    border: 1px solid #2e3250;
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 8px;
}

/* Badge de status */
.badge-ok      { background:#16a34a22; color:#4ade80; border:1px solid #16a34a; border-radius:6px; padding:2px 10px; font-size:12px; font-weight:700; }
.badge-recap   { background:#d9770622; color:#fb923c; border:1px solid #d97706; border-radius:6px; padding:2px 10px; font-size:12px; font-weight:700; }
.badge-scrap   { background:#dc262622; color:#f87171; border:1px solid #dc2626; border-radius:6px; padding:2px 10px; font-size:12px; font-weight:700; }
.badge-review  { background:#7c3aed22; color:#c084fc; border:1px solid #7c3aed; border-radius:6px; padding:2px 10px; font-size:12px; font-weight:700; }

/* Número de fogo em destaque */
.fogo-id {
    font-size: 28px;
    font-weight: 900;
    color: #facc15;
    letter-spacing: 2px;
    font-family: monospace;
}

button[kind="primary"] { background-color: #2563eb !important; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛞 SMART-LOG IA")
    st.markdown("**Inspetor Inteligente de Pneus**")
    st.caption("Powered by Claude · Anthropic")

    api_key = st.text_input(
        "Chave da API Anthropic",
        type="password",
        value=os.environ.get("ANTHROPIC_API_KEY", ""),
        help="Obtenha em console.anthropic.com"
    )

    st.divider()
    st.markdown("""
**Como funciona:**
1. Insira sua chave da API acima.
2. Faça upload do **lote completo** de fotos.
3. O sistema ordena as fotos **cronologicamente** pelo nome do arquivo.
4. A IA identifica automaticamente as **fotos de Fogo** (número de identificação na lateral) como âncoras.
5. As fotos seguintes até a próxima âncora são agrupadas como danos daquele pneu.
6. Um laudo é gerado para cada pneu.
""")

# ── Cabeçalho ────────────────────────────────────────────────────────────────
st.title("🛞 SMART-LOG: Inspeção de Pneus por IA")
st.markdown("Agrupamento automático por **âncora de Fogo** · Análise cronológica · Laudos individuais")
st.divider()

# ── Uploader ─────────────────────────────────────────────────────────────────
uploaded_files = st.file_uploader(
    "📁 Envie o lote completo de fotos dos pneus",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True,
    help="As fotos serão ordenadas automaticamente pelo nome do arquivo (timestamp)."
)

modo_analise = st.selectbox(
    "Modo de Análise",
    [
        "Inspeção Completa (ID Fogo + Sulco + Danos)",
        "Apenas Extrair Número de Fogo",
        "Análise Profunda de Danos e Desgaste",
    ]
)

# ── Funções auxiliares ────────────────────────────────────────────────────────

def image_to_base64(file_bytes: bytes, media_type: str) -> str:
    return base64.standard_b64encode(file_bytes).decode("utf-8")


def claude_classify_image(api_key: str, img_bytes: bytes, media_type: str) -> bool:
    """
    Retorna True se a imagem for identificada como foto de FOGO (âncora de pneu).
    """
    b64 = image_to_base64(img_bytes, media_type)
    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 50,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Esta é uma foto de pneu de caminhão. "
                            "Verifique se ela mostra a LATERAL do pneu com um número de identificação "
                            "pintado ou gravado (chamado 'número de Fogo', geralmente em tinta amarela ou branca, "
                            "ex: 32813, 33633, 3380, 30039). "
                            "Responda APENAS com a palavra FOGO se for claramente a lateral com o número de identificação, "
                            "ou DANO se for foto de banda de rodagem, sulco, desgaste ou dano. "
                            "Responda somente FOGO ou DANO."
                        ),
                    },
                ],
            }
        ],
    }

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        json=payload,
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    answer = data["content"][0]["text"].upper().strip()
    return "FOGO" in answer and "DANO" not in answer


def claude_analyze_tire(api_key: str, block: list, modo: str) -> str:
    """
    Gera laudo completo para um bloco de fotos do mesmo pneu.
    """
    content = []
    for item in block:
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": item["media_type"],
                    "data": image_to_base64(item["bytes"], item["media_type"]),
                },
            }
        )

    content.append(
        {
            "type": "text",
            "text": f"""Você é um inspetor especialista em pneus de frota de logística (sistema SMART-LOG).
Estas {len(block)} imagens pertencem ao MESMO pneu, agrupadas cronologicamente:
- A primeira imagem é a foto âncora (lateral com número de Fogo).
- As demais mostram a banda de rodagem, sulcos e possíveis danos.

Modo de análise: {modo}

Analise o conjunto e responda em português com o seguinte formato JSON (apenas o JSON, sem markdown):
{{
  "fogo": "<número de identificação visível na lateral, ou 'Desconhecido'>",
  "marca": "<Michelin / Bridgestone / Pirelli / Firestone / Goodyear / Outra / Não identificada>",
  "sulco": "<Bom (≥4mm) / Desgastado (2-4mm) / Crítico (<2mm)>",
  "danos": "<lista dos danos encontrados, ou 'Nenhum'>",
  "acao": "<Manter em serviço / Enviar para recapagem / Sucatear imediatamente / Inspecionar detalhadamente>",
  "confianca": "<Alto / Médio / Baixo>",
  "observacoes": "<notas adicionais relevantes>"
}}""",
        }
    )

    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": content}],
    }

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        json=payload,
        headers=headers,
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["content"][0]["text"].strip()


def parse_laudo(raw: str) -> dict:
    """Extrai o JSON do laudo, com fallback seguro."""
    try:
        # Remove blocos de markdown caso o modelo os inclua
        clean = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except Exception:
        return {
            "fogo": "Erro ao interpretar",
            "marca": "—",
            "sulco": "—",
            "danos": raw,
            "acao": "Inspecionar detalhadamente",
            "confianca": "Baixo",
            "observacoes": "Resposta inesperada da IA.",
        }


def status_badge(acao: str) -> str:
    acao_lower = acao.lower()
    if "serviço" in acao_lower or "manter" in acao_lower:
        return '<span class="badge-ok">✅ Manter em Serviço</span>'
    elif "recapagem" in acao_lower:
        return '<span class="badge-recap">🔄 Recapagem</span>'
    elif "sucatear" in acao_lower:
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
            st.error("⚠️ Insira sua chave da API Anthropic na barra lateral.")
            st.stop()

        # 1. Ordenação cronológica pelo nome do arquivo
        sorted_files = sorted(uploaded_files, key=lambda f: f.name)

        status_txt = st.empty()
        progress = st.progress(0)
        total = len(sorted_files)

        # 2. Classificação: FOGO ou DANO
        status_txt.info("Passo 1/2 · Identificando âncoras de Fogo em cada foto…")
        classificadas = []

        for idx, f in enumerate(sorted_files):
            raw_bytes = f.read()
            media_type = f.type or "image/jpeg"

            try:
                is_fogo = claude_classify_image(api_key, raw_bytes, media_type)
            except Exception as e:
                st.warning(f"Erro ao classificar '{f.name}': {e}. Assumindo DANO.")
                is_fogo = False

            classificadas.append(
                {"name": f.name, "bytes": raw_bytes, "media_type": media_type, "is_fogo": is_fogo}
            )
            progress.progress((idx + 1) / total * 0.45)

        # 3. Agrupamento em blocos por âncora
        blocks = []
        current = []
        for item in classificadas:
            if item["is_fogo"]:
                if current:
                    blocks.append(current)
                current = []
            current.append(item)
        if current:
            blocks.append(current)

        # 4. Geração de laudos
        status_txt.info(f"Passo 2/2 · Gerando laudos para {len(blocks)} pneu(s)…")
        results = []

        for b_idx, block in enumerate(blocks):
            status_txt.info(f"Analisando pneu {b_idx + 1} de {len(blocks)} ({len(block)} foto(s))…")
            try:
                raw_laudo = claude_analyze_tire(api_key, block, modo_analise)
                laudo = parse_laudo(raw_laudo)
            except Exception as e:
                laudo = {
                    "fogo": "Erro",
                    "marca": "—",
                    "sulco": "—",
                    "danos": str(e),
                    "acao": "Inspecionar detalhadamente",
                    "confianca": "Baixo",
                    "observacoes": "",
                }

            results.append(
                {
                    "id": b_idx + 1,
                    "files": [i["name"] for i in block],
                    "bytes_list": [i["bytes"] for i in block],
                    "media_types": [i["media_type"] for i in block],
                    "laudo": laudo,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status_manual": "Aprovado",
                    "fogo_manual": "",
                }
            )
            progress.progress(0.45 + (b_idx + 1) / len(blocks) * 0.55)

        st.session_state.results = results
        progress.empty()
        status_txt.success(f"✅ Varredura concluída! {len(blocks)} pneu(s) identificado(s).")

    # ── Exibição de resultados ───────────────────────────────────────────────
    if st.session_state.results:
        st.divider()
        st.subheader("📊 Laudos por Pneu")

        for res in st.session_state.results:
            laudo = res["laudo"]
            with st.expander(
                f"🛞 Pneu #{res['id']}  ·  Fogo: {laudo.get('fogo','?')}  ·  {len(res['files'])} foto(s)",
                expanded=(res["id"] == 1),
            ):
                # Fotos do bloco
                cols = st.columns(min(len(res["bytes_list"]), 4))
                for i, (img_b, mtype) in enumerate(zip(res["bytes_list"], res["media_types"])):
                    with cols[i % 4]:
                        st.image(img_b, caption=res["files"][i], use_container_width=True)

                st.divider()

                # Laudo resumido
                col_id, col_marca, col_sulco, col_acao = st.columns(4)
                with col_id:
                    st.markdown(f"**ID Fogo**")
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
                st.caption(f"Confiança: {laudo.get('confianca','—')}  ·  Gerado em: {res['timestamp']}")

                # Confirmação manual
                st.divider()
                c1, c2, c3 = st.columns(3)
                with c1:
                    fogo_edit = st.text_input(
                        "Confirmar / Corrigir ID Fogo",
                        value=laudo.get("fogo", ""),
                        key=f"fogo_{res['id']}",
                    )
                with c2:
                    status_edit = st.selectbox(
                        "Status Final",
                        ["Aprovado", "Precisa Recapagem", "Sucata", "Revisão Pendente"],
                        key=f"status_{res['id']}",
                    )
                with c3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button(f"💾 Salvar Pneu #{res['id']}", key=f"save_{res['id']}"):
                        res["fogo_manual"] = fogo_edit
                        res["status_manual"] = status_edit
                        st.success(f"Pneu #{res['id']} salvo · Fogo: {fogo_edit} · Status: {status_edit}")

        # ── Exportação CSV ───────────────────────────────────────────────────
        st.divider()
        st.subheader("📥 Exportar Relatório")

        if st.button("Gerar CSV"):
            rows = []
            for res in st.session_state.results:
                l = res["laudo"]
                rows.append(
                    {
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
                    }
                )

            df = pd.DataFrame(rows)
            csv_bytes = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="⬇️ Baixar Relatório CSV",
                data=csv_bytes,
                file_name=f"relatorio_pneus_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
            )

else:
    st.info("👆 Envie o lote de fotos dos pneus para iniciar a varredura.")

# ── Rodapé ───────────────────────────────────────────────────────────────────
st.divider()
st.caption("SMART-LOG · Sistema de Gestão de Pneus · Powered by Claude (Anthropic)")
