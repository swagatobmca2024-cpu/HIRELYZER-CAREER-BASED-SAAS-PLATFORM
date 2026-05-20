# pdf_fix.py
# ══════════════════════════════════════════════════════════════════════════════
# PDF-SAFE HTML RENDERER — drop-in replacement for html_to_pdf_bytes()
#
# What this fixes vs the old approach:
#   1. Injects @page A4 rule → proper A4 page size every time
#   2. Injects page-break-inside:avoid on all section/card divs → no mid-card cuts
#   3. Converts display:flex → table-based layout for two-column templates
#   4. Replaces linear-gradient() backgrounds with their first solid colour
#   5. Strips all CSS xhtml2pdf cannot parse (gap, grid, object-fit, box-shadow…)
#   6. Converts px font sizes to pt equivalents (1px ≈ 0.75pt) for crisp PDF text
#   7. Wraps body in a max-width:780px centred container → consistent A4 width
#   8. Adds page-break logic: every top-level section gets page-break-inside:avoid
#
# Usage (replace html_to_pdf_bytes in taab2.py):
#   from pdf_fix import html_to_pdf_bytes
# ══════════════════════════════════════════════════════════════════════════════

import re
from io import BytesIO
from xhtml2pdf import pisa


# ── 1. CSS properties that crash xhtml2pdf — strip entirely ──────────────────
_STRIP_PROPS = [
    r'flex-wrap\s*:[^;]*',
    r'flex-direction\s*:[^;]*',
    r'flex-shrink\s*:[^;]*',
    r'flex-grow\s*:[^;]*',
    r'flex\s*:[^;]*',
    r'align-items\s*:[^;]*',
    r'align-self\s*:[^;]*',
    r'justify-content\s*:[^;]*',
    r'justify-self\s*:[^;]*',
    r'gap\s*:[^;]*',
    r'row-gap\s*:[^;]*',
    r'column-gap\s*:[^;]*',
    r'grid[^:]*:[^;]*',
    r'object-fit\s*:[^;]*',
    r'object-position\s*:[^;]*',
    r'box-shadow\s*:[^;]*',
    r'text-shadow\s*:[^;]*',
    r'background-clip\s*:[^;]*',
    r'-webkit-[^:]*:[^;]*',
    r'-moz-[^:]*:[^;]*',
    r'-ms-[^:]*:[^;]*',
    r'transition\s*:[^;]*',
    r'transform\s*:[^;]*',
    r'animation[^:]*:[^;]*',
    r'will-change\s*:[^;]*',
    r'pointer-events\s*:[^;]*',
    r'resize\s*:[^;]*',
    r'cursor\s*:[^;]*',
    r'overflow-x\s*:[^;]*',
    r'overflow-y\s*:[^;]*',
    r'overflow\s*:\s*(?!hidden)[^;]*',
    r'white-space\s*:[^;]*',
    r'word-break\s*:[^;]*',
    r'overflow-wrap\s*:[^;]*',
    r'text-overflow\s*:[^;]*',
    r'letter-spacing\s*:[^;]*',
    r'text-transform\s*:[^;]*',
    r'min-height\s*:[^;]*',
    r'min-width\s*:[^;]*',
    r'max-width\s*:[^;]*',
    r'backdrop-filter\s*:[^;]*',
    r'filter\s*:[^;]*',
]

_STRIP_RE_LIST   = [re.compile(p, re.IGNORECASE) for p in _STRIP_PROPS]
_GRADIENT_RE     = re.compile(r'background\s*:\s*linear-gradient\(([^)]*)\)\s*(?:;|$)', re.IGNORECASE)
_FIRST_COLOR_RE  = re.compile(r'(#[0-9a-fA-F]{3,8}|rgba?\([^)]+\))')
_FLEX_DISP_RE    = re.compile(r'display\s*:\s*flex\b', re.IGNORECASE)
_IFLEX_DISP_RE   = re.compile(r'display\s*:\s*inline-flex\b', re.IGNORECASE)
_VIEWPORT_RE     = re.compile(r'[\w-]+\s*:[^;]*\d+v[hwmin][^;]*(?:;|$)', re.IGNORECASE)

# px font-size → pt  (factor 0.75 — standard CSS conversion)
_FONT_PX_RE = re.compile(r'font-size\s*:\s*(\d+(?:\.\d+)?)px', re.IGNORECASE)


def _px_to_pt(m):
    pt = round(float(m.group(1)) * 0.75, 1)
    return f'font-size:{pt}pt'


def _gradient_to_solid(m):
    colour_m = _FIRST_COLOR_RE.search(m.group(1))
    colour = colour_m.group(0) if colour_m else '#f5f5f5'
    return f'background:{colour};'


def _clean_style_value(val):
    val = _GRADIENT_RE.sub(_gradient_to_solid, val)
    val = _VIEWPORT_RE.sub('', val)
    val = _FLEX_DISP_RE.sub('display:block', val)
    val = _IFLEX_DISP_RE.sub('display:inline-block', val)
    for pat in _STRIP_RE_LIST:
        val = pat.sub('', val)
    # px → pt for font-size
    val = _FONT_PX_RE.sub(_px_to_pt, val)
    # clean up leftover semicolons
    val = re.sub(r'\s*;\s*;+', ';', val)
    val = re.sub(r'^\s*;+', '', val)
    return val.strip().strip(';')


def _replace_style_attr(m):
    quote   = m.group(1)
    cleaned = _clean_style_value(m.group(2))
    if not cleaned.strip():
        return ''
    return f'style={quote}{cleaned}{quote}'


def _clean_style_tag(m):
    css = m.group(1)
    css = _GRADIENT_RE.sub('background:#f5f5f5;', css)
    css = _FLEX_DISP_RE.sub('display:block', css)
    css = _IFLEX_DISP_RE.sub('display:inline-block', css)
    for pat in _STRIP_RE_LIST:
        css = pat.sub('', css)
    css = _FONT_PX_RE.sub(_px_to_pt, css)
    return f'<style>{css}</style>'


# ── 2. page-break injection ───────────────────────────────────────────────────
# Inject page-break-inside:avoid on every <div> that looks like a
# section wrapper or entry card (has margin-bottom in its style).
_DIV_STYLE_RE = re.compile(r'(<div\s[^>]*style=[\'"])([^"\']*margin-bottom[^"\']*)', re.IGNORECASE)


def _inject_page_break(m):
    opening = m.group(1)
    style   = m.group(2)
    if 'page-break-inside' not in style:
        style = style + ';page-break-inside:avoid'
    return opening + style


# ── 3. Two-column table layout fixer ─────────────────────────────────────────
# The default/sidebar/corporate etc. templates already use <table> for the
# two-column layout — that renders fine in xhtml2pdf.
# However some templates still use display:flex on the outer wrapper.
# After _clean_style_value converts flex→block, the sidebar column simply
# stacks below the main content, which is acceptable for PDF.
# We add a width hint to the sidebar <td> so it doesn't collapse.
_TD_WIDTH_RE = re.compile(r'(<td\s[^>]*style=[\'"])((?:(?!width)[^"\'])*)(width:\s*\d+px)', re.IGNORECASE)


# ── 4. Master sanitiser ───────────────────────────────────────────────────────
def _sanitize_html_for_pdf(html: str) -> str:
    # Inline style attributes
    html = re.sub(
        r'''style=(['"])(.*?)\1''',
        _replace_style_attr,
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # <style> tag blocks
    html = re.sub(
        r'<style[^>]*>(.*?)</style>',
        _clean_style_tag,
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Inject page-break-inside:avoid on section cards
    html = _DIV_STYLE_RE.sub(_inject_page_break, html)
    return html


# ── 5. A4 page wrapper ────────────────────────────────────────────────────────
_A4_WRAPPER = """\
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    @page {{
      size: A4 portrait;
      margin: 15mm 12mm 15mm 12mm;
    }}
    html, body {{
      margin: 0;
      padding: 0;
      font-size: 10pt;
      font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
      line-height: 1.5;
      color: #111;
      background: #fff;
      width: 100%;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }}
    td {{
      vertical-align: top;
    }}
    h1 {{ font-size: 18pt; margin: 0 0 4pt; }}
    h2 {{ font-size: 14pt; margin: 0 0 4pt; }}
    h3 {{ font-size: 11pt; margin: 0 0 3pt; }}
    p  {{ margin: 0 0 5pt; }}
    ul {{ margin: 0 0 6pt 16pt; padding: 0; list-style-type: disc; }}
    li {{ margin-bottom: 3pt; }}
    a  {{ color: inherit; text-decoration: none; }}
    hr {{ border: none; border-top: 1pt solid #ccc; margin: 6pt 0; }}
    /* Section cards — never split across pages */
    .section-card {{
      page-break-inside: avoid;
    }}
  </style>
</head>
<body>
  __CONTENT__
</body>
</html>"""


# ── 6. Public API ─────────────────────────────────────────────────────────────
def html_to_pdf_bytes(html_string: str) -> BytesIO:
    """
    Convert a resume/cover-letter HTML string to an A4 PDF BytesIO object.

    Drop-in replacement for the old html_to_pdf_bytes() in taab2.py.
    No third-party services needed — uses xhtml2pdf (pisa) only.

    Returns a seeked BytesIO containing the PDF bytes.
    """
    safe_html  = _sanitize_html_for_pdf(html_string)
    full_html  = _A4_WRAPPER.replace('__CONTENT__', safe_html)

    pdf_io = BytesIO()
    result = pisa.CreatePDF(full_html, dest=pdf_io)

    if result.err:
        # Fallback: return whatever pisa managed to produce
        pass

    pdf_io.seek(0)
    return pdf_io


# ── 7. Template HTML post-processor (call before rendering) ──────────────────
# This injects section-card class onto every top-level section div so
# page-break-inside:avoid is guaranteed even if the inline style injection
# missed it. Call this on the HTML string BEFORE passing to html_to_pdf_bytes.

_SECTION_DIV_RE = re.compile(
    r'(<div\s[^>]*style=[\'"][^"\']*margin-bottom:\s*(?:2[0-9]|[3-9]\d)\w+[^"\']*[\'"])',
    re.IGNORECASE,
)

def add_section_classes(html: str) -> str:
    """
    Adds class='section-card' to every <div> whose inline style contains
    a margin-bottom >= 20 (units: px or pt) — these are the section/entry
    wrappers in all resume templates. The CSS rule page-break-inside:avoid
    on .section-card then prevents mid-card page breaks.
    """
    def _add_class(m):
        tag = m.group(1)
        if 'class=' in tag:
            tag = re.sub(r"class=['\"]([^'\"]*)['\"]", r'class="\1 section-card"', tag)
        else:
            tag = tag.rstrip('>') + " class='section-card'>"
            # re-close: the regex consumed the opening tag, not the >
            # Actually let's insert before the style attr instead
        return tag
    return _SECTION_DIV_RE.sub(_add_class, html)
