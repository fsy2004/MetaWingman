"""Extract detailed figure design patterns from key papers."""
import fitz
import os

pdf_dir = r'C:\Users\fsy\Documents\Codex\MetaWingman\research\method-literature'

# Key papers to study for figure design
papers = {
    'ai-coscientist-2502.18864.pdf': 'Nature - Co-Scientist multi-agent',
    'metasyn-2606.17041.pdf': 'MetaSyn - SR/MA workflow + eval',
    'ai-scientist-2408.06292.pdf': 'AI Scientist - end-to-end pipeline',
    'setlur-prm-2410.08146.pdf': 'PRM - process verification',
    'test-time-compute-2408.03314.pdf': 'Test-time compute - scaling curves',
    'ideation-execution-gap-2506.20803.pdf': 'Ideation-execution - boxplots',
    'preflexor-npj.pdf': 'PreFLexOR - workflow (npj)',
    'llm-as-judge-2306.05685.pdf': 'LLM-as-Judge - bar charts',
    'openscholar-2412.01775.pdf': 'OpenScholar - RAG synthesis',
}

for fname, desc in papers.items():
    path = os.path.join(pdf_dir, fname)
    if not os.path.exists(path):
        continue
    doc = fitz.open(path)
    print(f"\n{'='*70}")
    print(f"PAPER: {desc} ({fname}, {len(doc)} pages)")
    print(f"{'='*70}")

    # Extract all figure captions with full text
    for page_num in range(min(len(doc), 30)):
        page = doc[page_num]
        text = page.get_text()
        lines = text.split('\n')
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if any(line_stripped.startswith(p) for p in ['Figure ', 'Fig. ', 'Fig ']):
                # Get full caption (next few lines)
                caption = line_stripped
                for j in range(i+1, min(i+5, len(lines))):
                    next_line = lines[j].strip()
                    if next_line and not next_line.startswith('Figure') and not next_line.startswith('Fig'):
                        caption += ' ' + next_line
                    else:
                        break
                print(f"  [p{page_num+1}] {caption[:250]}")

    # Also extract drawing info (vector graphics count per page)
    for page_num in range(min(len(doc), 15)):
        page = doc[page_num]
        drawings = page.get_drawings()
        n_rects = sum(1 for d in drawings if 'rect' in str(d.get('items', '')))
        n_curves = sum(1 for d in drawings if 'curve' in str(d.get('items', '')) or 'l' in str(d.get('items', '')))
        n_imgs = len(page.get_images())
        if n_imgs > 0 or len(drawings) > 20:
            print(f"  [page {page_num+1}] {len(drawings)} vector drawings, {n_imgs} images")

    doc.close()

print("\n\n=== FIGURE DESIGN PATTERNS SUMMARY ===")
print("""
Key patterns observed across top-venue papers:

1. ARCHITECTURE/FLOW DIAGRAMS (Fig 1 in most papers):
   - Multi-panel with labeled boxes and arrows
   - Use color coding for different components/stages
   - Include workflow steps as numbered/circular markers
   - Clean sans-serif fonts, minimal decoration

2. RESULTS PLOTS:
   - Bar charts with error bars (MetaSyn, LLM-as-Judge)
   - Box plots for distributions (ideation-execution)
   - Line plots with shaded confidence regions (test-time-compute)
   - Scatter plots for comparisons
   - Multi-panel layouts (a, b, c, d)

3. DESIGN CHARACTERISTICS:
   - Vector graphics (PDF/EPS)
   - Sans-serif fonts (Helvetica/Arial equivalent)
   - Small font sizes (7-8pt)
   - Minimal whitespace waste
   - Consistent color scheme across panels
   - Panel labels: bold lowercase (a, b, c) for Nature style
   - Color-coded legends, not oversized
   - Thin axis lines, tick marks pointing inward
""")
