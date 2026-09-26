import streamlit as st
import os, fitz
from pathlib import Path

st.set_page_config(page_title="Product and Price Finder", page_icon="🔍", layout="wide")
st.title("🔍 Product and Price Finder")
st.caption("Text + Image Search + Presentation + WhatsApp")

PDF_DIR = "data"
os.makedirs(PDF_DIR, exist_ok=True)

# --- SIDEBAR ---
st.sidebar.title("📚 Books")
uploaded = st.sidebar.file_uploader("Upload PDF price books", type=["pdf"], accept_multiple_files=True)

if uploaded:
    for f in uploaded:
        with open(os.path.join(PDF_DIR, f.name), "wb") as out:
            out.write(f.getbuffer())
    st.sidebar.success(f"Saved {len(uploaded)} books")
    st.cache_data.clear()

pdfs = list(Path(PDF_DIR).glob("*.pdf"))
st.sidebar.write(f"Books: {len(pdfs)}")
for p in pdfs:
    st.sidebar.caption(f"• {p.name} ({p.stat().st_size // 1024} KB)")

if st.sidebar.button("🔄 Clear Cache & Refresh"):
    st.cache_data.clear()
    st.rerun()

# --- INDEX ---
@st.cache_data(show_spinner="Reading 8 books...")
def build_index():
    all_pages = []
    for pdf_path in pdfs:
        try:
            doc = fitz.open(str(pdf_path))
            for i in range(len(doc)):
                txt = doc[i].get_text("text")
                if len(txt.strip()) < 10:
                    txt = f"Catalog page {i+1} - {pdf_path.name}"
                all_pages.append({
                    "book": pdf_path.name,
                    "page": i+1,
                    "text": txt,
                    "search": (pdf_path.name + " " + txt).lower(),
                    "path": str(pdf_path)
                })
            doc.close()
        except Exception as e:
            print(e)
    return all_pages

pages = build_index()
st.write(f"**Total pages indexed: {len(pages)}**")

# --- SEARCH ---
query = st.text_input("🔍 Ask: zero, catalano, blue basin, 110zp00", placeholder="Type single word like zero")

if not query:
    st.info("👆 Upload 8 books done. Now type e.g. `zero` or `catalano` and press Enter to see exact page image.")
    st.stop()

q = query.lower().strip()
words = q.replace(",", " ").split()

# Fuzzy search - ANY word match
results = []
for p in pages:
    for w in words:
        if w in p["search"]:
            results.append(p)
            break

results = results[:20]

if not results:
    st.error(f"Found 0 for '{query}'. Try single word: zero, wc, catalano, bamboo")
    st.stop()

st.success(f"Found {len(results)} pages for '{query}'")

# Make presentation
if st.button(f"📑 Make Presentation PDF with {len(results)} pages", type="primary"):
    new_pdf = fitz.open()
    for it in results:
        try:
            src = fitz.open(it["path"])
            new_pdf.insert_pdf(src, from_page=it["page"]-1, to_page=it["page"]-1)
            src.close()
        except:
            pass
    out = f"Presentation_{q.replace(' ','_')}.pdf"
    new_pdf.save(out)
    new_pdf.close()
    with open(out, "rb") as f:
        st.download_button("⬇️ DOWNLOAD Presentation PDF", f, file_name=out, type="primary")

# Show results with EXACT PAGE IMAGE
for idx, it in enumerate(results, 1):
    with st.container(border=True):
        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown(f"**{idx}. {it['book']} - Page {it['page']}**")
            st.text(it["text"][:800])
            wa_text = f"{it['book']} Page {it['page']} - {query}"
            st.link_button("💬 Forward on WhatsApp", f"https://wa.me/?text={wa_text}")
        with col2:
            try:
                doc = fitz.open(it["path"])
                pix = doc[it["page"]-1].get_pixmap(dpi=170)
                img_name = f"preview_{idx}.png"
                pix.save(img_name)
                st.image(img_name, caption=f"Exact Page Image - p.{it['page']}")
                doc.close()
            except Exception as e:
                st.write(f"Preview error: {e}")
