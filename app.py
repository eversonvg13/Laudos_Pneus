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

def obter_modelo_estavel(genai):
    """Retorna um modelo homologado e ativo, ignorando versões descontinuadas (1.x e 2.x)."""
    # Lista de modelos oficiais e suportados em ordem de prioridade (família 3.x, ago/2026)
    # "gemini-flash-latest" é um alias que sempre aponta para o Flash estável mais recente.
    modelos_homologados = [
        "gemini-flash-latest",
        "gemini-3.5-flash",
        "gemini-3.6-flash",
        "gemini-3.1-flash-lite",
        "gemini-3.5-flash-lite",
    ]

    # Prefixos de modelos descontinuados/desligados — nunca usar
    prefixos_descontinuados = ("gemini-1.", "gemini-2.0", "gemini-2.5")

    try:
        modelos_disponiveis = [
            m.name.replace('models/', '')
            for m in genai.list_models()
            if 'generateContent' in m.supported_generation_methods
        ]

        # Remove qualquer modelo descontinuado que ainda apareça na listagem
        modelos_validos = [
            m for m in modelos_disponiveis
            if not m.startswith(prefixos_descontinuados)
        ]

        # 1. Tenta usar, em ordem de preferência, um dos modelos homologados
        for h in modelos_homologados:
            if h in modelos_validos:
                return h

        # 2. Caso nenhum homologado esteja disponível, pega o primeiro "flash" válido
        for m in modelos_validos:
            if 'flash' in m:
                return m

        # 3. Por fim, qualquer modelo válido restante
        if modelos_validos:
            return modelos_validos[0]

    except Exception:
        pass

    # Padrão seguro default (alias sempre atualizado)
    return "gemini-flash-latest"

# Barra Lateral
st.sidebar.title("🛞 SMART-LOG IA")
st.sidebar.markdown("### Inspetor Inteligente de Pneus")
api_key_input = st.sidebar.text_input("Chave da API Gemini", type="password", value=os.environ.get("GEMINI_API_KEY", ""))

st.sidebar.markdown("---")
st.sidebar.info("Fotos comprimidas automaticamente. Modelo selecionado dinamicamente entre as versões estáveis da família Gemini 3.x.")

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
                texto_status.text("Selecionando modelo estável...")
                
                # Seleção segura do modelo
                nome_modelo_ativo = obter_modelo_estavel(genai)
                texto_status.text(f"Conectado ao modelo: {nome_modelo_ativo}. Comprimindo lote de fotos...")
                
                model = genai.GenerativeModel(nome_modelo_ativo)
                
                # 1. Ordenação cronológica pelo nome do arquivo
                sorted_files = sorted(uploaded_files, key=lambda f: f.name)
                
                # 2. Montar requisição em lote com imagens comprimidas
                conteudo_requisicao = []
                prompt_instrucoes = f"""
                Você é um inspetor especialista em inventário de pneus de frota (SMART-LOG).
                Abaixo estão {len(sorted_files)} fotos ordenadas cronologicamente.
                
                Sua tarefa é:
                1. Analisar todas as imagens e agrupá-las por pneu individual. Cada novo pneu começa com a foto da lateral contendo o número de 'Fogo' (número de identificação pintado em giz/tinta na lateral, ex: 32813), seguida pelas fotos da banda de rodagem/sulco/danos daquele pneu até a próxima foto de 'Fogo'.
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
                    bytes_comprimidos = comprimir_imagem(f.getvalue())
                    
                    conteudo_requisicao.append(f"Arquivo: {f.name}")
                    conteudo_requisicao.append({
                        "mime_type": "image/jpeg",
                        "data": bytes_comprimidos
                    })
                
                conteudo_requisicao.append(prompt_instrucoes)
                
                texto_status.text(f"Enviando dados para a IA ({nome_modelo_ativo})...")
                resposta_ia = model.generate_content(conteudo_requisicao)
                
                st.session_state.inspection_results = [{
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Modelo_Usado": nome_modelo_ativo,
                    "Analise_IA": resposta_ia.text,
                    "Imagens": sorted_files
                }]
                
                texto_status.success(f"✅ Inspeção concluída com sucesso via {nome_modelo_ativo}!")
                
            except Exception as e:
                st.error(f"Erro no processamento: {str(e)}")

    # Exibição dos Resultados
    if st.session_state.inspection_results:
        st.markdown("---")
        st.subheader("📊 Relatório Consolidado de Inspeção")
        
        for res in st.session_state.inspection_results:
            with st.expander(f"🛞 Laudo Geral do Lote ({len(res['Imagens'])} fotos) - Modelo: {res.get('Modelo_Usado', 'gemini-flash-latest')}", expanded=True):
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
