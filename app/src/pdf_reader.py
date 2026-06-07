from pathlib import Path
import pdfplumber

MAX_TEXT_CHARS = 60_000


def convert_tables_to_markdown(tables: list[list]) -> str:
    if not tables:
        return ""
    md_parts = []
    for table_idx, table in enumerate(tables):
        if not table:
            continue
        cleaned_table = []
        for row in table:
            if row:
                cleaned_table.append([str(cell or "").replace("\n", " ").strip() for cell in row])
        if not cleaned_table:
            continue

        num_cols = max(len(row) for row in cleaned_table)
        md_rows = []

        header = cleaned_table[0]
        if len(header) < num_cols:
            header += [""] * (num_cols - len(header))
        md_rows.append("| " + " | ".join(header) + " |")
        md_rows.append("| " + " | ".join(["---"] * num_cols) + " |")

        for row in cleaned_table[1:]:
            if len(row) < num_cols:
                row += [""] * (num_cols - len(row))
            md_rows.append("| " + " | ".join(row) + " |")

        md_parts.append(f"### Tabla de Datos {table_idx+1}\n\n" + "\n".join(md_rows))
    return "\n\n".join(md_parts)


def read_pdf(path: Path) -> dict:
    """Extract text and tables from a PDF file.

    Returns a dict with:
      - file_name: original filename
      - page_count: number of pages
      - text: extracted text (truncated to MAX_TEXT_CHARS if needed)
      - tables: list of tables found (each as list of rows)
      - has_text_layer: whether the PDF had selectable text
      - truncated: whether the text was cut short
    """
    text_parts: list[str] = []
    tables: list[list] = []
    has_text = False

    with pdfplumber.open(str(path)) as pdf:
        page_count = len(pdf.pages)
        for i, page in enumerate(pdf.pages, 1):
            page_text = page.extract_text() or ""
            if page_text.strip():
                has_text = True
            text_parts.append(f"--- Página {i} ---\n{page_text}")

            page_tables = page.extract_tables() or []
            for table in page_tables:
                tables.append(table)

    full_text = "\n\n".join(text_parts)

    # Append structured tables as markdown to the plain text representation
    md_tables = convert_tables_to_markdown(tables)
    if md_tables:
        full_text += "\n\n## Tablas Estructuradas Extraídas del PDF\n\n" + md_tables

    truncated = False
    if len(full_text) > MAX_TEXT_CHARS:
        full_text = full_text[:MAX_TEXT_CHARS] + "\n\n[...texto truncado por límite de contexto...]"
        truncated = True

    return {
        "file_name": path.name,
        "page_count": page_count,
        "text": full_text,
        "tables": tables,
        "has_text_layer": has_text,
        "truncated": truncated,
    }


def read_multiple_pdfs(paths: list[Path]) -> list[dict]:
    """Read multiple PDFs and return a list of extraction results."""
    results = []
    for p in paths:
        results.append(read_pdf(p))
    return results
