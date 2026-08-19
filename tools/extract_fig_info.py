"""Extract figure metadata from literature PDFs."""
import fitz
import os

pdf_dir = r'C:\Users\fsy\Documents\Codex\MetaWingman\research\method-literature'
for f in sorted(os.listdir(pdf_dir)):
    if not f.endswith('.pdf'):
        continue
    path = os.path.join(pdf_dir, f)
    try:
        doc = fitz.open(path)
        n_pages = len(doc)
        n_imgs = 0
        fig_captions = []
        for page in doc:
            n_imgs += len(page.get_images())
            text = page.get_text()
            for line in text.split('\n'):
                line = line.strip()
                if line.startswith('Figure ') or line.startswith('Fig. ') or line.startswith('Fig '):
                    fig_captions.append(line[:180])
        doc.close()
        print(f"--- {f} ({n_pages} pages, {n_imgs} images)")
        for cap in fig_captions[:6]:
            print(f"  {cap}")
        print()
    except Exception as e:
        print(f"--- {f}: ERROR {e}")
