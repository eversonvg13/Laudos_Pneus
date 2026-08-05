import os
from datetime import datetime
import pandas as pd
import streamlit as st

# Importações dos nossos módulos locais
from parser import parse_relatorio_html, CAMPOS_FIXOS
from ai_helper import (
    comprimir_imagem,
    obter_modelo_estavel,
    buscar_dados_relatorio,
    extrair_json_da_resposta,
)
from pdf_generator import gerar_pdf_laudo, gerar_pdf_fallback

# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="SMART-LOG - Inspetor de Pneus por IA",
    page_icon="🛞",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main { background-color: #f8fafc; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; background-color: #2563eb; color: white; }
    .stButton>button:hover { background-color: #1d4ed8; color: white; }
    .stAlert { border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# BARRA LATERAL
# ==============================================================================
st.sidebar.title("🛞 SMART-LOG IA")
st.sidebar.markdown("### Inspetor Inteligente de Pneus")
api_key_input = st.sidebar.text_input("Chave da API Gemini", type="password", value=os.environ.get("GEMINI_API_KEY", ""))
st.sidebar.markdown("---")
st.sidebar.info("Fotos comprimidas automaticamente. Modelo selecionado dinamicamente entre as versões estáveis do Gemini 3.x.")

api_key = api_key_input or st.secrets.get("GEMINI_API_KEY", "")

# ==============================================================================
# CABEÇALHO E PASSO 1 (RELATÓRIO)
# ==============================================================================
st.title("🛞 SMART-LOG: Inspeção de Pneus por IA")
st.markdown("Fluxo: **1) Envie o relatório** → **2) Envie as fotos** → **3) Gere o laudo em PDF**.")

st.markdown("---")
st.subheader("1️⃣ Relatório de Troca de Pneus (HTML)")

relatorio_file = st.file_uploader(
    "📄 Envie o relatório exportado em HTML (Relatório de Troca de Pneus - Modelo 4)",
    type=["html", "htm"],
    accept_multiple_files=False
)

if relatorio_file is not None:
    if st.session_state.get("relatorio_nome_processado") != relatorio_file.name:
        with st.spinner("Extraindo dados do relatório..."):
            try:
                df_relatorio = parse_relatorio_html(relatorio_file.getvalue())
                st.session_state.dados_relatorio = df_relatorio
                st.session_state.relatorio_nome_processado = relatorio_file.name
            except Exception as e:
                st.error(f"Não foi possível processar o relatório: {e}")

if "dados_relatorio" not in st.session_state:
    st.session_state.dados_relatorio = pd.DataFrame(columns=CAMPOS_FIXOS)

if not st.session_state.dados_relatorio.empty:
    st.success(f"✅ {len(st.session_state.dados_relatorio)} pneus extraídos do relatório.")
    with st.expander("📋 Ver / editar dados extraídos do relatório", expanded=False):
        st.caption("Pode corrigir manualmente qualquer campo antes de gerar o laudo.")
        st.session_state.dados_relatorio = st.data_editor(
            st.session_state.dados_relatorio,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_dados_relatorio",
        )
else:
    st.info("Nenhum relatório carregado ainda — envie o HTML acima ou preencha manualmente:")
    st.session_state.dados_relatorio = st.data_editor(
        st.session_state.dados_relatorio,
        num_rows="dynamic",
        use_container_width=True,
        key="editor_dados_relatorio_manual",
    )

# ==============================================================================
# PASSO 2 — UPLOAD DAS FOTOS
# ==============================================================================
st.markdown("---")
st.subheader("2️⃣ Fotos dos Pneus")

uploaded_files = st.file_uploader(
    "📁 Envie o lote completo de fotos dos pneus",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True
)

modo_analise = st.selectbox(
    "Selecione o Modo de Análise",
    [
        "Inspeção Completa (ID Fogo + Sulco + Danos)",
        "Apenas Extrair Número de 'Fogo' (ID do Pneu)",
        "Análise Profunda de Danos e Desgaste de Banda"
    ]
)

# ==============================================================================
# PASSO 3 — EXECUÇÃO E EXIBIÇÃO
# ==============================================================================
if uploaded_files:
    st.markdown("---")
    st.subheader("3️⃣ Executar Análise e Gerar Laudo")
    st.markdown(f"📂 Lote carregado: **{len(uploaded_files)} imagens**")

    if "inspection_results" not in st.session_state:
        st.session_state.inspection_results = []

    if st.button("🚀 Executar Varredura, Cruzar Dados e Gerar Laudo", type="primary"):
        if not api_key:
            st.error("⚠️ Por favor, insira sua chave da API Gemini na barra lateral.")
        else:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)

                texto_status = st.empty()
                texto_status.text("Selecionando modelo estável...")

                nome_modelo_ativo = obter_modelo_estavel(genai)
                texto_status.text(f"Conectado ao modelo: {nome_modelo_ativo}. Comprimindo lote de fotos...")

                model = genai.GenerativeModel(nome_modelo_ativo)
                sorted_files = sorted(uploaded_files, key=lambda f: f.name)

                prompt_instrucoes = f"""
                Você é um inspetor especialista em inventário de pneus de frota (SMART-LOG).
                Abaixo estão {len(sorted_files)} fotos ordenadas cronologicamente.

                Sua tarefa:
                1. Analise todas as imagens e agrupe-as por pneu individual. Cada novo pneu começa com a
                   foto da lateral contendo o número de 'Fogo' (identificação pintada em giz/tinta, ex: 32813),
                   seguida das fotos de banda de rodagem/sulco/danos daquele pneu até a próxima foto de 'Fogo'.
                2. Para cada pneu, leia o número de Fogo exatamente como aparece na foto (todos os dígitos,
                   incluindo zeros à esquerda se estiverem visíveis).
                3. Modo de análise solicitado: {modo_analise}.

                Responda SOMENTE com um array JSON válido (nada de texto antes ou depois, nada de markdown),
                no seguinte formato exato, um objeto por pneu:

                [
                  {{
                    "fogo": "string (número lido na foto)",
                    "marca": "string (observado na foto)",
                    "sulco": "string (observado na foto)",
                    "danos": "string (observado na foto)",
                    "acao_recomendada": "string",
                    "confianca": "Alta | Média | Baixa"
                  }}
                ]

                NÃO invente dados de placa, posição, quilometragem ou datas — essas informações não vêm
                das fotos e serão preenchidas separadamente a partir do relatório da frota.
                """

                conteudo_requisicao = []
                for f in sorted_files:
                    bytes_comprimidos = comprimir_imagem(f.getvalue())
                    conteudo_requisicao.append(f"Arquivo: {f.name}")
                    conteudo_requisicao.append({"mime_type": "image/jpeg", "data": bytes_comprimidos})
                conteudo_requisicao.append(prompt_instrucoes)

                texto_status.text(f"Enviando dados para a IA ({nome_modelo_ativo})...")
                resposta_ia = model.generate_content(conteudo_requisicao)

                pneus_estruturados = None
                erro_parse = None
                try:
                    pneus_ia = extrair_json_da_resposta(resposta_ia.text)
                    tabela_df = st.session_state.dados_relatorio
                    pneus_estruturados = []
                    for item in pneus_ia:
                        fogo_lido = str(item.get("fogo", "")).strip()
                        dados_tabela = buscar_dados_relatorio(fogo_lido, tabela_df)

                        pneu = {
                            "fogo": fogo_lido,
                            "pos": dados_tabela.get("POS", "") if dados_tabela else "",
                            "veiculo": dados_tabela.get("VEICULO", "") if dados_tabela else "",
                            "medida": dados_tabela.get("MEDIDA", "") if dados_tabela else "",
                            "retirada": dados_tabela.get("RETIRADA", "") if dados_tabela else "",
                            "local": dados_tabela.get("LOCAL", "") if dados_tabela else "",
                            "km_pos": dados_tabela.get("KM/POS", "") if dados_tabela else "",
                            "km_total": dados_tabela.get("KM TOTAL", "") if dados_tabela else "",
                            "marca": item.get("marca", ""),
                            "sulco": item.get("sulco", ""),
                            "danos": item.get("danos", ""),
                            "acao_recomendada": item.get("acao_recomendada", ""),
                            "confianca": item.get("confianca", ""),
                            "fogo_localizado_na_planilha": dados_tabela is not None,
                        }
                        pneus_estruturados.append(pneu)
                except Exception as e:
                    erro_parse = str(e)

                st.session_state.inspection_results = [{
                    "Timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    "Modelo_Usado": nome_modelo_ativo,
                    "Analise_IA_Bruta": resposta_ia.text,
                    "Pneus": pneus_estruturados,
                    "Erro_Parse": erro_parse,
                    "Imagens": sorted_files
                }]

                texto_status.success(f"✅ Inspeção concluída com sucesso via {nome_modelo_ativo}!")

            except Exception as e:
                st.error(f"Erro no processamento: {str(e)}")

    # Exibição dos Resultados
    if st.session_state.inspection_results:
        st.markdown("---")
        st.subheader("📊 Laudo Consolidado")

        for res in st.session_state.inspection_results:
            with st.expander(f"🛞 Laudo do Lote ({len(res['Imagens'])} fotos) - Modelo: {res.get('Modelo_Usado', 'gemini-flash-latest')}", expanded=True):
                st.markdown("##### Miniaturas Enviadas:")
                cols = st.columns(min(len(res["Imagens"]), 6))
                for idx, img_file in enumerate(res["Imagens"]):
                    with cols[idx % 6]:
                        st.image(img_file, caption=img_file.name, use_container_width=True)

                st.markdown("---")

                if res["Pneus"]:
                    st.markdown("#### 🤖 Laudo por Pneu")
                    for i, pneu in enumerate(res["Pneus"], start=1):
                        titulo = f"PNEU {i} — FOGO {pneu.get('fogo', 'N/A')}"
                        if pneu.get("fogo_localizado_na_planilha") is False:
                            titulo += " ⚠️ (não encontrado na planilha)"
                        with st.container(border=True):
                            st.markdown(f"**{titulo}**")
                            c1, c2 = st.columns(2)
                            with c1:
                                st.write(f"**POS:** {pneu.get('pos', '')}")
                                st.write(f"**VEICULO:** {pneu.get('veiculo', '')}")
                                st.write(f"**MEDIDA:** {pneu.get('medida', '')}")
                                st.write(f"**RETIRADA:** {pneu.get('retirada', '')}")
                            with c2:
                                st.write(f"**LOCAL:** {pneu.get('local', '')}")
                                st.write(f"**KM/POS:** {pneu.get('km_pos', '')}")
                                st.write(f"**KM TOTAL:** {pneu.get('km_total', '')}")
                                st.write(f"**Confiança:** {pneu.get('confianca', '')}")
                            st.write(f"**Marca/Fabricante:** {pneu.get('marca', '')}")
                            st.write(f"**Condição do Sulco:** {pneu.get('sulco', '')}")
                            st.write(f"**Danos/Anomalias:** {pneu.get('danos', '')}")
                            st.write(f"**Ação Recomendada:** {pneu.get('acao_recomendada', '')}")

                    pdf_bytes = gerar_pdf_laudo(res["Pneus"], res["Timestamp"])
                    st.download_button(
                        label="📥 Baixar Laudo Técnico em PDF",
                        data=pdf_bytes,
                        file_name=f"laudo_pneus_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf",
                        type="primary",
                    )
                else:
                    st.warning(
                        "⚠️ A IA respondeu, mas não foi possível estruturar o resultado automaticamente "
                        f"({res.get('Erro_Parse', 'motivo desconhecido')}). Veja a resposta bruta abaixo e, "
                        "se necessário, baixe o laudo em formato simples."
                    )
                    st.text_area("Resposta bruta da IA", res["Analise_IA_Bruta"], height=300)
                    pdf_fallback = gerar_pdf_fallback(res["Analise_IA_Bruta"], res["Timestamp"])
                    st.download_button(
                        label="📥 Baixar Laudo (texto simples) em PDF",
                        data=pdf_fallback,
                        file_name=f"laudo_pneus_bruto_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf",
                    )
else:
    st.info("👆 Envie o relatório e as fotos para começar.")
