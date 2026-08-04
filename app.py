import streamlit as st
from PIL import Image
from PIL.ExifTags import TAGS
from datetime import datetime
import re
import cv2
import numpy as np
import os

try:
    import pytesseract
    if os.path.exists('/usr/bin/tesseract'):
        pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
    elif os.path.exists('/usr/local/bin/tesseract'):
        pytesseract.pytesseract.tesseract_cmd = '/usr/local/bin/tesseract'
    OCR_DISPONIVEL = True
except ImportError:
    OCR_DISPONIVEL = False

st.set_page_config(
    page_title="Gerador de Laudos de Pneus", 
    page_icon="🛞", 
    layout="wide"
)

st.title("🛞 Gerador Automatizado de Laudos de Pneus")
st.markdown("### Motor Universal Otimizado para Stencils e Pinturas")

arquivos_fotos = st.file_uploader(
    "📁 Selecione as fotos do pátio (Fogo e Danos):", 
    type=["jpg", "jpeg", "png"], 
    accept_multiple_files=True
)

def extrair_data_hora(uploaded_file):
    """Extrai metadados EXIF da foto."""
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

def ler_numero_fogo_universal(uploaded_file):
    """Processa a imagem otimizando a leitura de números pintados (fogo)."""
    if not OCR_DISPONIVEL:
        return "Desconhecido", "⚠️ Erro: Biblioteca pytesseract não importada."

    try:
        uploaded_file.seek(0)
        file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
        img_cv = cv2.imdecode(file_bytes, 1)
        
        if img_cv is None:
            return "Desconhecido", "⚠️ Erro: Não foi possível decodificar a imagem."

        # 1. Redimensionamento padrão para estabilizar o OCR
        altura, largura = img_cv.shape[:2]
        fator = 1600 / largura if largura < 1600 else 1.0
        if fator != 1.0:
            img_cv = cv2.resize(img_cv, (int(largura * fator), int(altura * fator)))

        # 2. Conversão para escala de cinza e melhoria de contraste (CLAHE)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contraste = clahe.apply(gray)

        # 3. Executa o OCR com PSM 7 (focado em linha única de texto/código)
        texto_detectado = pytesseract.image_to_string(contraste, config='--psm 7')
        
        # Fallback se o PSM 7 vier vazio: tenta PSM 11
        if not texto_detectado.strip():
            texto_detectado = pytesseract.image_to_string(contraste, config='--psm 11')

        texto_completo = texto_detectado + " " + uploaded_file.name

        # 4. Filtragem de números do pneu
        padroes_encontrados = re.findall(r'\b(\d{3,6})\b', texto_completo)
        
        # Exclusões de especificações técnicas comuns
        exclusoes = ['3350', '3150', '850', '18', '7390', '6940', '5', '1', '385', '65', '225']
        numeros_validos = [num for num in padroes_encontrados if num not in exclusoes]
        
        fogo_encontrado = numeros_validos[0] if numeros_validos else "Desconhecido"
        
        return fogo_encontrado, f"Texto Bruto OCR: '{texto_detectado.strip()}'\nPadrões achados: {padroes_encontrados}"

    except Exception as e:
        return "Desconhecido", f"⚠️ Erro no processamento OCR: {str(e)}"

if arquivos_fotos:
    if st.button("🔄 Processar Lote Atualizado", type="primary"):
        with st.spinner("Analisando imagens e separando pneus..."):
            
            fotos_processadas = []
            for arquivo in arquivos_fotos:
                timestamp = extrair_data_hora(arquivo)
                fogo_id, texto_bruto = ler_numero_fogo_universal(arquivo)
                fotos_processadas.append({
                    "arquivo": arquivo,
                    "nome": arquivo.name,
                    "timestamp": timestamp,
                    "fogo_id": fogo_id,
                    "texto_bruto": texto_bruto
                })
            
            # Ordena cronologicamente
            fotos_ordenadas = sorted(fotos_processadas, key=lambda x: x["timestamp"])
            
            # Agrupamento inteligente por Fogo detectado
            blocos_pneus = []
            pneu_atual = None
            
            for i, item in enumerate(fotos_ordenadas):
                # Se encontrou um número válido de fogo, abre um novo bloco de pneu
                if i == 0 or item["fogo_id"] != "Desconhecido":
                    if pneu_atual is not None:
                        blocos_pneus.append(pneu_atual)
                    
                    pneu_atual = {
                        "ancora": item,
                        "fogo_numero": item["fogo_id"],
                        "danos": []
                    }
                else:
                    # Caso contrário, anexa como foto de dano do pneu atual
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
            
            # Exibição na interface
            st.markdown(f"### 📦 Total de Pneus Identificados: {len(blocos_pneus)}")
            
            for idx, bloco in enumerate(blocos_pneus, 1):
                fogo_exibicao = bloco['fogo_numero'] if bloco['fogo_numero'] != "Desconhecido" else f"Pneu #{idx} (Fogo não detectado)"
                with st.expander(f"🛞 Fogo: {fogo_exibicao} (Início: {bloco['ancora']['timestamp'].strftime('%H:%M:%S' if bloco['ancora']['timestamp'] != datetime.min else 'N/A')})", expanded=True):
                    col_ancora, col_danos = st.columns([1, 3])
                    
                    with col_ancora:
                        st.markdown("**📸 Foto Âncora / Identificação**")
                        bloco["ancora"]["arquivo"].seek(0)
                        st.image(bloco["ancora"]["arquivo"], use_column_width=True)
                        st.caption(f"ID Detectado: **{fogo_exibicao}**")
                        
                        # Caixa de depuração aberta por padrão para facilitar o diagnóstico
                        with st.expander("🔍 Ver Diagnóstico OCR", expanded=True):
                            st.text(bloco["ancora"]["texto_bruto"])
                        bloco["ancora"]["arquivo"].seek(0)
                    
                    with col_danos:
                        st.markdown(f"**🔍 Danos Vinculados ({len(blocos_pneus[idx-1]['danos'])} imagens):**")
                        danos_lista = bloco['danos']
                        if danos_lista:
                            cols_dano = st.columns(min(len(danos_lista), 4) if len(danos_lista) > 0 else 1)
                            for d_idx, dano in enumerate(danos_lista):
                                col_alvo = cols_dano[d_idx % len(cols_dano)]
                                with col_alvo:
                                    dano["arquivo"].seek(0)
                                    st.image(dano["arquivo"], width=110)
                                    st.caption(f"OCR: {dano['fogo_id']}")
                                    dano["arquivo"].seek(0)
                        else:
                            st.info("Apenas foto âncora neste bloco.")
                            
            st.success("✨ Processamento concluído com motor otimizado!")
else:
    st.info("💡 Suba as fotos para testar.")
