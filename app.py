import streamlit as st
from bs4 import BeautifulSoup
from fpdf import FPDF
from PIL import Image
import io

# --- FUNÇÃO PARA PARSAR O HTML DA PRAXIO ---
def extrair_dados_pneu(conteudo_html, numero_fogo):
    soup = BeautifulSoup(conteudo_html, 'html.parser')
    linhas = soup.find_all('tr')
    veiculo_atual = "N/A"

    for linha in linhas:
        colunas = [td.get_text(strip=True) for td in linha.find_all(['td', 'th'])]
        
        if len(colunas) >= 8:
            # Identifica o veículo no bloco visual do relatório
            if colunas[0] and colunas[0].isdigit():
                veiculo_atual = colunas[0]
            
            fogo = colunas[2]
            # Normaliza o número de fogo para comparação
            if fogo.zfill(7) == str(numero_fogo).zfill(7):
                return {
                    "veiculo": veiculo_atual,
                    "posicao": colunas[1],
                    "fogo": colunas[2],
                    "medida": colunas[3],
                    "data_retirada": colunas[4],
                    "garagem": colunas[5],
                    "km_posicao": colunas[6],
                    "km_total": colunas[7]
                }
    return None

# --- FUNÇÃO PARA GERAR O PDF NA MEMÓRIA ---
class PDFLaudo(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 10, 'LAUDO TÉCNICO DE INSPEÇÃO DE PNEU', border=False, ln=True, align='C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', align='C')

def gerar_pdf_bytes(dados, parecer, fotos_bytes):
    pdf = PDFLaudo()
    pdf.add_page()
    pdf.set_font('Helvetica', '', 10)

    # Bloco 1: Dados do Pneu (Tabela)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 8, '1. Dados Identificadores (Praxio)', ln=True)
    pdf.set_font('Helvetica', '', 10)
    
    # Grid de dados 2 colunas
    largura_col = 95
    pdf.cell(largura_col, 7, f"Número de Fogo: {dados['fogo']}", border=1)
    pdf.cell(largura_col, 7, f"Veículo: {dados['veiculo']}", border=1, ln=True)
    
    pdf.cell(largura_col, 7, f"Medida/Modelo: {dados['medida']}", border=1)
    pdf.cell(largura_col, 7, f"Posição: {dados['posicao']}", border=1, ln=True)
    
    pdf.cell(largura_col, 7, f"Data Retirada: {dados['data_retirada']}", border=1)
    pdf.cell(largura_col, 7, f"Garagem/Local: {dados['garagem']}", border=1, ln=True)
    
    pdf.cell(largura_col, 7, f"Km na Posição: {dados['km_posicao']}", border=1)
    pdf.cell(largura_col, 7, f"Km Acumulado Total: {dados['km_total']}", border=1, ln=True)
    
    pdf.ln(8)

    # Bloco 2: Parecer Técnico
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 8, '2. Parecer Técnico / Observações da Vistoria', ln=True)
    pdf.set_font('Helvetica', '', 10)
    pdf.multi_cell(0, 6, parecer if parecer else "Nenhuma observação informada.", border=1)
    
    pdf.ln(8)

    # Bloco 3: Evidências Fotográficas
    if fotos_bytes:
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(0, 8, '3. Registro Fotográfico', ln=True)
        pdf.ln(2)

        for idx, img_buffer in enumerate(fotos_bytes):
            # Garante que a imagem está em formato compatível via PIL
            image = Image.open(img_buffer)
            temp_img_path = f"temp_img_{idx}.jpg"
            image.convert("RGB").save(temp_img_path)

            # Adiciona imagem no PDF
            pdf.image(temp_img_path, w=120)
            pdf.ln(5)

    # Retorna o arquivo binário em bytes para o botão de download
    return bytes(pdf.output())


# --- INTERFACE STREAMLIT ---
st.title("📋 Gerador de Laudos Técnicos")
st.caption("SMART-LOG | Módulo de Extração Automática & Vistorias")

col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("1. Arquivos e Identificação")
    arquivo_html = st.file_uploader("Upload do Relatório Praxio (.html)", type=["html", "htm"])
    fogo_busca = st.text_input("Número de Fogo do Pneu:", placeholder="Ex: 0031712")
    
    parecer_tecnico = st.text_area(
        "Parecer Técnico / Motivo do Descarta ou Reparo:",
        placeholder="Descreva o estado do pneu, avarias encontradas (ex: perfuração na rodagem, separação de cintas)...",
        height=120
    )

with col_right:
    st.subheader("2. Fotos da Inspeção")
    fotos_upload = st.file_uploader(
        "Selecione as Imagens das Avarias", 
        type=["jpg", "jpeg", "png"], 
        accept_multiple_files=True
    )
    
    if fotos_upload:
        st.write(f"📷 **{len(fotos_upload)} foto(s) anexada(s)**")
        # Exibe miniaturas na tela
        cols_img = st.columns(min(len(fotos_upload), 3))
        for idx, img_file in enumerate(fotos_upload):
            with cols_img[idx % 3]:
                st.image(img_file, use_container_width=True)

st.divider()

# --- PROCESSAMENTO E EXTRAÇÃO ---
if st.button("🔎 Buscar Dados e Preparar Laudo", type="primary"):
    if not arquivo_html or not fogo_busca:
        st.warning("⚠️ Forneça o arquivo HTML do relatório e informe o número de Fogo.")
    else:
        conteudo = arquivo_html.getvalue().decode("utf-8", errors="ignore")
        dados_pneu = extrair_dados_pneu(conteudo, fogo_busca)

        if dados_pneu:
            st.success(f"Pneu **{fogo_busca}** localizado com sucesso!")
            
            # Exibição dos Dados Encontrados
            st.json(dados_pneu)

            # Gerar PDF em memória
            list_img_buffers = [io.BytesIO(img.getvalue()) for img in fotos_upload] if fotos_upload else []
            pdf_bytes = gerar_pdf_bytes(dados_pneu, parecer_tecnico, list_img_buffers)

            # Botão de Download do PDF
            st.download_button(
                label="📥 Baixar Laudo Técnico (PDF)",
                data=pdf_bytes,
                file_name=f"Laudo_Pneu_{fogo_busca}.pdf",
                mime="application/pdf",
                type="secondary"
            )
        else:
            st.error(f"❌ O pneu número **{fogo_busca}** não foi localizado no arquivo HTML enviado.")
