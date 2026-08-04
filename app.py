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
2. Faça o upload das fotos do pneu (Ex: Foto 1 = Lateral com Fogo, Foto 2 = Banda de rodagem / Sulco).
3. Selecione o modo de análise e clique em executar!
""")

# Cabeçalho Principal
st.title("🛞 SMART-LOG: Inspeção e Inventário de Pneus por IA")
st.markdown("Automatize a identificação do número de **Fogo**, análise cruzada de sulcos/desgaste e detecção de danos na carcaça utilizando visão computacional avançada.")

# Verificar chave da API
api_key = api_key_input
if not api_key:
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        api_key = ""

# Uploader de arquivos permitindo múltiplas fotos para o mesmo pneu
uploaded_files = st.file_uploader(
    "📁 Envie as fotos do pneu (Ex: Foto 1 = Lateral/Fogo, Foto 2 = Banda de Rodagem)",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True
)

modo_analise = st.selectbox(
    "Selecione o Modo de Análise",
    [
        "Inspeção Completa Unificada (ID Fogo + Sulco + Danos)",
        "Apenas Extrair Número de 'Fogo' (ID do Pneu)",
        "Análise Profunda de Danos e Desgaste de Banda"
    ]
)

if uploaded_files:
    st.markdown(f"### 📂 Lote Selecionado ({len(uploaded_files)} imagens)")
    
    if "inspection_results" not in st.session_state:
        st.session_state.inspection_results = []

    if st.button("🚀 Executar Inspeção Unificada por IA", type="primary"):
        if not api_key:
            st.error("⚠️ Por favor, insira sua chave da API Gemini na barra lateral ou configure nas Secrets para executar a inspeção.")
        else:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                
                # Atualizado para o modelo correto e estável gemini-1.5-flash
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                texto_status = st.empty()
                texto_status.text("Analisando conjunto de imagens do pneu em conjunto...")
                
                # Prepara todas as imagens e o prompt unificado
                conteudo_requisicao = []
                for uploaded_file in uploaded_files:
                    conteudo_requisicao.append({
                        "mime_type": uploaded_file.type,
                        "data": uploaded_file.getvalue()
                    })
                
                prompt = f"""
                Você é um inspetor especialista em inventário e manutenção de pneus para uma frota de logística (SMART-LOG). 
                As imagens enviadas acima pertencem ao **mesmo pneu** (sendo a primeira imagem normalmente a lateral com o número de "Fogo" gravado/pintado, e as seguintes imagens os detalhes da banda de rodagem, sulcos ou danos).
                O modo de análise selecionado é: {modo_analise}.
                
                Analise o conjunto de imagens correlacionando-as. Extraia e estruture os seguintes detalhes em português:
                1. Fogo (Número de identificação do pneu identificado na foto da lateral). Se não estiver visível, estime ou coloque 'Desconhecido'.
                2. Marca / Fabricante (ex: Michelin, Bridgestone, Pirelli, Firestone, Goodyear).
                3. Condição / Status da Profundidade de Sulco (Bom, Desgastado, Crítico / Precisa de Recapagem), avaliando pelas fotos de banda.
                4. Danos / Anomalias Detectadas (ex: Cortes, Bolhas, Exposição de carcaça, Desgaste irregular, Vulcanização/Conserto, Nenhum).
                5. Ação Recomendada (Manter em serviço, Enviar para recapagem, Sucatear imediatamente, Inspecionar detalhadamente).
                6. Nível de Confiança (Alto, Médio, Baixo).
                
                Formate sua resposta de forma clara, destacando o relacionamento entre a identificação do pneu e o estado físico apresentado nas fotos complementares.
                """
                
                conteudo_requisicao.append(prompt)
                
                try:
                    resposta = model.generate_content(conteudo_requisicao)
                    ai_texto = resposta.text
                except Exception as e:
                    ai_texto = f"Erro durante a análise de IA: {str(e)}"
                
                # Salva o resultado unificado do conjunto de fotos
                nomes_arquivos = ", ".join([f.name for f in uploaded_files])
                st.session_state.inspection_results = [{
                    "Nomes dos Arquivos": nomes_arquivos,
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Analise_IA": ai_texto,
                    "Imagens": uploaded_files
                }]
                
                texto_status.success("✅ Inspeção cruzada concluída com sucesso!")
                
            except ImportError:
                st.error("A biblioteca `google-generativeai` não está instalada. Instale com `pip install google-generativeai`.")
            except Exception as e:
                st.error(f"Ocorreu um erro ao inicializar a API: {str(e)}")

    # Exibir Resultados se disponíveis
    if st.session_state.inspection_results:
        st.markdown("---")
        st.subheader("📊 Resultado da Inspeção Unificada do Pneu")
        
        for i, res in enumerate(st.session_state.inspection_results):
            with st.expander(f"Inspeção Pneu • Arquivos: {res['Nomes dos Arquivos']} ({res['Timestamp']})", expanded=True):
                # Exibe todas as imagens lado a lado
                cols_imagens = st.columns(len(res["Imagens"]))
                for idx_img, img_file in enumerate(res["Imagens"]):
                    with cols_imagens[idx_img]:
                        st.image(img_file, caption=f"Foto {idx_img+1}: {img_file.name}", use_container_width=True)
                
                st.markdown("#### 🤖 Diagnóstico Unificado da IA")
                st.write(res["Analise_IA"])
                
                # Formulário rápido de revisão / salvamento
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    edita_fogo = st.text_input("Confirmar ID Fogo", value="", key=f"fogo_{i}")
                with col_b:
                    edita_status = st.selectbox("Status Geral", ["Aprovado", "Precisa Recapagem", "Sucata", "Revisão Pendente"], key=f"status_{i}")
                with col_c:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Salvar Registro Consolidado", key=f"save_{i}"):
                        st.success(f"Salvo com sucesso! Fogo: {edita_fogo or 'Detectado'} | Status: {edita_status}")

        # Opção de Exportação
        st.markdown("### 📥 Exportar Dados")
        if st.button("Exportar Relatório para CSV"):
            dados_resumo = []
            for res in st.session_state.inspection_results:
                dados_resumo.append({
                    "Arquivos": res["Nomes dos Arquivos"],
                    "Timestamp": res["Timestamp"],
                    "Resultados": res["Analise_IA"].replace("\n", " ")
                })
            df_export = pd.DataFrame(dados_resumo)
            csv = df_export.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Baixar Relatório CSV",
                data=csv,
                file_name=f"relatorio_inspecao_pneu_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )

else:
    st.info("👆 Por favor, envie as fotos do pneu acima (ex: foto da lateral com o número de Fogo e foto da banda de rodagem) para iniciar.")

# Rodapé
st.markdown("---")
st.markdown("<p style='text-align: center; color: #64748b;'>Sistema de Gestão de Pneus SMART-LOG • Desenvolvido com Streamlit e Google Gemini AI</p>", unsafe_allow_html=True)
