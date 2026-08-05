import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak


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