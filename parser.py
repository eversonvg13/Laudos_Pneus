import re
import pandas as pd
from bs4 import BeautifulSoup

# Campos fixos do laudo, na ordem exigida
CAMPOS_FIXOS = ["FOGO", "POS", "VEICULO", "MEDIDA", "RETIRADA", "LOCAL", "KM/POS", "KM TOTAL"]

# Mapeamento de posição (left em px) -> nome da coluna
COLUNAS_REFERENCIA = [
    (0, "VEICULO"), (45, "POS"), (68, "FOGO"), (113, "MARCA"), (232, "MEDIDA"),
    (350, "E"), (362, "RE"), (379, "CO"), (396, "V"), (407, "COLOCADO"),
    (469, "RETIRADA"), (531, "DIAS"), (571, "MOTIVO"), (655, "LOCAL"),
    (695, "KM/POS"), (751, "VIDA1"), (814, "RECAP1"), (876, "RECAP2"),
    (938, "RECAP3"), (1000, "KM TOTAL"), (1085, "RECAPADOR_SERVICO_VALOR"),
]
TOLERANCIA_PX = 30


def _left_para_coluna(left_px):
    melhor = min(COLUNAS_REFERENCIA, key=lambda c: abs(c[0] - left_px))
    if abs(melhor[0] - left_px) <= TOLERANCIA_PX:
        return melhor[1]
    return None


def parse_relatorio_html(file_bytes):
    """
    Lê o relatório HTML (RDprint por divs ou Tabela HTML simples) 
    e extrai os campos de cada pneu.
    """
    soup = BeautifulSoup(file_bytes, "html.parser")
    paginas = soup.find_all("div", class_="pagina")

    registros = []

    # MÉTODO 1: Processamento por Divs do RDprint (posições em px)
    if paginas:
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
                if len(campos) < 10:
                    continue
                campos.sort(key=lambda c: c[0])
                registro = {}
                for left, texto in campos:
                    coluna = _left_para_coluna(left)
                    if coluna and coluna not in registro:
                        registro[coluna] = texto.strip()

                veiculo = registro.get("VEICULO", "")
                fogo = registro.get("FOGO", "")
                if veiculo.isdigit() and fogo.isdigit():
                    registros.append({c: registro.get(c, "") for c in CAMPOS_FIXOS})

    # MÉTODO 2: Fallback para Tabelas HTML padrão (<tr> / <td>)
    if not registros:
        linhas_tr = soup.find_all("tr")
        veiculo_atual = ""
        for tr in linhas_tr:
            cols = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if len(cols) >= 8:
                if cols[0] and cols[0].isdigit():
                    veiculo_atual = cols[0]
                fogo = cols[2]
                if fogo.isdigit():
                    registros.append({
                        "VEICULO": veiculo_atual,
                        "POS": cols[1],
                        "FOGO": cols[2],
                        "MEDIDA": cols[3],
                        "RETIRADA": cols[4],
                        "LOCAL": cols[5],
                        "KM/POS": cols[6],
                        "KM TOTAL": cols[7]
                    })

    df = pd.DataFrame(registros, columns=CAMPOS_FIXOS)
    if df.empty:
        return df

    # Ordena pela data de retirada mais recente e remove duplicadas do mesmo fogo
    df["_retirada_dt"] = pd.to_datetime(df["RETIRADA"], format="%d/%m/%Y", errors="coerce")
    df = df.sort_values("_retirada_dt", ascending=False, na_position="last")
    df = df.drop_duplicates(subset="FOGO", keep="first")
    df = df.drop(columns="_retirada_dt").sort_values("FOGO").reset_index(drop=True)
    return df