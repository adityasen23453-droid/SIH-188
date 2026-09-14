import os
import sys
import subprocess

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not os.path.exists(EDGE_PATH):
    EDGE_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

def render_pdf(html_path, pdf_path):
    print(f"Rendering {html_path} -> {pdf_path}...")
    cmd = [
        EDGE_PATH,
        "--headless=new",
        "--disable-gpu",
        "--run-all-compositor-stages-before-draw",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path}",
        html_path
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 1000:
        print(f"SUCCESS: Created {pdf_path} ({os.path.getsize(pdf_path):,} bytes)")
        return True
    else:
        print(f"ERROR: Failed to create {pdf_path}. Output: {res.stdout} {res.stderr}")
        return False

# Common CSS Stylesheet
COMMON_CSS = """
@page {
    size: A4;
    margin: 14mm 14mm 14mm 14mm;
    @bottom-right {
        content: counter(page);
    }
}
* {
    box-sizing: border-box;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
}
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #1e293b;
    background-color: #ffffff;
    line-height: 1.55;
    font-size: 9.8pt;
    margin: 0;
    padding: 0;
}
h1, h2, h3, h4, h5, h6 {
    color: #0f172a;
    font-weight: 700;
    line-height: 1.25;
    margin-top: 1.4em;
    margin-bottom: 0.5em;
    page-break-after: avoid;
}
h1 {
    font-size: 20pt;
    letter-spacing: -0.02em;
    border-bottom: 2px solid #e2e8f0;
    padding-bottom: 8px;
    margin-top: 0;
}
h2 {
    font-size: 14pt;
    color: #1e1b4b;
    border-bottom: 1.5px solid #cbd5e1;
    padding-bottom: 5px;
    margin-top: 1.6em;
}
h3 {
    font-size: 11.5pt;
    color: #2563eb;
    margin-top: 1.2em;
}
h4 {
    font-size: 10.5pt;
    color: #334155;
}
p {
    margin-top: 0.4em;
    margin-bottom: 0.8em;
}
ul, ol {
    margin-top: 0.3em;
    margin-bottom: 0.8em;
    padding-left: 20px;
}
li {
    margin-bottom: 0.3em;
}
table {
    width: 100%;
    border-collapse: collapse;
    margin: 1.2em 0;
    font-size: 8.8pt;
    page-break-inside: avoid;
}
th, td {
    padding: 7px 10px;
    border: 1px solid #cbd5e1;
    text-align: left;
    vertical-align: top;
}
th {
    background-color: #0f172a;
    color: #ffffff;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 7.8pt;
    letter-spacing: 0.05em;
}
tr:nth-child(even) td {
    background-color: #f8fafc;
}
code {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 8.5pt;
    background-color: #f1f5f9;
    padding: 2px 5px;
    border-radius: 4px;
    border: 1px solid #e2e8f0;
    color: #0f172a;
}
pre {
    background-color: #0f172a;
    color: #f8fafc;
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 8.5pt;
    overflow-x: auto;
    page-break-inside: avoid;
    line-height: 1.45;
}
pre code {
    background-color: transparent;
    color: inherit;
    border: none;
    padding: 0;
}
.header-banner {
    background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
    color: white;
    padding: 18px 22px;
    border-radius: 10px;
    margin-bottom: 22px;
    box-shadow: 0 4px 10px rgba(0,0,0,0.1);
}
.header-banner h1 {
    color: white;
    border-bottom: none;
    padding-bottom: 0;
    margin-bottom: 4px;
    font-size: 19pt;
}
.header-banner .meta {
    font-size: 9pt;
    color: #cbd5e1;
    font-family: ui-monospace, monospace;
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
    margin-top: 6px;
}
.header-banner .tag {
    background-color: #3b82f6;
    color: white;
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 700;
    font-size: 8pt;
}
.callout {
    border-left: 4px solid #3b82f6;
    background-color: #eff6ff;
    padding: 10px 14px;
    margin: 1em 0;
    border-radius: 0 8px 8px 0;
    font-size: 9.3pt;
}
.callout-warning {
    border-left-color: #f59e0b;
    background-color: #fffbeb;
}
.callout-danger {
    border-left-color: #ef4444;
    background-color: #fef2f2;
}
.callout-success {
    border-left-color: #10b981;
    background-color: #ecfdf5;
}
.callout-title {
    font-weight: 700;
    margin-bottom: 4px;
    color: #0f172a;
    font-size: 9.5pt;
    display: flex;
    align-items: center;
    gap: 6px;
}
.badge {
    display: inline-block;
    padding: 2px 6px;
    font-size: 7.5pt;
    font-weight: 700;
    border-radius: 4px;
    font-family: ui-monospace, monospace;
}
.badge-green { background-color: #d1fae5; color: #065f46; border: 1px solid #a7f3d0; }
.badge-blue { background-color: #dbeafe; color: #1e40af; border: 1px solid #bfdbfe; }
.badge-amber { background-color: #fef3c7; color: #92400e; border: 1px solid #fde68a; }
.badge-red { background-color: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
.badge-purple { background-color: #f3e8ff; color: #6b21a8; border: 1px solid #e9d5ff; }
.page-break {
    page-break-before: always;
}
.diagram-container {
    width: 100%;
    margin: 1.4em 0;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 12px;
    text-align: center;
    page-break-inside: avoid;
}
.diagram-caption {
    font-size: 8.5pt;
    font-weight: 600;
    color: #64748b;
    margin-top: 6px;
    text-align: center;
}
svg {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 0 auto;
}
"""

print("Writing document builders...")

