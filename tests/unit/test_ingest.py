import pytest

from app import ingest


def test_chunk_respeta_tamano_y_traslape():
    text = "\n\n".join(f"Párrafo {i}. " + "palabra " * 40 for i in range(10))
    chunks = ingest.chunk(text, size=500, overlap=100)
    assert len(chunks) > 1
    assert all(len(c) <= 500 + 100 + 2 for c in chunks)
    assert chunks[0][-100:] in chunks[1]  # el final de uno abre el siguiente


def test_chunk_parte_un_parrafo_enorme():
    chunks = ingest.chunk("x" * 2500, size=1000, overlap=150)
    assert len(chunks) >= 3
    assert "".join(chunks).count("x") >= 2500


def test_chunk_texto_vacio():
    assert ingest.chunk("   \n\n  ") == []


def test_txt_en_cp1252(tmp_path):
    path = tmp_path / "viejo.txt"
    path.write_bytes("Inscripción del año".encode("cp1252"))
    assert ingest.read_file(path) == "Inscripción del año"


def test_csv_con_punto_y_coma(tmp_path):
    path = tmp_path / "materias.csv"
    path.write_text("Clave;Materia;Semestre\nTC1001;Programación;1\n", encoding="utf-8")
    text = ingest.read_file(path)
    assert "TC1001 | Programación | 1" in text


def test_docx_con_tabla(tmp_path):
    docx = pytest.importorskip("docx")
    doc = docx.Document()
    doc.add_paragraph("Requisitos de graduación")
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Servicio social"
    table.rows[0].cells[1].text = "480 horas"
    path = tmp_path / "reglamento.docx"
    doc.save(path)
    text = ingest.read_file(path)
    assert "Requisitos de graduación" in text and "Servicio social | 480 horas" in text


def test_xlsx(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    wb.active.title = "Plan"
    wb.active.append(["Semestre", "Materia"])
    wb.active.append([1, "Cálculo"])
    path = tmp_path / "plan.xlsx"
    wb.save(path)
    text = ingest.read_file(path)
    assert "Hoja: Plan" in text and "1 | Cálculo" in text


def test_pptx(tmp_path):
    pptx = pytest.importorskip("pptx")
    prs = pptx.Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "Becas"
    slide.placeholders[1].text = "La convocatoria abre en agosto"
    path = tmp_path / "becas.pptx"
    prs.save(path)
    text = ingest.read_file(path)
    assert "Diapositiva 1" in text and "convocatoria abre en agosto" in text


def test_formato_no_soportado(tmp_path):
    path = tmp_path / "foto.png"
    path.write_bytes(b"\x89PNG")
    with pytest.raises(ValueError):
        ingest.read_file(path)
