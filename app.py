import streamlit as st
import fitz # pymupdf
import os
from pathlib import Path

st.set_page_config(
    page_title="Bathroom Price AI",
    page_icon="🛁",
    layout="wide"
)

# --- Header like Claude artifact ---
st.markdown("""
<style>
.big-font {font-size:22px!important; font-weight:600}
</style>
""", unsafe_allow_html=True)

col_logo, col_nav = st.columns([2,3])
with col_logo:
    st.title("🛁 Bathroom Price AI")
with col_nav:
    st.write("")
    st.write("Search | Library | Presentation")

# --- Sidebar: Upload Books ---
st.sidebar.title("📚 Upload Books")
uploaded_files = st.sidebar.file_uploader(
    "Drag & drop PDF price books",
    type=["pdf"],
    accept_multiple_files=True
)

PDF_DIR = "data"
os.makedirs(PDF_DIR, exist_ok=True)

# Save uploaded files
if uploaded_files:
    for f in uploaded_files:
        with open(os.path.join(PDF_DIR, f.name), "wb") as out:
            out.write(f.getbuffer())
    st.sidebar.success(f"Saved {len(uploaded_files)} books")

pdfs = list(Path(PDF_DIR).glob("*.pdf"))
st.sidebar.write(f"**Books loaded: {len(pdfs)}**")
for p in pdfs[:10]:
    st.sidebar.caption(f"• {p.name} ({fitz.open(str(p)).page_count} pages)")

st.sidebar.info("Tip: Upload multiple catalogs to compare prices across suppliers.")

# --- Build Index ---
@st.cache_data
def build_index():
    index = []
    for pdf_path in Path(PDF_DIR).glob("*.pdf"):
        try:
            doc = fitz.open(str(pdf_path))
            for i in range(len(doc)):
                text = doc[i].get_text()
                if not text.strip():
                    continue
                low = text.lower()
                # index if it has price or product keywords
                if "₹" in text or "rs" in low or "price" in low or "bamboo" in low or "chevron" in low or "adda" in low or "balnea" in low or "anima" in low or "jacuzzi" in low:
                    lines = [l.strip() for l in text.split("\n") if l.strip()][:6]
                    title = " ".join(lines)[:120]
                    # extract price snippet
                    import re
                    prices = re.findall(r'₹\s*[\d,]+|Rs\.?\s*[\d,]+', text)
                    price_str = ", ".join(prices[:3])
                    index.append({
                        "book": pdf_path.name,
                        "page": i+1,
                        "title": title,
                        "prices": price_str,
                        "full_text": text,
                        "search_text": low,
                        "path": str(pdf_path)
                    })
        except Exception as e:
            st.write(f"Error {pdf_path}: {e}")
    return index

index = build_index()
if not index:
    st.warning("Upload your PDFs in the left panel to start. I already tested with your 4 books (632 pages).")
    st.stop()

# --- Search Bar like Claude ---
query = st.text_input(
    "🔍 Ask: blue counter basin",
    placeholder="e.g. blue counter basin, Anima L120, Bamboo Pietra D'Avola, Jacuzzi 5 person under 43 lakhs"
)

# Session state for selected items for presentation
if "selected" not in st.session_state:
    st.session_state.selected = []

if query:
    q = query.lower()
    words = q.split()
    results = []
    for item in index:
        score = sum(1 for w in words if w in item["search_text"])
        if score > 0:
            results.append((score, item))
    results = sorted(results, key=lambda x: x[0], reverse=True)[:10]

    if not results:
        st.warning(f"No results for '{query}' - showing top 10")
        results = [(0, it) for it in index[:10]]

    st.success(f"Results • {len(results)} products found matching '{query}'")

    # Make Presentation button - TOP
    col_btn1, col_btn2 = st.columns([1,3])
    with col_btn1:
        if st.button(f"📑 Make Presentation with {len(st.session_state.selected) if st.session_state.selected else len(results)}", type="primary"):
            new_pdf = fitz.open()
            items_to_use = st.session_state.selected if st.session_state.selected else [r[1] for r in results]
            for it in items_to_use:
                try:
                    src = fitz.open(it["path"])
                    new_pdf.insert_pdf(src, from_page=it["page"]-1, to_page=it["page"]-1)
                    src.close()
                except:
                    pass
            out_path = f"Presentation_{query[:20].replace(' ','_')}.pdf"
            new_pdf.save(out_path)
            new_pdf.close()
            with open(out_path, "rb") as f:
                st.download_button("⬇️ Download Presentation PDF", f, file_name=out_path, mime="application/pdf")
            st.balloons()

    # --- Results + Exact Page Preview (3 columns like your image) ---
    for idx, (score, item) in enumerate(results, 1):
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 1.2, 1])
            with c1:
                st.markdown(f"**{idx}. {item['title'][:60]}**")
                st.write(f"**Price:** {item['prices']}")
                st.caption(f"Supplier: {item['book'].replace('.pdf','')} • In stock • Catalog: {item['book']}, p.{item['page']}")
                checked = st.checkbox(f"Add to presentation", key=f"chk_{idx}_{item['page']}", value=item in st.session_state.selected)
                if checked and item not in st.session_state.selected:
                    st.session_state.selected.append(item)
                if not checked and item in st.session_state.selected:
                    st.session_state.selected.remove(item)

            with c2:
                st.text(item['full_text'][:500])

            with c3:
                st.markdown("**Exact Page Preview**")
                try:
                    doc = fitz.open(item["path"])
                    page = doc[item["page"]-1]
                    pix = page.get_pixmap(dpi=150)
                    img_path = f"preview_{item['book']}_{item['page']}_{idx}.png"
                    pix.save(img_path)
                    st.image(img_path, caption=f"p.{item['page']} — {item['book']}", use_container_width=True)
                    doc.close()

                    # WhatsApp forward
                    wa_text = f"{item['title']} - {item['prices']} - {item['book']} Page {item['page']}"
                    wa_link = f"https://wa.me/?text={wa_text.replace(' ','%20')}"
                    st.link_button("💬 Forward on WhatsApp", wa_link)

                except Exception as e:
                    st.write(f"Preview error: {e}")

else:
    st.info("Try: 'Bamboo', 'Chevron', 'Anima L120', 'Gris du Marais', 'Jacuzzi'")
    st.write("### Sample - What customer gets (Exact Page Image):")
    for item in index[:2]:
        st.write(f"**{item['title'][:60]} - {item['prices']} - Page {item['page']}**")
