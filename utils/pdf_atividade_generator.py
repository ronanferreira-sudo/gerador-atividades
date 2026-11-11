import os
import re
import html
try:
    import pythoncom
    from docx2pdf import convert
except ImportError:
    pythoncom = None
    convert = None
import docx

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    HRFlowable,
    KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """
    Canvas em dois passos para calcular o total real de páginas
    e desenhar o rodapé institucional em todas elas.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.6)

        # Linha divisória do rodapé
        self.line(36, 36, 559, 36)

        # Informações institucionais e numeração
        self.drawString(36, 24, "SENAI — Serviço Nacional de Aprendizagem Industrial")
        self.drawRightString(559, 24, f"Página {self._pageNumber} de {page_count}")
        self.restoreState()


def _formatar_texto_markdown(texto):
    """Escapa HTML e converte marcadores básicos de markdown para tags do ReportLab."""
    if not texto:
        return ""
    txt = html.escape(texto)
    # Negrito: **texto** ou __texto__
    txt = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", txt)
    txt = re.sub(r"__(.+?)__", r"<b>\1</b>", txt)
    # Itálico: *texto* ou _texto_
    txt = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<i>\1</i>", txt)
    return txt


def _localizar_logo():
    """Tenta localizar o logotipo oficial do SENAI."""
    candidatos = [
        "static/img/SENAI_logo_2024.png",
        "static/img/logo.png",
        "static/img/logo.jpg",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "static/img/SENAI_logo_2024.png"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "static/img/logo.jpg"),
    ]
    for c in candidatos:
        if os.path.exists(c):
            return c
    return None


def gerar_pdf_atividade_reportlab(
    arquivo_pdf,
    titulo=None,
    subtitulo=None,
    dados_cabecalho=None,
    conteudo=None,
    arquivo_docx=None
):
    """
    Gera o PDF da atividade usando ReportLab nativo, garantindo
    layout profissional no padrão SENAI mesmo sem Microsoft Word instalado.
    """
    pasta = os.path.dirname(arquivo_pdf)
    if pasta:
        os.makedirs(pasta, exist_ok=True)

    cabecalho = dict(dados_cabecalho or {})
    texto_questoes = conteudo or ""
    titulo_doc = str(titulo or "ATIVIDADE")

    # Se faltar dados e houver o DOCX disponível, lê parágrafos do DOCX
    if (not cabecalho or not texto_questoes) and arquivo_docx and os.path.exists(arquivo_docx):
        try:
            doc_docx = docx.Document(arquivo_docx)
            questoes_linhas = []
            lendo_questoes = False

            for p in doc_docx.paragraphs:
                txt = p.text.strip()
                if not txt:
                    continue
                if txt.startswith("- Curso:"):
                    if not cabecalho.get("curso"):
                        cabecalho["curso"] = txt.replace("- Curso:", "").strip()
                elif txt.startswith("- Unidade Curricular:"):
                    if not cabecalho.get("unidade_curricular"):
                        cabecalho["unidade_curricular"] = txt.replace("- Unidade Curricular:", "").strip()
                elif txt.startswith("- Aula / Encontro:"):
                    if not cabecalho.get("aula_encontro"):
                        cabecalho["aula_encontro"] = txt.replace("- Aula / Encontro:", "").strip()
                elif txt.startswith("- Nível Cognitivo (Taxonomia de Bloom):"):
                    if not cabecalho.get("nivel_bloom"):
                        cabecalho["nivel_bloom"] = txt.replace("- Nível Cognitivo (Taxonomia de Bloom):", "").strip()
                elif txt.lower() in ("questões", "questoes", "atividades"):
                    lendo_questoes = True
                elif lendo_questoes:
                    questoes_linhas.append(txt)

            if not texto_questoes and questoes_linhas:
                texto_questoes = "\n".join(questoes_linhas)
        except Exception as e:
            print(f"Aviso ao inspecionar DOCX para PDF: {e}")

    pdf_doc = SimpleDocTemplate(
        arquivo_pdf,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=48
    )

    styles = getSampleStyleSheet()

    style_titulo = ParagraphStyle(
        "TituloAtividade",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=colors.HexColor("#004696"),
        alignment=1,  # Centralizado
    )

    style_lbl = ParagraphStyle(
        "LblInfo",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#003366")
    )

    style_val = ParagraphStyle(
        "ValInfo",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#1E293B")
    )

    story = []

    # 1. Cabeçalho com Logo SENAI e Título
    logo_path = _localizar_logo()
    titulo_escaped = html.escape(titulo_doc)
    if logo_path:
        img_logo = Image(logo_path, width=115, height=29)
        img_logo.hAlign = "LEFT"
        t_header = Table([[img_logo, Paragraph(f"<b>{titulo_escaped}</b>", style_titulo)]], colWidths=[125, 398])
        t_header.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (1, 0), "CENTER"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(t_header)
    else:
        story.append(Paragraph(f"<b>{titulo_escaped}</b>", style_titulo))

    story.append(Spacer(1, 6))

    # 2. Caixa de Identificação
    curso_txt = html.escape(str(cabecalho.get("curso") or subtitulo or "—"))
    uc_txt = html.escape(str(cabecalho.get("unidade_curricular") or "—"))
    aula_txt = html.escape(str(cabecalho.get("aula_encontro") or "Encontro Regular"))
    bloom_txt = html.escape(str(cabecalho.get("nivel_bloom") or "Lembrar"))

    dados_tabela = [
        [
            Paragraph("<b>Curso:</b>", style_lbl),
            Paragraph(curso_txt, style_val),
            Paragraph("<b>Data:</b>", style_lbl),
            Paragraph("____/____/________", style_val)
        ],
        [
            Paragraph("<b>Unidade Curricular:</b>", style_lbl),
            Paragraph(uc_txt, style_val),
            Paragraph("<b>Bloom:</b>", style_lbl),
            Paragraph(bloom_txt, style_val)
        ],
        [
            Paragraph("<b>Aula / Encontro:</b>", style_lbl),
            Paragraph(aula_txt, style_val),
            Paragraph("<b>Estudante:</b>", style_lbl),
            Paragraph("____________________________", style_val)
        ]
    ]

    t_info = Table(dados_tabela, colWidths=[105, 218, 55, 145])
    t_info.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#94A3B8")),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))

    story.append(t_info)
    story.append(Spacer(1, 10))

    # 3. Faixa de Seção de Questões
    style_secao = ParagraphStyle(
        "SecaoQuestoes",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=13,
        textColor=colors.HexColor("#004696"),
    )
    story.append(Paragraph("QUESTÕES DA ATIVIDADE", style_secao))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#004696"), spaceBefore=2, spaceAfter=8))

    # 4. Questões formatadas
    style_questao = ParagraphStyle(
        "QuestaoHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=7,
        spaceAfter=3,
        keepWithNext=True
    )
    style_corpo = ParagraphStyle(
        "QuestaoCorpo",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1E293B"),
        spaceBefore=2,
        spaceAfter=2
    )
    style_alt = ParagraphStyle(
        "QuestaoAlternativa",
        parent=style_corpo,
        leftIndent=14,
        spaceBefore=1,
        spaceAfter=2
    )
    style_gabarito = ParagraphStyle(
        "QuestaoGabarito",
        parent=style_corpo,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#0284C7"),
        spaceBefore=4,
        spaceAfter=6
    )

    linhas = texto_questoes.split("\n")
    for linha in linhas:
        l_strip = linha.strip()
        if not l_strip:
            story.append(Spacer(1, 3))
            continue

        l_fmt = _formatar_texto_markdown(l_strip)

        if re.match(r"^(Quest[aã]o\s*\d+|Exerc[íi]cio\s*\d+|\d+[\.\)])", l_strip, re.IGNORECASE):
            story.append(Paragraph(l_fmt, style_questao))
        elif re.match(r"^[A-E]\)", l_strip):
            story.append(Paragraph(l_fmt, style_alt))
        elif l_strip.lower().startswith("resposta") or l_strip.lower().startswith("gabarito:"):
            story.append(Paragraph(l_fmt, style_gabarito))
        else:
            story.append(Paragraph(l_fmt, style_corpo))

    pdf_doc.build(story, canvasmaker=NumberedCanvas)
    return True


def gerar_pdf_atividade(
    arquivo_docx,
    arquivo_pdf,
    titulo=None,
    subtitulo=None,
    dados_cabecalho=None,
    conteudo=None
):
    """
    Função principal para gerar o PDF da atividade.
    Gera o PDF com layout institucional SENAI nativamente via ReportLab (rápido, sem depender de Word).
    Caso necessário, suporta docx2pdf como alternativa.
    """
    pasta = os.path.dirname(arquivo_pdf)
    if pasta:
        os.makedirs(pasta, exist_ok=True)

    # 1. Geração nativa e de alta performance com ReportLab (padrão institucional SENAI)
    try:
        sucesso = gerar_pdf_atividade_reportlab(
            arquivo_pdf=arquivo_pdf,
            titulo=titulo,
            subtitulo=subtitulo,
            dados_cabecalho=dados_cabecalho,
            conteudo=conteudo,
            arquivo_docx=arquivo_docx
        )
        if sucesso and os.path.exists(arquivo_pdf) and os.path.getsize(arquivo_pdf) > 0:
            print(f"[OK] PDF de atividade gerado com sucesso via ReportLab: {arquivo_pdf}")
            return True
    except Exception as e:
        print(f"Aviso no gerador ReportLab da atividade: {e}. Tentando docx2pdf...")

    # 2. Alternativa via docx2pdf (se Word estiver disponível no Windows)
    if pythoncom and convert and arquivo_docx and os.path.exists(arquivo_docx):
        try:
            pythoncom.CoInitialize()
            convert(arquivo_docx, arquivo_pdf)
            if os.path.exists(arquivo_pdf) and os.path.getsize(arquivo_pdf) > 0:
                print(f"[OK] PDF gerado via docx2pdf: {arquivo_pdf}")
                return True
        except Exception as e:
            print(f"Aviso docx2pdf indisponível ({e}).")
        finally:
            try:
                pythoncom.CoUninitialize()
            except:
                pass

    return os.path.exists(arquivo_pdf) and os.path.getsize(arquivo_pdf) > 0
