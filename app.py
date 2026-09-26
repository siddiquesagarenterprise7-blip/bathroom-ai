import streamlit as st
import os
from pathlib import Path
st.set_page_config(page_title="Bathroom Price AI", page_icon="🛁", layout="wide")

try:
    import fitz
    HAS_FITZ = True
except:
    HAS_FITZ = False

st.sidebar.title("📚 Upload Books")
uploaded_files = st.sidebar.file_uploader("Drag & drop PDF price books", type=["pdf"], accept_multiple_files=True)

PDF_DIR = "data"
os.makedirs(PDF_DIR, exist_ok=True)

if uploaded_files:
    for f in uploaded_files:
        with open(os.path.join(PDF_DIR, f.name), "wb") as out:
            out.write(f.getbuffer())
    st.sidebar.success(f"Saved {len(uploaded_files)} books - Refreshing...")
    st.rerun()

pdfs = list(Path(PDF_DIR).glob("*.pdf"))
st.sidebar.write(f"Books: {len(pdfs)}")
for p in pdfs:
    st.sidebar.caption(f"• {p.name}")

st.title("🛁 Bathroom Price AI")
query = st.text_input("🔍 Ask: blue counter basin", placeholder="e.g. Bamboo, Catalano, Anima L120")

if not HAS_FITZ:
    st.error("Fix requirements.txt to: streamlit and pymupdf")
    st.stop()

@st.cache_data
def build_index():
    index=[]
    for pdf_path in Path(PDF_DIR).glob("*.pdf"):
        try:
            doc = fitz.open(str(pdf_path))
            for i in range(len(doc)):
                text = doc[i].get_text()
                if len(text.strip()) < 10:
                    continue
                low=text.lower()
                if "₹" in text or "rs" in low or "price" in low or "eur" in low:
                    lines=[l.strip() for l in text.split("\n") if l.strip()][:4]
                    title=" ".join(lines)[:120]
                    index.append({"book":pdf_path.name,"page":i+1,"title":title,"text":text,"search":low,"path":str(pdf_path)})
        except:
            pass
    return index

index = build_index()

if not index:
    st.warning("👈 Upload PDFs from LEFT sidebar. After upload Books: 0 will become Books: 4")
    st.info("Once uploaded, search 'blue counter basin' and you will get Exact Page Image + Make Presentation button like Claude app but better.")
    st.stop()

if query:
    q=query.lower()
    results=[it for it in index if any(w in it["search"] for w in q.split())][:10]
    if not results:
        results=index[:10]
    st.success(f"Results • {len(results)} products found matching '{query}'")

    if st.button(f"📑 Make Presentation with {len(results)} pages", type="primary"):
        new_pdf=fitz.open()
        for it in results:
            try:
                src=fitz.open(it["path"])
                new_pdf.insert_pdf(src, from_page=it["page"]-1, to_page=it["page"]-1)
                src.close()
            except:
                pass
        out=f"Presentation_{query}.pdf"
        new_pdf.save(out)
        new_pdf.close()
        with open(out,"rb") as f:
            st.download_button("⬇️ Download Presentation PDF", f, file_name=out)

    for idx,it in enumerate(results,1):
        with st.container(border=True):
            c1,c2=st.columns([1,1])
            with c1:
                st.write(f"**{idx}. {it['title']}**")
                st.write(f"Page {it['page']} - {it['book']}")
                st.text(it["text"][:700])
                st.link_button("💬 Forward on WhatsApp", f"https://wa.me/?text={it['title'][:80]} Page {it['page']}")
            with c2:
                try:
                    doc=fitz.open(it["path"])
                    pix=doc[it["page"]-1].get_pixmap(dpi=150)
                    img=f"preview_{idx}.png"
                    pix.save(img)
                    st.image(img, caption=f"Exact Page Preview p.{it['page']} — {it['book']}")
                    doc.close()
                except Exception as e:
                    st.write(e)
else:
    st.info("Upload books from left sidebar, then search e.g. 'Bamboo', 'Catalano', 'Anima L120'")
