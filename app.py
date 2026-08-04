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
**Instruções:**
1. Insira sua chave da API do Google Gemini acima (ou configure a variável de ambiente `GEMINI_API_KEY`).
2. Faça o upload de uma ou mais fotos de pneus.
3. Selecione o modo de análise desejado.
4. Clique em executar, revise os dados extraídos e exporte o relatório em CSV!
""")

# Cabeçalho Principal
st.title("🛞 SMART-LOG: Inspeção e Inventário de Pneus por IA")
st.markdown("Automatize a identificação do número de **Fogo**, análise de sulcos/desgaste e detecção de danos na carcaça usando visão computacional e Inteligência Artificial.")

# Verificar chave da API (prioriza input da barra lateral, depois os Secrets do Streamlit)
api_key = api_key_input
if not api_key:
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        api_key = ""

# Uploader de arquivos
uploaded_files = st.file_uploader(
    "📁 Envie as fotos dos pneus (JPG, PNG, JPEG)",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True
)

modo_analise = st.selectbox(
    "Selecione o Modo de Análise",
    [
        "Inspeção Completa (ID Fogo + Desgaste + Danos)",
        "Apenas Extrair Número de 'Fogo' (ID do Pneu)",
        "Análise Profunda de Danos e Desgaste de Banda"
    ]
)

if uploaded_files:
    st.markdown(f"### 📂 Fila de Upload ({len(uploaded_files)} imagens)")
    
    # Inicializar session state para os resultados do lote
    if "inspection_results" not in st.session_state:
        st.session_state.inspection_results = []

    if st.button("🚀 Executar Inspeção por IA em Todas as Imagens", type="primary"):
        if not api_key:
            st.error("⚠️ Por favor, insira sua chave da API Gemini na barra lateral ou configure nas Secrets para executar a inspeção.")
        else:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                
                # Usar gemini-2.5-flash para tarefas multimodais de visão
                model = genai.GenerativeModel('gemini-2.5-flash')
                
                results = []
                barra_progresso = st.progress(0)
                texto_status = st.empty()
                
                for idx, uploaded_file in enumerate(uploaded_files):
                    texto_status.text(f"Analisando imagem {idx+1} de {len(uploaded_files)}: {uploaded_file.name}...")
                    
                    bytes_dados = uploaded_file.getvalue()
                    parte_imagem = {
                        "mime_type": uploaded_file.type,
                        "data": bytes_dados
                    }
                    
                    prompt = f"""
                    Você é um inspetor especialista em inventário e manutenção de pneus para uma frota de logística (SMART-LOG). 
                    Analise esta imagem de pneu cuidadosamente. O modo de análise selecionado é: {modo_analise}.
                    
                    Extraia os seguintes detalhes em um formato estruturado em português:
                    1. Fogo (Número de identificação do pneu pintado ou gravado na lateral/banda de rodagem). Se não estiver visível, estime ou coloque 'Desconhecido'.
                    2. Marca / Fabricante (ex: Michelin, Bridgestone, Pirelli, Firestone, Goodyear).
                    3. Condição / Status da Profundidade de Sulco (Bom, Desgastado, Crítico / Precisa de Recapagem).
                    4. Danos / Anomalias Detectadas (ex: Cortes, Bolhas, Exposição de carcaça, Desgaste irregular, Vulcanização/Conserto, Nenhum).
                    5. Ação Recomendada (Manter em serviço, Enviar para recapagem, Sucatear imediatamente, Inspecionar detalhadamente).
                    6. Nível de Confiança (Alto, Médio, Baixo).
                    
                    Formate sua resposta estritamente como pares de chave-valor separados por dois-pontos (ex: Fogo: 12345), seguidos por um parágrafo de resumo curto.
                    """
                    
                    try:
                        resposta = model.generate_content([parte_imagem, prompt])
                        ai_texto = resposta.text
                    except Exception as e:
                        ai_texto = f"Erro durante a análise de IA: {str(e)}"
                    
                    results.append({
                        "Nome do Arquivo": uploaded_file.name,
                        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Analise_IA": ai_texto,
                        "Bytes_Imagem": bytes_dados
                    })
                    
                    barra_progresso.progress((idx + 1) / len(uploaded_files))
                
                st.session_state.inspection_results = results
                texto_status.success("✅ Inspeção concluída para todas as imagens com sucesso!")
                barra_progresso.empty()
                
            except ImportError:
                st.error("A biblioteca `google-generativeai` não está instalada. Instale com `pip install google-generativeai`.")
            except Exception as e:
                st.error(f"Ocorreu um erro ao inicializar a API: {str(e)}")

    # Exibir Resultados se disponíveis
    if st.session_state.inspection_results:
        st.markdown("---")
        st.subheader("📊 Resultados da Inspeção e Dados Extraídos")
        
        for i, res in enumerate(st.session_state.inspection_results):
            with st.expander(f"Inspeção #{i+1}: {res['Nome do Arquivo']} ({res['Timestamp']})", expanded=(i==0)):
                cols = st.columns([1, 2])
                with cols[0]:
                    st.image(res["Bytes_Imagem"], caption=res["Nome do Arquivo"], use_container_width=True)
                with cols[1]:
                    st.markdown("#### 🤖 Diagnóstico da IA")
                    st.write(res["Analise_IA"])
                    
                    # Formulário rápido de revisão / salvamento
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        edita_fogo = st.text_input(f"Confirmar ID Fogo #{i+1}", value="", key=f"fogo_{i}")
                    with col_b:
                        edita_status = st.selectbox(f"Status #{i+1}", ["Aprovado", "Precisa Recapagem", "Sucata", "Revisão Pendente"], key=f"status_{i}")
                    with col_c:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button(f"Salvar Registro #{i+1}", key=f"save_{i}"):
                            st.success(f"Salvo! Fogo: {edita_fogo or 'Automático'} | Status: {edita_status}")

        # Opção de Exportação em Lote
        st.markdown("### 📥 Exportar Dados em Lote")
        if st.button("Exportar Todos os Resultados para CSV"):
            dados_resumo = []
            for i, res in enumerate(st.session_state.inspection_results):
                dados_resumo.append({
                    "Nome do Arquivo": res["Nome do Arquivo"],
                    "Timestamp": res["Timestamp"],
                    "Resultados": res["Analise_IA"].replace("\n", " ")
                })
            df_export = pd.DataFrame(dados_resumo)
            csv = df_export.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Baixar Relatório CSV",
                data=csv,
                file_name=f"relatorio_inspecao_pneus_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )

else:
    st.info("👆 Por favor, envie uma ou mais fotos de pneus acima para iniciar a inspeção inteligente por IA.")

# Rodapé
st.markdown("---")
st.markdown("<p style='text-align: center; color: #64748b;'>Sistema de Gestão de Pneus SMART-LOG • Desenvolvido com Streamlit e Google Gemini AI</p>", unsafe_allow_html=True)
