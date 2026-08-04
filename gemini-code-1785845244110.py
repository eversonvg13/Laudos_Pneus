import streamlit as st
from PIL import Image
from PIL.ExifTags import TAGS
from datetime import datetime

st.set_page_config(
    page_title="Gerador de Laudos de Pneus", 
    page_icon="🛞", 
    layout="wide"
)

st.title("🛞 Gerador Automatizado de Laudos de Pneus")
st.markdown("### Agrupamento Inteligente por Intervalo de Tempo (Pátio)")

arquivos_fotos = st.file_uploader(
    "📁 Selecione as fotos do pátio (Fogo e Danos):", 
    type=["jpg", "jpeg", "png"], 
    accept_multiple_files=True
)

def extrair_data_hora(uploaded_file):
    try:
        uploaded_file.seek(0)
        image = Image.open(uploaded_file)
        exif_data = image._getexif()
        if exif_data:
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag == 'DateTimeOriginal':
                    return datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
    except Exception:
        pass
    return datetime.min

if arquivos_fotos:
    if st.button("🔄 Processar Lote por Intervalo de Tempo", type="primary"):
        with st.spinner("Analisando os segundos entre os cliques..."):
            
            # 1. Extração e Ordenação Cronológica
            fotos_processadas = []
            for arquivo in arquivos_fotos:
                timestamp = extrair_data_hora(arquivo)
                fotos_processadas.append({
                    "arquivo": arquivo,
                    "nome": arquivo.name,
                    "timestamp": timestamp
                })
            
            fotos_ordenadas = sorted(fotos_processadas, key=lambda x: x["timestamp"])
            
            # 2. Agrupamento por Gap de Tempo (Ex: pausa > 45 segundos indica troca de pneu)
            blocos_pneus = []
            pneu_atual = {"ancora": None, "danos": []}
            
            ultimo_tempo = None
            LIMITE_SEGUNDOS = 45 # Pausa maior que 45s separa um pneu do outro
            
            for i, item in enumerate(fotos_ordenadas):
                tempo_atual = item["timestamp"]
                
                # Se for a primeira foto do lote
                if i == 0:
                    pneu_atual["ancora"] = item
                    ultimo_tempo = tempo_atual
                    continue
                
                # Calcula a diferença de tempo em relação à foto anterior
                if tempo_atual != datetime.min and ultimo_tempo != datetime.min:
                    diferenca_segundos = (tempo_atual - ultimo_tempo).total_seconds()
                else:
                    diferenca_segundos = 0
                
                # Se passou muito tempo, fecha o pneu anterior e abre um novo (a foto atual vira a âncora do novo pneu)
                if diferenca_segundos > LIMITE_SEGUNDOS:
                    blocos_pneus.append(pneu_atual)
                    pneu_atual = {"ancora": item, "danos": []}
                else:
                    # Continua no mesmo pneu (foto de dano)
                    pneu_atual["danos"].append(item)
                
                ultimo_tempo = tempo_atual if tempo_atual != datetime.min else ultimo_tempo
            
            if pneu_atual["ancora"]:
                blocos_pneus.append(pneu_atual)
            
            # 3. Exibição dos Blocos Organizados
            st.markdown(f"### 📦 Total de Pneus Identificados: {len(blocos_pneus)}")
            
            for idx, bloco in enumerate(blocos_pneus, 1):
                with st.expander(f"🛞 Pneu #{idx} (Início: {bloco['ancora']['timestamp'].strftime('%H:%M:%S' if bloco['ancora']['timestamp'] != datetime.min else 'Desconhecido')})", expanded=True):
                    col_ancora, col_danos = st.columns([1, 3])
                    
                    with col_ancora:
                        st.markdown("**📸 Foto Âncora (Fogo)**")
                        bloco["ancora"]["arquivo"].seek(0)
                        st.image(bloco["ancora"]["arquivo"], use_column_width=True)
                        st.caption(f"`{bloco['ancora']['nome']}`")
                    
                    with col_danos:
                        st.markdown(f"**🔍 Danos Registrados ({len(bloco['danos'])} imagens):**")
                        if bloco["danos"]:
                            cols_dano = st.columns(len(bloco['danos']) if len(bloco['danos']) > 0 else 1)
                            for d_idx, dano in enumerate(bloco["danos"]):
                                with cols_dano[d_idx] if isinstance(cols_dano, list) else st:
                                    dano["arquivo"].seek(0)
                                    st.image(dano["arquivo"], width=120)
                                    st.caption(f"Dano {d_idx+1}")
                        else:
                            st.info("Apenas foto âncora neste bloco.")
                            
            st.success("✨ Lote agrupado com base na cadência real de inspeção!")
else:
    st.info("💡 Suba as fotos para testar o agrupamento por intervalo de tempo.")
