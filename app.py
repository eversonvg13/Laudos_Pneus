import streamlit as st
import os
import io
import pandas as pd
from datetime import datetime
from PIL import Image

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
    .stAlert { border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

def comprimir_imagem(file_bytes, max_dim=1024, qualidade=80):
    """Reduz o tamanho e peso da imagem para caber no payload da API."""
    img = Image.open(io.BytesIO(file_bytes))
    img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
        
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=qualidade, optimize=True)
    return buffer.getvalue()

# Barra Lateral
st.sidebar.title("🛞 SMART-LOG IA")
st.sidebar.markdown("### Inspetor Inteligente de Pneus")
api_key_input = st.sidebar.text_input("Chave da API Gemini", type="password", value=os.environ.get("GEMINI_API_KEY", ""))

st.sidebar.markdown("---")
st.sidebar.info("As imagens serão comprimidas automaticamente antes de serem enviadas para otimizar o consumo da API.")

# Cabeçalho Principal
st.title("🛞 SMART-LOG: Inspeção de Pneus por IA")
st.markdown("Agrupamento por âncoras de **Fogo** com compressão de imagens em tempo real.")

# Obter Chave da API
api_key = api_key_input or st.secrets.get("GEMINI_API_KEY", "")

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
            st.error("⚠️ Por favor, insira sua chave da API Gemini na barra lateral.")
        else:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                
                texto_status = st.empty()
                texto_status.text("Comprimindo imagens e preparando lote...")
                
                # Instanciação do modelo estável padrão
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                # 1. Ordenação cronológica pelo nome do arquivo
                sorted_files = sorted(uploaded_files, key=lambda f: f.name)
                
                # 2. Prepara o lote comprimido para envio em chamada única
                conteudo_requisicao = []
                prompt_instrucoes = f"""
                Você é um inspetor especialista em inventário de pneus de frota (SMART-LOG).
                Abaixo estão {len(sorted_files)} fotos ordenadas cronologicamente.
                
                Sua tarefa é:
                1. Analisar todas as imagens e agrupá-las por pneu individual. Cada novo pneu começa com a foto da lateral contendo o número de 'Fogo' (número de identificação pintado em giz/tinta na lateral), seguida pelas fotos da banda de rodagem/sulco/danos daquele pneu até a próxima foto de 'Fogo'.
                2. Para cada pneu agrupado, extraia:
                   - Número do Fogo
                   - Marca/Fabricante
                   - Condição do Sulco
                   - Danos/Anomalias Detectadas
                   - Ação Recomendada
                   - Confiança da Leitura
                
                Modo de análise solicitado: {modo_analise}.
                Organize a resposta claramente separada por Pneu (ex: PNEU 1, PNEU 2...).
                """
                
                for f in sorted_files:
                    # Compressão leve em memória para garantir payload < 5MB total
                    bytes_comprimidos = comprimir_imagem(f.getvalue())
                    
                    conteudo_requisicao.append(f"Arquivo: {f.name}")
                    conteudo_requisicao.append({
                        "mime_type": "image/jpeg",
                        "data": bytes_comprimidos
                    })
                
                conteudo_requisicao.append(prompt_instrucoes)
                
                texto_status.text("Enviando lote comprimido para a IA...")
                resposta_ia = model.generate_content(conteudo_requisicao)
                
                st.session_state.inspection_results = [{
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Analise_IA": resposta_ia.text,
                    "Imagens": sorted_files
                }]
                
                texto_status.success("✅ Inspeção concluída com sucesso!")
                
            except Exception as e:
                st.error(f"Erro no processamento: {str(e)}")

    # Exibição dos Resultados
    if st.session_state.inspection_results:
        st.markdown("---")
        st.subheader("📊 Relatório Consolidado de Inspeção")
        
        for res in st.session_state.inspection_results:
            with st.expander(f"🛞 Laudo Geral do Lote ({len(res['Imagens'])} fotos analisadas)", expanded=True):
                st.markdown("##### Miniaturas Enviadas:")
                cols = st.columns(min(len(res["Imagens"]), 6))
                for idx, img_file in enumerate(res["Imagens"]):
                    with cols[idx % 6]:
                        st.image(img_file, caption=img_file.name, use_container_width=True)
                
                st.markdown("---")
                st.markdown("#### 🤖 Laudo da IA")
                st.write(res["Analise_IA"])

else:
    st.info("👆 Faça o upload das fotos para começar.")
