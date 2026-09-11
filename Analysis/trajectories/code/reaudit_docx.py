r"""reaudit_docx.py -- extract full text of the three H-report docx and dump it so
the auditor can search for the noise-floor discussion, H3 direction language,
k-rule note, placeholder tokens, and spot-check numbers."""
import os, zipfile, re, sys

BASE = r"C:\Projects\Repos\Mouse Arena\Analysis\trajectories\reports"
FILES = {
    "H1": "H1 - encounters vs tortuosity.docx",
    "H2": "H2 - alignment vs distance.docx",
    "H3": "H3 - peri-contact reorientation.docx",
}

def docx_text(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    # paragraph breaks
    xml = xml.replace("</w:p>", "\n")
    # text runs
    texts = re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml, flags=re.S)
    # Reconstruct by stripping tags overall as fallback join
    txt = re.sub(r"<[^>]+>", "", xml)
    # unescape
    for a,b in [("&amp;","&"),("&lt;","<"),("&gt;",">"),("&quot;",'"'),("&apos;","'")]:
        txt = txt.replace(a,b)
    return txt

PLACEHOLDERS = ["TODO","TBD","FIXME","XXX","PLACEHOLDER","<INSERT","{{","}}","<FILL","N/A_PLACEHOLDER","lorem ipsum","<value>","<num>","XX.X","NN.N","???"]

for tag, fn in FILES.items():
    p = os.path.join(BASE, fn)
    t = docx_text(p)
    print("="*80)
    print("FILE:", tag, fn, " len=", len(t))
    print("="*80)
    print(t)
    print()
    print("--- placeholder scan ---")
    low = t.lower()
    hits = [ph for ph in PLACEHOLDERS if ph.lower() in low]
    print("placeholder hits:", hits if hits else "NONE")
    # raw '<' occurrences with context
    for m in re.finditer(r".{0,15}<.{0,15}", t):
        print("  '<' ctx:", repr(m.group(0)))
    print()
