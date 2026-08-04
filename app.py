import streamlit as st
import os
import io
import re
import json
import unicodedata
from datetime import datetime

import pandas as pd
from PIL import Image
from bs4 import BeautifulSoup

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)

# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="SMART-LOG - Inspetor de Pneus por IA",
    page_icon="🛞",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main { background-color: #f8fafc; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; background-color: #2563eb; color: white; }
    .stButton>button:hover { background-color: #1d4ed8; color: white; }
    .stAlert { border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

# Campos fixos do laudo, na ordem exigida pelo usuário
CAMPOS_FIXOS = ["FOGO", "POS", "VEICULO", "MEDIDA", "RETIRADA", "LOCAL", "KM/POS", "KM TOTAL"]

# ==============================================================================
# PARSER DO RELATÓRIO HTML (formato RDprint - posições fixas por pixel)
# ==============================================================================

# Mapa de posição (left em px) -> nome da coluna, calibrado no layout
# "Relatório de Troca de Pneus - Modelo 4"
COLUNAS_REFERENCIA = [
    (0, "VEICULO"), (45, "POS"), (68, "FOGO"), (113, "MARCA"), (232, "MEDIDA"),
    (350, "E"), (362, "RE"), (379, "CO"), (396, "V"), (407, "COLOCADO"),
    (469, "RETIRADA"), (531, "DIAS"), (571, "MOTIVO"), (661, "LOCAL"),
    (695, "KM/POS"), (751, "VIDA1"), (814, "RECAP1"), (876, "RECAP2"),
    (938, "RECAP3"), (1000, "KM TOTAL"), (1085, "RECAPADOR_SERVICO_VALOR"),
]
TOLERANCIA_PX = 10


def _left_para_coluna(left_px):
    melhor = min(COLUNAS_REFERENCIA, key=lambda c: abs(c[0] - left_px))
    if abs(melhor[0] - left_px) <= TOLERANCIA_PX:
        return melhor[1]
    return None


def parse_relatorio_html(file_bytes):
    """
    Lê o relatório HTML (gerado pelo RDprint) e extrai uma linha por pneu,
    reconstruindo as colunas a partir da posição (left) de cada <div>.
    Cada página do relatório é processada separadamente, pois o eixo 'top'
    se repete a cada página.
    """
    soup = BeautifulSoup(file_bytes, "html.parser")
    paginas = soup.find_all("div", class_="pagina")

    registros = []
    for pagina in paginas:
        linhas = {}
        for div in pagina.find_all("div", recursive=False):
            style = div.get("style", "")
            m_top = re.search(r"top:(-?\d+)px", style)
            m_left = re.search(r"left:(-?\d+)px", style)
            if not m_top or not m_left:
                continue
            top = int(m_top.group(1))
            left = int(m_left.group(1))
            texto = div.get_text()
            linhas.setdefault(top, []).append((left, texto))

        for top, campos in linhas.items():
            # Linhas de dados de pneu têm ~20 campos; cabeçalhos/subtotais têm menos.
            if len(campos) < 15:
                continue
            campos.sort(key=lambda c: c[0])
            registro = {}
            for left, texto in campos:
                coluna = _left_para_coluna(left)
                if coluna and coluna not in registro:
                    registro[coluna] = texto.strip()

            veiculo = registro.get("VEICULO", "")
            fogo = registro.get("FOGO", "")
            # Só aceita linhas reais de pneu (veículo e fogo são códigos numéricos);
            # descarta linhas de subtotal ("Total do local =>", "DD - DIANTEIRO...", etc.)
            if veiculo.isdigit() and fogo.isdigit():
                registros.append({c: registro.get(c, "") for c in CAMPOS_FIXOS})

    df = pd.DataFrame(registros, columns=CAMPOS_FIXOS)
    if df.empty:
        return df

    # Em caso de um mesmo Fogo aparecer mais de uma vez (trocas em datas diferentes),
    # mantém o registro cuja data de RETIRADA seja a mais recente — comparando a data
    # de verdade, não a ordem em que a linha aparece no arquivo (o relatório não vem
    # necessariamente ordenado cronologicamente).
    df["_retirada_dt"] = pd.to_datetime(df["RETIRADA"], format="%d/%m/%Y", errors="coerce")
    df = df.sort_values("_retirada_dt", ascending=False, na_position="last")
    df = df.drop_duplicates(subset="FOGO", keep="first")
    df = df.drop(columns="_retirada_dt").sort_values("FOGO").reset_index(drop=True)
    return df


# ==============================================================================
# UTILITÁRIOS DE IMAGEM E MODELO GEMINI
# ==============================================================================

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
    modelos_homologados = [
        "gemini-flash-latest",
        "gemini-3.5-flash",
        "gemini-3.6-flash",
        "gemini-3.1-flash-lite",
        "gemini-3.5-flash-lite",
    ]
    prefixos_descontinuados = ("gemini-1.", "gemini-2.0", "gemini-2.5")

    try:
        modelos_disponiveis = [
            m.name.replace('models/', '')
            for m in genai.list_models()
            if 'generateContent' in m.supported_generation_methods
        ]
        modelos_validos = [m for m in modelos_disponiveis if not m.startswith(prefixos_descontinuados)]

        for h in modelos_homologados:
            if h in modelos_validos:
                return h
        for m in modelos_validos:
            if 'flash' in m:
                return m
        if modelos_validos:
            return modelos_validos[0]
    except Exception:
        pass

    return "gemini-flash-latest"


def buscar_dados_relatorio(fogo_lido, df):
    """
    Busca a linha da tabela do relatório correspondente ao Fogo lido na foto.
    Compara normalizando zeros à esquerda (ex: '31712' == '0031712'),
    já que a IA pode ler o número sem os zeros de preenchimento.
    Retorna um dict com os campos fixos, ou None se não encontrar.
    """
    if df is None or df.empty or not fogo_lido:
        return None

    fogo_lido = str(fogo_lido).strip()
    fogo_lido_norm = fogo_lido.lstrip("0") or "0"

    fogos_tabela = df["FOGO"].astype(str).str.strip()

    # 1. Tenta correspondência exata
    match = df[fogos_tabela == fogo_lido]
    if match.empty:
        # 2. Tenta correspondência ignorando zeros à esquerda
        match = df[fogos_tabela.str.lstrip("0").replace("", "0") == fogo_lido_norm]

    if match.empty:
        return None
    return match.iloc[0].to_dict()


def extrair_json_da_resposta(texto):
    """Extrai o array JSON da resposta da IA, mesmo se vier com texto/markdown ao redor."""
    texto_limpo = texto.strip()
    texto_limpo = re.sub(r"^```json", "", texto_limpo.strip())
    texto_limpo = re.sub(r"^```", "", texto_limpo.strip())
    texto_limpo = re.sub(r"```$", "", texto_limpo.strip())

    inicio = texto_limpo.find("[")
    fim = texto_limpo.rfind("]")
    if inicio == -1 or fim == -1:
        raise ValueError("Nenhum array JSON encontrado na resposta da IA.")

    return json.loads(texto_limpo[inicio:fim + 1])


# ==============================================================================
# GERAÇÃO DO LAUDO EM PDF
# ==============================================================================

def gerar_pdf_laudo(pneus, timestamp_str):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm
    )

    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle("TituloLaudo", parent=styles["Title"], fontSize=16)
    subtitulo_style = ParagraphStyle("SubtituloLaudo", parent=styles["Normal"], fontSize=9, textColor=colors.grey)
    secao_style = ParagraphStyle("SecaoPneu", parent=styles["Heading2"], fontSize=13, spaceBefore=6)
    label_style = ParagraphStyle("Label", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#334155"))
    alerta_style = ParagraphStyle("Alerta", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#b91c1c"))

    story = []
    story.append(Paragraph("🛞 SMART-LOG — Laudo Técnico de Inspeção de Pneus", titulo_style))
    story.append(Paragraph(f"Gerado em: {timestamp_str}  |  Total de pneus no laudo: {len(pneus)}", subtitulo_style))
    story.append(Spacer(1, 0.6 * cm))

    for i, pneu in enumerate(pneus, start=1):
        if i > 1:
            story.append(Spacer(1, 0.4 * cm))

        fogo = pneu.get("fogo", "N/A")
        story.append(Paragraph(f"PNEU {i} — FOGO {fogo}", secao_style))

        if pneu.get("fogo_localizado_na_planilha") is False:
            story.append(Paragraph(
                "⚠ Este número de Fogo foi identificado na foto, mas NÃO foi encontrado no relatório enviado. "
                "Dados fixos abaixo podem estar incompletos.",
                alerta_style
            ))

        dados_fixos = [
            ["FOGO", pneu.get("fogo", "")],
            ["POS", pneu.get("pos", "")],
            ["VEICULO", pneu.get("veiculo", "")],
            ["MEDIDA", pneu.get("medida", "")],
            ["RETIRADA", pneu.get("retirada", "")],
            ["LOCAL", pneu.get("local", "")],
            ["KM/POS", pneu.get("km_pos", "")],
            ["KM TOTAL", pneu.get("km_total", "")],
        ]
        tabela_fixa = Table(dados_fixos, colWidths=[3.5 * cm, 13.5 * cm])
        tabela_fixa.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eff6ff")),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1e3a8a")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(tabela_fixa)
        story.append(Spacer(1, 0.25 * cm))

        analise = [
            ["Marca/Fabricante", pneu.get("marca", "")],
            ["Condição do Sulco", pneu.get("sulco", "")],
            ["Danos/Anomalias Detectadas", pneu.get("danos", "")],
            ["Ação Recomendada", pneu.get("acao_recomendada", "")],
            ["Confiança da Leitura", pneu.get("confianca", "")],
        ]
        tabela_analise = Table(
            [[Paragraph(f"<b>{campo}</b>", label_style), Paragraph(str(valor), styles["Normal"])] for campo, valor in analise],
            colWidths=[4.5 * cm, 12.5 * cm]
        )
        tabela_analise.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(tabela_analise)

        if i < len(pneus) and i % 3 == 0:
            story.append(PageBreak())

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def gerar_pdf_fallback(texto_bruto, timestamp_str):
    """Gera um PDF simples com o texto cru da IA, usado quando o JSON não pôde ser interpretado."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                             leftMargin=1.5 * cm, rightMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("🛞 SMART-LOG — Laudo Técnico de Inspeção de Pneus", styles["Title"]),
        Paragraph(f"Gerado em: {timestamp_str}", styles["Normal"]),
        Spacer(1, 0.5 * cm),
    ]
    for linha in texto_bruto.split("\n"):
        story.append(Paragraph(linha.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") or "&nbsp;", styles["Normal"]))
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# ==============================================================================
# BARRA LATERAL
# ==============================================================================
st.sidebar.title("🛞 SMART-LOG IA")
st.sidebar.markdown("### Inspetor Inteligente de Pneus")
api_key_input = st.sidebar.text_input("Chave da API Gemini", type="password", value=os.environ.get("GEMINI_API_KEY", ""))
st.sidebar.markdown("---")
st.sidebar.info("Fotos comprimidas automaticamente. Modelo selecionado dinamicamente entre as versões estáveis da família Gemini 3.x.")

api_key = api_key_input or st.secrets.get("GEMINI_API_KEY", "")

# ==============================================================================
# CABEÇALHO
# ==============================================================================
st.title("🛞 SMART-LOG: Inspeção de Pneus por IA")
st.markdown("Fluxo: **1) Envie o relatório** → **2) Envie as fotos** → **3) Gere o laudo em PDF**.")

# ==============================================================================
# PASSO 1 — UPLOAD DO RELATÓRIO
# ==============================================================================
st.markdown("---")
st.subheader("1️⃣ Relatório de Troca de Pneus (HTML)")

relatorio_file = st.file_uploader(
    "📄 Envie o relatório exportado em HTML (Relatório de Troca de Pneus - Modelo 4)",
    type=["html", "htm"],
    accept_multiple_files=False
)

if relatorio_file is not None:
    if st.session_state.get("relatorio_nome_processado") != relatorio_file.name:
        with st.spinner("Extraindo dados do relatório..."):
            try:
                df_relatorio = parse_relatorio_html(relatorio_file.getvalue())
                st.session_state.dados_relatorio = df_relatorio
                st.session_state.relatorio_nome_processado = relatorio_file.name
            except Exception as e:
                st.error(f"Não foi possível processar o relatório: {e}")

if "dados_relatorio" not in st.session_state:
    st.session_state.dados_relatorio = pd.DataFrame(columns=CAMPOS_FIXOS)

if not st.session_state.dados_relatorio.empty:
    st.success(f"✅ {len(st.session_state.dados_relatorio)} pneus extraídos do relatório.")
    with st.expander("📋 Ver / editar dados extraídos do relatório", expanded=False):
        st.caption("Pode corrigir manualmente qualquer campo antes de gerar o laudo.")
        st.session_state.dados_relatorio = st.data_editor(
            st.session_state.dados_relatorio,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_dados_relatorio",
        )
else:
    st.info("Nenhum relatório carregado ainda — envie o HTML acima ou preencha manualmente:")
    st.session_state.dados_relatorio = st.data_editor(
        st.session_state.dados_relatorio,
        num_rows="dynamic",
        use_container_width=True,
        key="editor_dados_relatorio_manual",
    )

# ==============================================================================
# PASSO 2 — UPLOAD DAS FOTOS
# ==============================================================================
st.markdown("---")
st.subheader("2️⃣ Fotos dos Pneus")

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

# ==============================================================================
# PASSO 3 — EXECUÇÃO E LAUDO
# ==============================================================================
if uploaded_files:
    st.markdown("---")
    st.subheader("3️⃣ Executar Análise e Gerar Laudo")
    st.markdown(f"📂 Lote carregado: **{len(uploaded_files)} imagens**")

    if "inspection_results" not in st.session_state:
        st.session_state.inspection_results = []

    if st.button("🚀 Executar Varredura, Cruzar Dados e Gerar Laudo", type="primary"):
        if not api_key:
            st.error("⚠️ Por favor, insira sua chave da API Gemini na barra lateral.")
        else:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)

                texto_status = st.empty()
                texto_status.text("Selecionando modelo estável...")

                nome_modelo_ativo = obter_modelo_estavel(genai)
                texto_status.text(f"Conectado ao modelo: {nome_modelo_ativo}. Comprimindo lote de fotos...")

                model = genai.GenerativeModel(nome_modelo_ativo)

                sorted_files = sorted(uploaded_files, key=lambda f: f.name)

                prompt_instrucoes = f"""
                Você é um inspetor especialista em inventário de pneus de frota (SMART-LOG).
                Abaixo estão {len(sorted_files)} fotos ordenadas cronologicamente.

                Sua tarefa:
                1. Analise todas as imagens e agrupe-as por pneu individual. Cada novo pneu começa com a
                   foto da lateral contendo o número de 'Fogo' (identificação pintada em giz/tinta, ex: 32813),
                   seguida das fotos de banda de rodagem/sulco/danos daquele pneu até a próxima foto de 'Fogo'.
                2. Para cada pneu, leia o número de Fogo exatamente como aparece na foto (todos os dígitos,
                   incluindo zeros à esquerda se estiverem visíveis).
                3. Modo de análise solicitado: {modo_analise}.

                Responda SOMENTE com um array JSON válido (nada de texto antes ou depois, nada de markdown),
                no seguinte formato exato, um objeto por pneu:

                [
                  {{
                    "fogo": "string (número lido na foto)",
                    "marca": "string (observado na foto)",
                    "sulco": "string (observado na foto)",
                    "danos": "string (observado na foto)",
                    "acao_recomendada": "string",
                    "confianca": "Alta | Média | Baixa"
                  }}
                ]

                NÃO invente dados de placa, posição, quilometragem ou datas — essas informações não vêm
                das fotos e serão preenchidas separadamente a partir do relatório da frota.
                """

                conteudo_requisicao = []
                for f in sorted_files:
                    bytes_comprimidos = comprimir_imagem(f.getvalue())
                    conteudo_requisicao.append(f"Arquivo: {f.name}")
                    conteudo_requisicao.append({"mime_type": "image/jpeg", "data": bytes_comprimidos})
                conteudo_requisicao.append(prompt_instrucoes)

                texto_status.text(f"Enviando dados para a IA ({nome_modelo_ativo})...")
                resposta_ia = model.generate_content(conteudo_requisicao)

                pneus_estruturados = None
                erro_parse = None
                try:
                    pneus_ia = extrair_json_da_resposta(resposta_ia.text)

                    # Cruzamento determinístico: para cada pneu identificado pela IA na foto,
                    # busca os dados fixos (POS, VEICULO, MEDIDA, RETIRADA, LOCAL, KM/POS, KM TOTAL)
                    # por correspondência EXATA do Fogo na tabela do relatório — a IA não participa
                    # dessa parte, evitando que ela erre ou deixe campos em branco.
                    tabela_df = st.session_state.dados_relatorio
                    pneus_estruturados = []
                    for item in pneus_ia:
                        fogo_lido = str(item.get("fogo", "")).strip()
                        dados_tabela = buscar_dados_relatorio(fogo_lido, tabela_df)

                        pneu = {
                            "fogo": fogo_lido,
                            "pos": dados_tabela.get("POS", "") if dados_tabela else "",
                            "veiculo": dados_tabela.get("VEICULO", "") if dados_tabela else "",
                            "medida": dados_tabela.get("MEDIDA", "") if dados_tabela else "",
                            "retirada": dados_tabela.get("RETIRADA", "") if dados_tabela else "",
                            "local": dados_tabela.get("LOCAL", "") if dados_tabela else "",
                            "km_pos": dados_tabela.get("KM/POS", "") if dados_tabela else "",
                            "km_total": dados_tabela.get("KM TOTAL", "") if dados_tabela else "",
                            "marca": item.get("marca", ""),
                            "sulco": item.get("sulco", ""),
                            "danos": item.get("danos", ""),
                            "acao_recomendada": item.get("acao_recomendada", ""),
                            "confianca": item.get("confianca", ""),
                            "fogo_localizado_na_planilha": dados_tabela is not None,
                        }
                        pneus_estruturados.append(pneu)
                except Exception as e:
                    erro_parse = str(e)

                st.session_state.inspection_results = [{
                    "Timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    "Modelo_Usado": nome_modelo_ativo,
                    "Analise_IA_Bruta": resposta_ia.text,
                    "Pneus": pneus_estruturados,
                    "Erro_Parse": erro_parse,
                    "Imagens": sorted_files
                }]

                texto_status.success(f"✅ Inspeção concluída com sucesso via {nome_modelo_ativo}!")

            except Exception as e:
                st.error(f"Erro no processamento: {str(e)}")

    # --------------------------------------------------------------------
    # EXIBIÇÃO DOS RESULTADOS
    # --------------------------------------------------------------------
    if st.session_state.inspection_results:
        st.markdown("---")
        st.subheader("📊 Laudo Consolidado")

        for res in st.session_state.inspection_results:
            with st.expander(f"🛞 Laudo do Lote ({len(res['Imagens'])} fotos) - Modelo: {res.get('Modelo_Usado', 'gemini-flash-latest')}", expanded=True):
                st.markdown("##### Miniaturas Enviadas:")
                cols = st.columns(min(len(res["Imagens"]), 6))
                for idx, img_file in enumerate(res["Imagens"]):
                    with cols[idx % 6]:
                        st.image(img_file, caption=img_file.name, use_container_width=True)

                st.markdown("---")

                if res["Pneus"]:
                    st.markdown("#### 🤖 Laudo por Pneu")
                    for i, pneu in enumerate(res["Pneus"], start=1):
                        titulo = f"PNEU {i} — FOGO {pneu.get('fogo', 'N/A')}"
                        if pneu.get("fogo_localizado_na_planilha") is False:
                            titulo += " ⚠️ (não encontrado na planilha)"
                        with st.container(border=True):
                            st.markdown(f"**{titulo}**")
                            c1, c2 = st.columns(2)
                            with c1:
                                st.write(f"**POS:** {pneu.get('pos', '')}")
                                st.write(f"**VEICULO:** {pneu.get('veiculo', '')}")
                                st.write(f"**MEDIDA:** {pneu.get('medida', '')}")
                                st.write(f"**RETIRADA:** {pneu.get('retirada', '')}")
                            with c2:
                                st.write(f"**LOCAL:** {pneu.get('local', '')}")
                                st.write(f"**KM/POS:** {pneu.get('km_pos', '')}")
                                st.write(f"**KM TOTAL:** {pneu.get('km_total', '')}")
                                st.write(f"**Confiança:** {pneu.get('confianca', '')}")
                            st.write(f"**Marca/Fabricante:** {pneu.get('marca', '')}")
                            st.write(f"**Condição do Sulco:** {pneu.get('sulco', '')}")
                            st.write(f"**Danos/Anomalias:** {pneu.get('danos', '')}")
                            st.write(f"**Ação Recomendada:** {pneu.get('acao_recomendada', '')}")

                    pdf_bytes = gerar_pdf_laudo(res["Pneus"], res["Timestamp"])
                    st.download_button(
                        label="📥 Baixar Laudo Técnico em PDF",
                        data=pdf_bytes,
                        file_name=f"laudo_pneus_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf",
                        type="primary",
                    )
                else:
                    st.warning(
                        "⚠️ A IA respondeu, mas não foi possível estruturar o resultado automaticamente "
                        f"({res.get('Erro_Parse', 'motivo desconhecido')}). Veja a resposta bruta abaixo e, "
                        "se necessário, baixe o laudo em formato simples."
                    )
                    st.text_area("Resposta bruta da IA", res["Analise_IA_Bruta"], height=300)
                    pdf_fallback = gerar_pdf_fallback(res["Analise_IA_Bruta"], res["Timestamp"])
                    st.download_button(
                        label="📥 Baixar Laudo (texto simples) em PDF",
                        data=pdf_fallback,
                        file_name=f"laudo_pneus_bruto_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf",
                    )

else:
    st.info("👆 Envie o relatório e as fotos para começar.")
