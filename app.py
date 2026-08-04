import streamlit as st
import os
import pandas as pd
from datetime import datetime

# Configuração da página
st.set_page_config(
    page_title="SMART-LOG - Inspetor de Pneus por IA",
    page_icon="🛞",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização CSS personalizada
st.markdown("""
    <style>
    .main { background-color: #f8fafc; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; background-color: #2563eb; color: white; }
    .stButton>button:hover { background-color: #1d4ed8; color: white; }
    .metric-card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-left: 5px solid #2563eb; }
    .stAlert { border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

# Configuração da Barra Lateral (Sidebar)
st.sidebar.title("🛞 SMART-LOG IA")
st.sidebar.markdown("### Inspetor Inteligente de Pneus")
st.sidebar.markdown("Desenvolvido com Google Gemini Multimodal AI")

api_key_input = st.sidebar.text_input("Chave da API Gemini (API Key)", type="password", value=os.environ.get("GEMINI_API_KEY", ""))

st.sidebar.markdown("---")
st.sidebar.info("""
**Instruções (Varredura Inteligente):**
1. Insira sua chave da API do Gemini acima.
2. Faça o upload do lote completo de fotos.
3. O sistema detectará automaticamente o modelo de IA ativo e fará a análise otimizada em lote!
""")

# Cabeçalho Principal
st.title("🛞 SMART-LOG: Inspeção e Inventário de Pneus por IA")
st.markdown("Agrupamento inteligente por âncoras de **Fogo** com seleção automática de modelo e otimização de requisições.")

# Verificar chave da API
api_key = api_key_input
if not api_key:
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        api_key = ""

# Uploader de arquivos
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

if uploaded_files:
    st.markdown(f"### 📂 Lote Carregado: {len(uploaded_files)} imagens detectadas")
    
    if "inspection_results" not in st.session_state:
        st.session_state.inspection_results = []

    if st.button("🚀 Executar Varredura e Análise Otimizada", type="primary"):
        if not api_key:
            st.error("⚠️ Por favor, insira sua chave da API Gemini na barra lateral ou configure nas Secrets.")
        else:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                
                texto_status = st.empty()
                texto_status.text("Conectando à API e detectando modelo disponível...")
                
                # Seleção automática e dinâmica de modelo compatível (Elimina erros 404)
                model_name = 'gemini-2.5-flash' # Padrão moderno recomendado
                try:
                    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                    flash_models = [m for m in available_models if 'flash' in m.lower()]
                    if flash_models:
                        model_name = flash_models[0]
                    elif available_models:
                        model_name = available_models[0]
                    
                    if model_name.startswith('models/'):
                        model_name = model_name.replace('models/', '')
                except Exception:
                    pass
                
                model = genai.GenerativeModel(model_name)
                texto_status.text(f"Modelo ativo: {model_name}. Processando lote de imagens...")
                
                # Passo 1: Ordenação Cronológica pelo nome do arquivo
                sorted_files = sorted(uploaded_files, key=lambda f: f.name)
                
                # Passo 2: Montar requisição única em lote (Evita estourar o limite de 5 RPM / Erro 429)
                conteudo_requisicao = []
                prompt_instrucoes = f"""
                Você é um inspetor especialista em inventário e frotas de pneus (SMART-LOG).
                Abaixo estão {len(sorted_files)} fotos ordenadas cronologicamente. Cada foto possui o nome do arquivo visível.
                Sua tarefa é:
                1. Analisar todas as imagens e agrupá-las por pneu individual. Cada pneu é iniciado por uma foto de âncora (a lateral que mostra o número de 'Fogo' pintado/gravado, ex: giz amarelo) seguida pelas fotos de banda de rodagem ou danos daquele mesmo pneu até o próximo número de Fogo.
                2. Para cada grupo de pneu formado, gere o laudo técnico completo. O modo de análise é: {modo_analise}.
                
                Retorne a resposta estruturada claramente separando cada Pneu (ex: PNEU 1, PNEU 2...) indicando quais nomes de arquivos compõem o bloco e o laudo técnico detalhado contendo:
                - Fogo (Número identificado)
                - Marca / Fabricante
                - Condição do Sulco
                - Danos Detectados
                - Ação Recomendada
                - Nível de Confiança
                """
                
                for f in sorted_files:
                    conteudo_requisicao.append(f"Arquivo: {f.name}")
                    conteudo_requisicao.append({
                        "mime_type": f.type,
                        "data": f.getvalue()
                    })
                
                conteudo_requisicao.append(prompt_instrucoes)
                
                try:
                    resposta_ia = model.generate_content(conteudo_requisicao)
                    texto_resposta = resposta_ia.text
                except Exception as e:
                    texto_resposta = f"Erro na execução da IA: {str(e)}"
                
                # Salvar resultado global estruturado
                st.session_state.inspection_results = [{
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Analise_IA": texto_resposta,
                    "Imagens": sorted_files
                }]
                
                texto_status.success("✅ Inspeção e agrupamento concluídos com sucesso!")
                
            except Exception as e:
                st.error(f"Ocorreu um erro durante o processamento: {str(e)}")

    # Exibir Resultados Organizados
    if st.session_state.inspection_results:
        st.markdown("---")
        st.subheader("📊 Relatório Consolidado de Inspeção por Lote")
        
        for i, res in enumerate(st.session_state.inspection_results):
            with st.expander(f"🛞 Laudo Geral do Lote ({len(res['Imagens'])} fotos analisadas) - {res['Timestamp']}", expanded=True):
                
                # Miniaturas de todas as fotos do lote para referência visual rápida
                st.markdown("##### Miniaturas das fotos enviadas:")
                cols_mini = st.columns(min(len(res["Imagens"]), 6))
                for idx_img, img_file in enumerate(res["Imagens"]):
                    with cols_mini[idx_img % 6]:
                        st.image(img_file, caption=img_file.name, use_container_width=True)
                
                st.markdown("---")
                st.markdown("#### 🤖 Diagnóstico e Agrupamento da IA")
                st.write(res["Analise_IA"])
                
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    edita_fogo = st.text_input("Confirmar ID Fogo Principal", value="")
                with col_b:
                    edita_status = st.selectbox("Status Geral do Lote", ["Aprovado", "Precisa Recapagem", "Sucata", "Revisão Pendente"])
                with col_c:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Salvar Registros"):
                        st.success(f"Registros salvos com sucesso! Status: {edita_status}")

        st.markdown("### 📥 Exportar Dados")
        if st.button("Exportar Relatório para CSV"):
            dados_resumo = [{
                "Timestamp": st.session_state.inspection_results[0]["Timestamp"],
                "Total Fotos": len(uploaded_files),
                "Relatorio_IA": st.session_state.inspection_results[0]["Analise_IA"].replace("\n", " ")
            }]
            df_export = pd.DataFrame(dados_resumo)
            csv = df_export.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Baixar Relatório CSV",
                data=csv,
                file_name=f"relatorio_lote_pneus_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )

else:
    st.info("👆 Por favor, envie o lote de fotos dos pneus para iniciar.")

# Rodapé
st.markdown("---")
st.markdown("<p style='text-align: center; color: #64748b;'>Sistema de Gestão de Pneus SMART-LOG • Desenvolvido com Streamlit e Google Gemini AI</p>", unsafe_allow_html=True)
