import markdown
import weasyprint

_EXTENSIONS = ["tables", "sane_lists"]

_CSS = """
@page { size: Letter; margin: 2cm; }
body { font-family: Georgia, 'Times New Roman', serif; font-size: 10.5pt; line-height: 1.45; color: #1a1a1a; }
h1, h2, h3 { font-family: Helvetica, Arial, sans-serif; color: #111111; }
h1 { font-size: 18pt; border-bottom: 2px solid #333333; padding-bottom: 6px; }
h2 { font-size: 14pt; margin-top: 1.4em; }
h3 { font-size: 12pt; margin-top: 1.2em; }
table { border-collapse: collapse; width: 100%; font-size: 8.5pt; margin: 1em 0; }
th, td { border: 1px solid #cccccc; padding: 4px 6px; text-align: left; vertical-align: top; }
th { background: #eeeeee; }
hr { border: none; border-top: 1px solid #cccccc; margin: 1.4em 0; }
code, pre { font-family: 'Courier New', monospace; }
"""


def render(markdown_text: str) -> bytes:
    """Publisher interface: markdown_text -> pdf_bytes.

    Swappable in isolation — nothing outside this module knows or cares
    that this is currently markdown+weasyprint (see DESIGN.md §4/§6).
    """
    html_body = markdown.markdown(markdown_text, extensions=_EXTENSIONS)
    full_html = f"<html><head><style>{_CSS}</style></head><body>{html_body}</body></html>"
    return weasyprint.HTML(string=full_html).write_pdf()
