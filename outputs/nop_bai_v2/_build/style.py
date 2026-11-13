# -*- coding: utf-8 -*-
"""Module dung chung cho bo ho so (python-docx).

Dung:
    import style
    doc = style.new_document("Ten tai lieu")      # bia + muc luc + chan trang
    style.add_heading(doc, "Tong quan", 1)         # tu danh so 1, 1.1, 1.1.1
    style.add_paragraph(doc, "Noi dung...")
    style.add_bullets(doc, ["a", "b"])
    style.add_table(doc, ["Cot 1", "Cot 2"], [["a", "b"]], caption="Bang ...")
    style.add_figure(doc, "hinh.png", "Hinh ...")
    style.save(doc, "out.docx")
"""
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

FONT = "Times New Roman"
SIZE = 13
LINE = 1.3

PROJECT_NAME = "Trung tâm giám sát, điều hành và phục hồi sau sự cố nhà màng SMIOT"
TEAM = "Simpson"


def _set_font(style, size=SIZE, bold=None, italic=None):
    style.font.name = FONT
    style.font.size = Pt(size)
    if bold is not None:
        style.font.bold = bold
    if italic is not None:
        style.font.italic = italic
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(a), FONT)
    # bo mau tieu de mac dinh
    color = rpr.find(qn("w:color"))
    if color is not None:
        rpr.remove(color)


def _fmt(style, before=0, after=6, line=LINE):
    pf = style.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.line_spacing = line


def _setup_styles(doc):
    st = doc.styles
    _set_font(st["Normal"])
    _fmt(st["Normal"], 0, 6)
    st["Normal"].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    sizes = {1: 16, 2: 14, 3: 13}
    for lvl, sz in sizes.items():
        s = st["Heading %d" % lvl]
        _set_font(s, sz, bold=True, italic=False)
        _fmt(s, 14 if lvl == 1 else 10, 6)
        s.paragraph_format.keep_with_next = True
        s.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    for name in ("List Bullet", "Caption"):
        _set_font(st[name])
        _fmt(st[name], 0, 4)
    _set_font(st["Caption"], 12, bold=False, italic=True)
    st["Caption"].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    st["Caption"].paragraph_format.keep_with_next = False
    for n in ("TOC Heading",):
        if n in [s.name for s in st]:
            _set_font(st[n], 16, bold=True)


def _page_setup(section):
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)
    section.left_margin = Cm(3)
    section.right_margin = Cm(2)


def _field(paragraph, instr, placeholder=""):
    run = paragraph.add_run()
    b = OxmlElement("w:fldChar")
    b.set(qn("w:fldCharType"), "begin")
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = instr
    sep = OxmlElement("w:fldChar")
    sep.set(qn("w:fldCharType"), "separate")
    t = OxmlElement("w:t")
    t.text = placeholder
    e = OxmlElement("w:fldChar")
    e.set(qn("w:fldCharType"), "end")
    for x in (b, it, sep, t, e):
        run._r.append(x)
    return run


def _footer_page_number(section):
    section.footer.is_linked_to_previous = False
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for r in list(p.runs):
        r._r.getparent().remove(r._r)
    _field(p, "PAGE", "1")
    for r in p.runs:
        r.font.name = FONT
        r.font.size = Pt(12)


def _update_fields_on_open(doc):
    settings = doc.settings.element
    el = OxmlElement("w:updateFields")
    el.set(qn("w:val"), "true")
    settings.append(el)


def _par(doc, text="", bold=False, italic=False, size=SIZE, align=None, after=6):
    p = doc.add_paragraph()
    if text:
        r = p.add_run(text)
        r.bold = bold
        r.italic = italic
        r.font.size = Pt(size)
        r.font.name = FONT
    if align is not None:
        p.alignment = align
    p.paragraph_format.space_after = Pt(after)
    return p


def add_cover(doc, doc_title):
    C = WD_ALIGN_PARAGRAPH.CENTER
    for _ in range(5):
        _par(doc)
    _par(doc, "HỒ SƠ DỰ ÁN", True, size=14, align=C)
    _par(doc, PROJECT_NAME.upper(), True, size=20, align=C, after=24)
    _par(doc, doc_title, True, size=18, align=C, after=48)
    _par(doc, "Nhóm: " + TEAM, True, size=14, align=C)
    _par(doc)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def add_toc(doc):
    p = _par(doc, "MỤC LỤC", True, size=16, align=WD_ALIGN_PARAGRAPH.CENTER, after=12)
    p2 = doc.add_paragraph()
    _field(p2, 'TOC \\o "1-3" \\h \\z \\u',
           "Nhấn chuột phải và chọn Update Field để cập nhật mục lục.")
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def new_document(doc_title, with_toc=True):
    doc = Document()
    _page_setup(doc.sections[0])
    _setup_styles(doc)
    doc._smiot_counters = [0, 0, 0]
    doc._smiot_fig = 0
    doc._smiot_tab = 0
    add_cover(doc, doc_title)
    if with_toc:
        add_toc(doc)
    _footer_page_number(doc.sections[0])
    _update_fields_on_open(doc)
    return doc


def add_heading(doc, text, level=1):
    """Tieu de tu danh so: 1, 1.1, 1.1.1 (toi da cap 3)."""
    level = max(1, min(3, level))
    c = doc._smiot_counters
    c[level - 1] += 1
    for i in range(level, 3):
        c[i] = 0
    num = ".".join(str(x) for x in c[:level])
    return doc.add_heading("%s. %s" % (num, text) if level == 1 else "%s %s" % (num, text), level)


def add_paragraph(doc, text, bold=False, italic=False):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = bold
    r.italic = italic
    return p


def add_bullets(doc, items):
    for it in items:
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(it)
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT


def _borders(table):
    tbl = table._tbl
    pr = tbl.tblPr
    b = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement("w:" + edge)
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), "4")
        e.set(qn("w:space"), "0")
        e.set(qn("w:color"), "000000")
        b.append(e)
    pr.append(b)


def _shade(cell, fill="D9D9D9"):
    tcpr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear")
    sh.set(qn("w:color"), "auto")
    sh.set(qn("w:fill"), fill)
    tcpr.append(sh)


def _repeat_header(row):
    trpr = row._tr.get_or_add_trPr()
    h = OxmlElement("w:tblHeader")
    h.set(qn("w:val"), "true")
    trpr.append(h)


def add_table(doc, header, rows, caption=None, font_size=11):
    """Bang co tieu de in dam, ke bang. caption (neu co) dat phia tren bang."""
    if caption:
        doc._smiot_tab += 1
        cp = doc.add_paragraph(style="Caption")
        cp.add_run("Bảng %d. %s" % (doc._smiot_tab, caption))
        cp.paragraph_format.keep_with_next = True
    t = doc.add_table(rows=1, cols=len(header))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    _borders(t)
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]
        c.text = ""
        r = c.paragraphs[0].add_run(str(h))
        r.bold = True
        r.font.size = Pt(font_size)
        r.font.name = FONT
        c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        _shade(c)
    _repeat_header(t.rows[0])
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            para = cells[i].paragraphs[0]
            r = para.add_run("" if v is None else str(v))
            r.font.size = Pt(font_size)
            r.font.name = FONT
            para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    for row in t.rows:
        for c in row.cells:
            for para in c.paragraphs:
                para.paragraph_format.line_spacing = 1.15
                para.paragraph_format.space_after = Pt(2)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    return t


def add_figure(doc, png_path, caption, width_cm=15.0):
    """Chen hinh can giua, chu thich phia duoi."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(png_path, width=Cm(width_cm))
    doc._smiot_fig += 1
    cp = doc.add_paragraph(style="Caption")
    cp.add_run("Hình %d. %s" % (doc._smiot_fig, caption))
    return p


def save(doc, path):
    doc.save(path)
    return path


if __name__ == "__main__":
    import os
    import tempfile
    d = new_document("Tài liệu thử")
    add_heading(d, "Mục thử", 1)
    add_heading(d, "Mục con", 2)
    add_heading(d, "Mục cháu", 3)
    add_paragraph(d, "Đoạn văn thử bằng tiếng Việt có dấu.")
    add_bullets(d, ["Ý một", "Ý hai"])
    add_table(d, ["Cột A", "Cột B"], [["1", "2"], ["3", "4"]], caption="Bảng thử")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        png = os.path.join(tempfile.gettempdir(), "_smiot_test.png")
        plt.plot([1, 2, 3]); plt.savefig(png, dpi=80); plt.close()
        add_figure(d, png, "Hình thử")
        os.remove(png)
    except ImportError:
        pass
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_test.docx")
    save(d, out)
    print("OK", os.path.getsize(out))
    os.remove(out)
