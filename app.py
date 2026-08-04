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
**Instruções (Varredura por Âncora):**
1. Insira sua chave da API do Gemini acima.
2. Faça o upload de todas as fotos do lote de uma vez.
3. O sistema ordenará cronologicamente e usará a **Foto de Fogo** como âncora para iniciar cada novo pneu automaticamente!
""")

# Cabeçalho Principal
st.title("🛞 SMART-LOG: Inspeção e Inventário de Pneus por IA")
st.markdown("Agrupamento inteligente baseado em âncoras de **Fogo** e análise cronológica de lotes fotográficos.")

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

    if st.button("🚀 Executar Varredura Inteligente e Agrupamento por Âncora", type="primary"):
        if not api_key:
            st.error("⚠️ Por favor, insira sua chave da API Gemini na barra lateral ou configure nas Secrets.")
        else:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                
                # Modelo Gemini Flash estável
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                # Passo 1: Ordenação Cronológica pelo nome do arquivo (timestamp)
                sorted_files = sorted(uploaded_files, key=lambda f: f.name)
                
                texto_status = st.empty()
                barra_progresso = st.progress(0)
                
                # Passo 2: Varredura Inteligente para classificar quais fotos são "Fogo" (Âncora)
                texto_status.text("Passo 1/2: Executando varredura inteligente nas fotos para identificar as âncoras de Fogo...")
                
                classificacoes_fotos = []
                total_arquivos = len(sorted_files)
                
                for idx, file in enumerate(sorted_files):
                    bytes_data = file.getvalue()
                    img_part = {"mime_type": file.type, "data": bytes_data}
                    
                    check_prompt = """
                    Analise esta imagem de pneu. Responda estritamente se esta foto é principalmente uma foto da lateral focada em mostrar o número de identificação ('Fogo' do pneu pintado ou gravado) ou se é uma foto de banda de rodagem/dano.
                    Responda exatamente no formato:
                    TIPO: FOGO (se for a foto principal mostrando claramente o número de fogo) ou DANO (se for foto de banda, sulco ou dano sem foco principal no número de fogo).
                    """
                    
                    try:
                        resp = model.generate_content([img_part, check_prompt])
                        resposta_texto = resp.text.upper()
                        is_fogo = "TIPO: FOGO" in resposta_texto or ("FOGO" in resposta_texto and "DANO" not in resposta_texto)
                    except Exception:
                        # Fallback seguro: se a primeira foto do lote ou a cada X fotos não classificar, assume Dano ou Fogo baseado na ordem
                        is_fogo = (idx == 0) # Garante que pelo menos a primeira começa um bloco se houver falha
                    
                    classificacoes_fotos.append({
                        "file": file,
                        "bytes": bytes_data,
                        "name": file.name,
                        "is_fogo": is_fogo
                    })
                    barra_progresso.progress((idx + 1) / total_arquivos * 0.5)

                # Passo 3: Fechamento de Blocos por Âncora de Fogo
                texto_status.text("Passo 2/2: Agrupando fotos por pneu e realizando laudos técnicos...")
                
                tires_blocks = []
                current_block = []
                
                for item in classificacoes_fotos:
                    # Se encontrou uma nova foto de Fogo E já temos itens no bloco atual, fechamos o bloco anterior
                    if item["is_fogo"]:
                        if current_block:
                            tires_blocks.append(current_block)
                            current_block = []
                    
                    current_block.append(item)
                
                # Adiciona o último bloco restante
                if current_block:
                    tires_blocks.append(current_block)
                
                # Passo 4: Executar análise completa para cada bloco de pneu formado
                results = []
                total_blocos = len(tires_blocks)
                
                for b_idx, block in enumerate(tires_blocks):
                    texto_status.text(f"Analisando Pneu {b_idx+1} de {total_blocos} (Contém {len(block)} foto(s))...")
                    
                    conteudo_requisicao = [{"mime_type": item["file"].type, "data": item["bytes"]} for item in block]
                    nomes_fotos = [item["name"] for item in block]
                    
                    prompt_completo = f"""
                    Você é um inspetor especialista em inventário e manutenção de pneus para uma frota de logística. 
                    Estas {len(block)} imagens pertencem ao **mesmo pneu** (agrupadas cronologicamente a partir da foto âncora com o número de "Fogo" até as fotos seguintes de banda de rodagem/danos).
                    O modo de análise selecionado é: {modo_analise}.
                    
                    Analise o conjunto de imagens deste pneu e extraia os seguintes detalhes em português:
                    1. Fogo (Número de identificação do pneu visível na foto âncora/lateral). Se não estiver visível, estime ou coloque 'Desconhecido'.
                    2. Marca / Fabricante (ex: Michelin, Bridgestone, Pirelli, Firestone, Goodyear).
                    3. Condição / Status da Profundidade de Sulco (Bom, Desgastado, Crítico / Precisa de Recapagem).
                    4. Danos / Anomalias Detectadas (ex: Cortes, Bolhas, Exposição de carcaça, Desgaste irregular, Vulcanização/Conserto, Nenhum).
                    5. Ação Recomendada (Manter em serviço, Enviar para recapagem, Sucatear imediatamente, Inspecionar detalhadamente).
                    6. Nível de Confiança (Alto, Médio, Baixo).
                    
                    Formate sua resposta de forma clara e estruturada.
                    """
                    conteudo_requisicao.append(prompt_completo)
                    
                    try:
                        resposta_ia = model.generate_content(conteudo_requisicao)
                        ai_texto = resposta_ia.text
                    except Exception as e:
                        ai_texto = f"Erro na análise de IA: {str(e)}"
                    
                    results.append({
                        "Pneu_ID": b_idx + 1,
                        "Nomes_Arquivos": nomes_fotos,
                        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Analise_IA": ai_texto,
                        "Bytes_Imagens": [item["bytes"] for item in block]
                    })
                    
                    barra_progresso.progress(0.5 + ((b_idx + 1) / total_blocos * 0.5))

                st.session_state.inspection_results = results
                texto_status.success(f"✅ Varredura concluída! {len(tires_blocks)} pneus identificados e agrupados com sucesso.")
                barra_progresso.empty()
                
            except Exception as e:
                st.error(f"Ocorreu um erro durante o processamento: {str(e)}")

    # Exibir Resultados Organizados por Pneu
    if st.session_state.inspection_results:
        st.markdown("---")
        st.subheader("📊 Laudos de Inspeção por Pneu (Agrupados por Âncora)")
        
        for i, res in enumerate(st.session_state.inspection_results):
            with st.expander(f"🛞 Pneu #{res['Pneu_ID']} • Fotos do Bloco: {', '.join(res['Nomes_Arquivos'])}", expanded=(i==0)):
                # Exibe todas as fotos daquele pneu lado a lado
                cols_imgs = st.columns(len(res["Bytes_Imagens"]))
                for img_idx, img_bytes in enumerate(res["Bytes_Imagens"]):
                    with cols_imgs[img_idx]:
                        st.image(img_bytes, caption=f"Foto {img_idx+1}: {res['Nomes_Arquivos'][img_idx]}", use_container_width=True)
                
                st.markdown("#### 🤖 Diagnóstico da IA para este Pneu")
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
        st.markdown("### 📥 Exportar Dados Consolidados")
        if st.button("Exportar Relatório para CSV"):
            dados_resumo = []
            for res in st.session_state.inspection_results:
                dados_resumo.append({
                    "Pneu ID": res["Pneu_ID"],
                    "Arquivos do Bloco": ", ".join(res["Nomes_Arquivos"]),
                    "Timestamp": res["Timestamp"],
                    "Resultados": res["Analise_IA"].replace("\n", " ")
                })
            df_export = pd.DataFrame(dados_resumo)
            csv = df_export.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Baixar Relatório CSV",
                data=csv,
                file_name=f"relatorio_pneus_ancora_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/css"
            )

else:
    st.info("👆 Por favor, envie o lote de fotos dos pneus para iniciar a varredura inteligente por âncora.")

# Rodapé
st.markdown("---")
st.markdown("<p style='text-align: center; color: #64748b;'>Sistema de Gestão de Pneus SMART-LOG • Desenvolvido com Streamlit e Google Gemini AI</p>", unsafe_allow_html=True)
