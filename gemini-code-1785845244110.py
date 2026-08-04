import streamlit as st
from PIL import Image
from PIL.ExifTags import TAGS
from datetime import datetime

# Configuração da página
st.set_page_config(
    page_title="Gerador de Laudos de Pneus", 
    page_icon="🛞", 
    layout="wide"
)

st.title("🛞 Gerador Automatizado de Laudos de Pneus")
st.markdown("### Motor de Leitura de Metadados (EXIF)")
st.write("Arraste as fotos do pátio abaixo. O sistema vai extrair a hora, minuto e segundo exatos da captura de cada imagem diretamente do arquivo.")

st.markdown("---")

# Área de Upload de Múltiplas Fotos
arquivos_fotos = st.file_uploader(
    "📁 Selecione ou arraste as fotos do pátio (Fogo e Danos):", 
    type=["jpg", "jpeg", "png"], 
    accept_multiple_files=True
)

def extrair_data_hora(uploaded_file):
    """Extrai a data e hora real do EXIF da foto."""
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
    # Retorna uma data mínima se a foto não tiver EXIF (ex: imagem editada ou tirada de print)
    return datetime.min

if arquivos_fotos:
    st.success(f"✨ **{len(arquivos_fotos)} arquivos carregados com sucesso!**")
    
    if st.button("⏱️ Ler Horários Reais e Organizar Lote", type="primary"):
        with st.spinner("Extraindo metadados EXIF e ordenando cronologicamente..."):
            
            fotos_processadas = []
            for arquivo in arquivos_fotos:
                timestamp = extrair_data_hora(arquivo)
                fotos_processadas.append({
                    "arquivo": arquivo,
                    "nome": arquivo.name,
                    "timestamp": timestamp
                })
            
            # Ordena a lista estritamente pela data/hora (da mais antiga para a mais recente)
            fotos_ordenadas = sorted(fotos_processadas, key=lambda x: x["timestamp"])
            
            st.markdown("### 📋 Linha do Tempo Detectada no Lote")
            st.write("Veja como as fotos foram capturadas em sequência no seu pátio:")
            
            # Exibe a tabela visual com os horários reais extraídos
            for i, item in enumerate(fotos_ordenadas, 1):
                col_img, col_info = st.columns([1, 4])
                
                with col_img:
                    item["arquivo"].seek(0)
                    st.image(item["arquivo"], width=100)
                
                with col_info:
                    st.markdown(f"**Foto #{i}:** `{item['nome']}`")
                    if item["timestamp"] != datetime.min:
                        data_formatada = item["timestamp"].strftime('%d/%m/%Y às %H:%M:%S')
                        st.success(f"🕒 Capturado em: **{data_formatada}**")
                    else:
                        st.warning("⚠️ Metadado de horário não encontrado (EXIF ausente).")
                
                st.markdown("---")
            
            st.info("💡 **Próximo passo:** Agora que o sistema já lê e ordena perfeitamente a linha do tempo dos seus cliques, podemos programar a lógica automática de agrupamento (Âncora + Danos) para fechar os laudos de cada pneu!")
else:
    st.info("💡 Faça o upload de algumas fotos reais tiradas no celular para ver o sistema lendo os horários na prática.")
