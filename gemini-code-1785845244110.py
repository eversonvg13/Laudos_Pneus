import streamlit as st
from PIL import Image
from PIL.ExifTags import TAGS
from datetime import datetime
import re
import cv2
import numpy as np

# Tenta carregar o motor de OCR
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
st.markdown("### Motor Universal de Leitura de Fogo (Pintado ou Gravado)")

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
    """
    Processa a imagem universalmente para encontrar o número do fogo,
    seja ele pintado de amarelo ou esculpido na borracha.
    """
    if not OCR_DISPONIVEL:
        return "Desconhecido", False

    try:
        uploaded_file.seek(0)
        file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
        img_cv = cv2.imdecode(file_bytes, 1)
        
        if img_cv is None:
            return "Desconhecido", False

        # 1. Redimensiona para otimizar a leitura
        altura, largura = img_cv.shape[:2]
        fator = 1500 / largura if largura < 1500 else 1.0
        if fator != 1.0:
            img_cv = cv2.resize(img_cv, (int(largura * fator), int(altura * fator)))

        # 2. Converte para escala de cinza
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

        # 3. Aplica limiarização adaptativa (destaca bordas, relevos e contrastes de tinta)
        # Isso faz números gravados (sombras) e pintados se destacarem do fundo preto do pneu
        binaria = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )

        # 4. Executa o OCR na imagem tratada
        texto_detectado = pytesseract.image_to_string(binaria, config='--psm 11') # PSM 11: Sparse text (encontra texto em qualquer lugar)
        
        # Adiciona também o nome do arquivo na busca (caso o inspetor renomeie ou o padrão ajude)
        texto_completo = texto_detectado + " " + uploaded_file.name

        # 5. Procura por um padrão numérico de 3 a 6 dígitos isolados (que é o padrão de fogo)
        # Ignora números longos como especificações de carga (ex: 3350, 3150 que aparecem no pneu)
        padroes_encontrados = re.findall(r'\b(\d{3,6})\b', texto_completo)
        
        # Filtragem inteligente para evitar pegar dados técnicos de carga se aparecerem no texto
        numeros_validos = [num for num in padroes_encontrados if num not in ['3350', '3150', '850', '18']]
        
        if numeros_validos:
            # Retorna o primeiro número provável encontrado como o Fogo
            return numeros_validos[0], True

    except Exception as e:
        pass

    return "Desconhecido", False

if arquivos_fotos:
    if st.button("🔄 Processar Lote (Universal)", type="primary"):
        with st.spinner("Analisando imagens e identificando os fogos..."):
            
            # 1. Extração, Ordenação e Identificação
            fotos_processadas = []
            for arquivo in arquivos_fotos:
                timestamp = extrair_data_hora(arquivo)
                fogo_id, eh_ancora = ler_numero_fogo_universal(arquivo)
                fotos_processadas.append({
                    "arquivo": arquivo,
                    "nome": arquivo.name,
                    "timestamp": timestamp,
                    "fogo_id": fogo_id,
                    "eh_ancora": eh_ancora
                })
            
            fotos_ordenadas = sorted(fotos_processadas, key=lambda x: x["timestamp"])
            
            # 2. Agrupamento por mudança de Fogo
            blocos_pneus = []
            pneu_atual = None
            
            for i, item in enumerate(fotos_ordenadas):
                # Se for a primeira foto ou se o OCR detectou um número de fogo válido
                if i == 0 or item["fogo_id"] != "Desconhecido":
                    if pneu_atual is not None:
                        blocos_pneus.append(pneu_atual)
                    
                    pneu_atual = {
                        "ancora": item,
                        "fogo_numero": item["fogo_id"],
                        "danos": []
                    }
                else:
                    # Caso contrário, acumula como foto de dano do pneu atual
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
            
            # 3. Exibição na Tela
            st.markdown(f"### 📦 Total de Pneus Identificados: {len(blocos_pneus)}")
            
            for idx, bloco in enumerate(blocos_pneus, 1):
                fogo_exibicao = bloco['fogo_numero'] if bloco['fogo_numero'] != "Desconhecido" else f"Pneu #{idx} (Requer ajuste)"
                with st.expander(f"🛞 Fogo: {fogo_exibicao} (Início: {bloco['ancora']['timestamp'].strftime('%H:%M:%S' if bloco['ancora']['timestamp'] != datetime.min else 'N/A')})", expanded=True):
                    col_ancora, col_danos = st.columns([1, 3])
                    
                    with col_ancora:
                        st.markdown("**📸 Foto Âncora (Fogo)**")
                        bloco["ancora"]["arquivo"].seek(0)
                        st.image(bloco["ancora"]["arquivo"], use_column_width=True)
                        st.caption(f"ID Detectado: **{fogo_exibicao}**")
                    
                    with col_danos:
                        st.markdown(f"**🔍 Danos Vinculados ({len(bloco['danos'])} imagens):**")
                        if bloco["danos"]:
                            cols_dano = st.columns(len(bloco['danos']))
                            for d_idx, dano in enumerate(bloco["danos"]):
                                with cols_dano[d_idx]:
                                    dano["arquivo"].seek(0)
                                    st.image(dano["arquivo"], width=120)
                                    dano["arquivo"].seek(0)
                        else:
                            st.info("Apenas foto âncora neste bloco.")
                            
            st.success("✨ Processamento concluído considerando ambos os formatos (com tinta ou gravados)!")
else:
    st.info("💡 Suba um lote misto de fotos para testar a leitura universal.")
