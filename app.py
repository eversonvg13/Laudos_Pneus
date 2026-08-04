import streamlit as st
import os
import pandas as pd
from datetime import datetime

# Configuração da página
st.set_page_config(
    page_title="Laudo de Pneus por IA",
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
st.sidebar.title("Laudo IA")
st.sidebar.markdown("### Inspetor Inteligente de Pneus")
st.sidebar.markdown("Desenvolvido com Google Gemini Multimodal AI")

api_key_input = st.sidebar.text_input("Chave da API Gemini (API Key)", type="password", value=os.environ.get("GEMINI_API_KEY", ""))

st.sidebar.markdown("---")
st.sidebar.info("""
**Instruções:**
1. Insira sua chave da API do Google Gemini acima.
2. Faça o upload das fotos em **pares por pneu** (Ex: Foto 1 = Lateral com Fogo, Foto 2 = Banda de Rodagem).
3. O sistema agrupará automaticamente as fotos de 2 em 2 para cada pneu!
""")

# Cabeçalho Principal
st.title("Laudo de Pneus por IA")
st.markdown("Automatize a identificação do número de **Fogo** e análise cruzada de sulcos agrupando as fotos por pneu (Pares: Lateral + Banda).")

# Verificar chave da API
api_key = api_key_input
if not api_key:
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        api_key = ""

# Uploader de arquivos
uploaded_files = st.file_uploader(
    "📁 Envie as fotos dos pneus (Envie em pares: 2 fotos por pneu)",
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
    st.markdown(f"### 📂 Total de arquivos enviados: {len(uploaded_files)} imagens")
    st.info("💡 As imagens serão agrupadas automaticamente em pares (2 fotos por pneu: a 1ª sendo a lateral com o Fogo e a 2ª a banda de rodagem).")
    
    if "inspection_results" not in st.session_state:
        st.session_state.inspection_results = []

    if st.button("🚀 Executar Inspeção por Pares de Pneus", type="primary"):
        if not api_key:
            st.error("⚠️ Por favor, insira sua chave da API Gemini na barra lateral ou configure nas Secrets.")
        else:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                
                # Modelo estável atualizado
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                results = []
                barra_progresso = st.progress(0)
                texto_status = st.empty()
                
                # Agrupar arquivos automaticamente em blocos de 2 (pares por pneu)
                pares_pneus = [uploaded_files[i:i+2] for i in range(0, len(uploaded_files), 2)]
                total_pares = len(pares_pneus)
                
                for idx, par in enumerate(pares_pneus):
                    nomes_par = " + ".join([f.name for f in par])
                    texto_status.text(f"Analisando Pneu {idx+1} de {total_pares} ({nomes_par})...")
                    
                    conteudo_requisicao = []
                    for foto in par:
                        conteudo_requisicao.append({
                            "mime_type": foto.type,
                            "data": foto.getvalue()
                        })
                    
                    prompt = f"""
                    Você é um inspetor especialista em inventário e manutenção de pneus para uma frota de logística (SMART-LOG). 
                    Estas imagens pertencem ao **mesmo pneu** (sendo a primeira foto a lateral com o número de "Fogo" e a segunda foto a banda de rodagem ou detalhes de danos).
                    O modo de análise selecionado é: {modo_analise}.
                    
                    Analise o par de imagens em conjunto e extraia os seguintes detalhes em português:
                    1. Fogo (Número de identificação do pneu visível na foto da lateral). Se não estiver visível, estime ou coloque 'Desconhecido'.
                    2. Marca / Fabricante (ex: Michelin, Bridgestone, Pirelli, Firestone, Goodyear).
                    3. Condição / Status da Profundidade de Sulco (Bom, Desgastado, Crítico / Precisa de Recapagem).
                    4. Danos / Anomalias Detectadas (ex: Cortes, Bolhas, Exposição de carcaça, Desgaste irregular, Vulcanização/Conserto, Nenhum).
                    5. Ação Recomendada (Manter em serviço, Enviar para recapagem, Sucatear imediatamente, Inspecionar detalhadamente).
                    6. Nível de Confiança (Alto, Médio, Baixo).
                    
                    Formate sua resposta de forma clara e estruturada.
                    """
                    conteudo_requisicao.append(prompt)
                    
                    try:
                        resposta = model.generate_content(conteudo_requisicao)
                        ai_texto = resposta.text
                    except Exception as e:
                        ai_texto = f"Erro durante a análise de IA: {str(e)}"
                    
                    results.append({
                        "Pneu_ID": idx + 1,
                        "Nomes_Arquivos": [f.name for f in par],
                        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Analise_IA": ai_texto,
                        "Bytes_Imagens": [f.getvalue() for f in par]
                    })
                    
                    barra_progresso.progress((idx + 1) / total_pares)
                
                st.session_state.inspection_results = results
                texto_status.success("✅ Inspeção por pares concluída com sucesso!")
                barra_progresso.empty()
                
            except Exception as e:
                st.error(f"Ocorreu um erro ao inicializar a API: {str(e)}")

    # Exibir Resultados Organizados por Pneu
    if st.session_state.inspection_results:
        st.markdown("---")
        st.subheader("📊 Resultados da Inspeção por Pneu")
        
        for i, res in enumerate(st.session_state.inspection_results):
            with st.expander(f"🛞 Pneu #{res['Pneu_ID']} • Fotos: {', '.join(res['Nomes_Arquivos'])}", expanded=(i==0)):
                # Exibe as fotos do par lado a lado de forma limpa
                cols_imgs = st.columns(len(res["Bytes_Imagens"]))
                for img_idx, img_bytes in enumerate(res["Bytes_Imagens"]):
                    with cols_imgs[img_idx]:
                        st.image(img_bytes, caption=f"Foto {img_idx+1}: {res['Nomes_Arquivos'][img_idx]}", use_container_width=True)
                
                st.markdown("#### 🤖 Diagnóstico da IA")
                st.write(res["Analise_IA"])
                
                # Formulário rápido de revisão / salvamento por pneu
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    edita_fogo = st.text_input(f"Confirmar ID Fogo #{res['Pneu_ID']}", value="", key=f"fogo_{i}")
                with col_b:
                    edita_status = st.selectbox(f"Status #{res['Pneu_ID']}", ["Aprovado", "Precisa Recapagem", "Sucata", "Revisão Pendente"], key=f"status_{i}")
                with col_c:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button(f"Salvar Pneu #{res['Pneu_ID']}", key=f"save_{i}"):
                        st.success(f"Salvo! Pneu #{res['Pneu_ID']} | Fogo: {edita_fogo or 'Detectado'} | Status: {edita_status}")

        # Opção de Exportação em Lote
        st.markdown("### 📥 Exportar Dados")
        if st.button("Exportar Relatório para CSV"):
            dados_resumo = []
            for res in st.session_state.inspection_results:
                dados_resumo.append({
                    "Pneu ID": res["Pneu_ID"],
                    "Arquivos": ", ".join(res["Nomes_Arquivos"]),
                    "Timestamp": res["Timestamp"],
                    "Resultados": res["Analise_IA"].replace("\n", " ")
                })
            df_export = pd.DataFrame(dados_resumo)
            csv = df_export.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Baixar Relatório CSV",
                data=csv,
                file_name=f"relatorio_pneus_pares_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )

else:
    st.info("👆 Por favor, envie as fotos dos pneus em pares (Ex: Foto 1 = Lateral com Fogo, Foto 2 = Banda de Rodagem).")

# Rodapé
st.markdown("---")
st.markdown("<p style='text-align: center; color: #64748b;'>Sistema de Gestão de Pneus SMART-LOG • Desenvolvido com Streamlit e Google Gemini AI</p>", unsafe_allow_html=True)
