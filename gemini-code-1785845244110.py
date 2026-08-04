import streamlit as st
from PIL import Image
from PIL.ExifTags import TAGS
from datetime import datetime
import re

# Tenta carregar o motor de OCR do Tesseract
try:
    import pytesseract
    OCR_DISPONIVEL = True
except ImportError:
    OCR_DISPONIVEL = False

st.set_page_config(
    page_title="Gerador de Laudos de Pneus", 
    page_icon="🛞", 
    layout="wide"
)

st.title("🛞 Gerador Automatizado de Laudos de Pneus")
st.markdown("### Agrupamento por Leitura Automática do Fogo (Âncora)")

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

def detectar_fogo(uploaded_file):
    """Lê o texto da imagem para identificar o número do Fogo."""
    uploaded_file.seek(0)
    image = Image.open(uploaded_file)
    
    texto_detectado = ""
    if OCR_DISPONIVEL:
        try:
            texto_detectado = pytesseract.image_to_string(image)
        except Exception:
            pass
            
    nome_arquivo = uploaded_file.name
    
    # Procura por padrões numéricos que representem o fogo (3 a 6 dígitos)
    padrao_fogo = re.search(r'(?:fogo|f[\s:\-_]*)?(\d{3,6})', texto_detectado.lower() + " " + nome_arquivo.lower())
    
    if padrao_fogo:
        return padrao_fogo.group(1), True
        
    return "Desconhecido", False

if arquivos_fotos:
    if st.button("🔍 Processar e Separar por Fogo", type="primary"):
        with st.spinner("Lendo metadados, escaneando os números de fogo e organizando o pátio..."):
            
            # 1. Extração, Ordenação Cronológica e Leitura do Fogo
            fotos_processadas = []
            for arquivo in arquivos_fotos:
                timestamp = extrair_data_hora(arquivo)
                fogo_id, eh_ancora = detectar_fogo(arquivo)
                fotos_processadas.append({
                    "arquivo": arquivo,
                    "nome": arquivo.name,
                    "timestamp": timestamp,
                    "fogo_id": fogo_id,
                    "eh_ancora": eh_ancora
                })
            
            fotos_ordenadas = sorted(fotos_processadas, key=lambda x: x["timestamp"])
            
            # 2. Agrupamento estrito baseado na mudança de Fogo
            blocos_pneus = []
            pneu_atual = None
            
            for i, item in enumerate(fotos_ordenadas):
                # Se for a primeira foto do lote ou se encontrou um novo número de fogo válido, abre um novo pneu
                if i == 0 or item["fogo_id"] != "Desconhecido":
                    if pneu_atual is not None:
                        blocos_pneus.append(pneu_atual)
                    
                    pneu_atual = {
                        "ancora": item,
                        "fogo_numero": item["fogo_id"],
                        "danos": []
                    }
                else:
                    # Caso contrário, acumula como dano do pneu que está aberto atualmente
                    if pneu_atual is not None:
                        pneu_atual["danos"].append(item)
                    else:
                        pneu_atual = {
                            "ancora": item,
                            "fogo_numero": "Indefinido",
                            "danos": []
                        }
            
            if pneu_atual is not None:
                blocos_pneus.append(pneu_atual)
            
            # 3. Exibição dos Blocos Organizados
            st.markdown(f"### 📦 Total de Pneus Identificados: {len(blocos_pneus)}")
            
            for idx, bloco in enumerate(blocos_pneus, 1):
                fogo_exibicao = bloco['fogo_numero'] if bloco['fogo_numero'] != "Desconhecido" else f"Pneu #{idx}"
                with st.expander(f"🛞 Fogo: {fogo_exibicao} (Início: {bloco['ancora']['timestamp'].strftime('%H:%M:%S' if bloco['ancora']['timestamp'] != datetime.min else 'N/A')})", expanded=True):
                    col_ancora, col_danos = st.columns([1, 3])
                    
                    with col_ancora:
                        st.markdown("**📸 Foto Âncora (Fogo)**")
                        bloco["ancora"]["arquivo"].seek(0)
                        st.image(bloco["ancora"]["arquivo"], use_column_width=True)
                        st.caption(f"ID: **{fogo_exibicao}**")
                    
                    with col_danos:
                        st.markdown(f"**🔍 Danos Vinculados ({len(bloco['danos'])} imagens):**")
                        if bloco["danos"]:
                            cols_dano = st.columns(len(bloco['danos']))
                            for d_idx, dano in enumerate(bloco["danos"]):
                                with cols_dano[d_idx]:
                                    dano["arquivo"].seek(0)
                                    st.image(dano["arquivo"], width=120)
                                    st.caption(f"Dano {d_idx+1}")
                        else:
                            st.info("Apenas foto âncora neste bloco.")
                            
            st.success("✨ Agrupamento concluído respeitando estritamente a sequência de cada Fogo!")
