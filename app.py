import streamlit as st
import os
from pathlib import Path

st.set_page_config(page_title="Bathroom Price AI", page_icon="🛁", layout="wide")
st.title("🛁 Bathroom Price AI")

try:
    import fitz
    HAS_FITZ = True
except:
    HAS_FITZ = False
    st.warning("Installing viewer... please use requirements: pymupdf")

PDF_DIR = "data"
os.makedirs(PDF_DIR, exist_ok=True)

pdfs = list(Path(PDF_DIR).glob("*.pdf"))
st.sidebar.write(f"Books: {len(pdfs)}")

@st.cache_data
def build_index():
    index=[]
    for pdf_path in Path(PDF_DIR).glob("*.pdf"):
        if not HAS_FITZ:
            continue
        doc = fitz.open(str(pdf_path))
        for i in range(len(doc)):
            text = doc[i].get_text()
            low = text.lower()
            if "₹" in text or "rs" in low:
                lines=[l.strip() for l in text.split("\n") if l.strip()][:4]
                title=" ".join(lines)[:100]
                index.append({"book":pdf_path.name,"page":i+1,"title":title,"text":text,"search":low,"path":str(pdf_path)})
    return index

index = build_index()

query = st.text_input("🔍 Ask: blue counter basin")

if query and HAS_FITZ:
    q=query.lower()
    results=[it for it in index if any(w in it["search"] for w in q.split())][:10]
    st.success(f"Found {len(results)} - Each with Exact Page Image")

    if st.button(f"📑 Make Presentation with {len(results)}"):
        new_pdf=fitz.open()
        for it in results:
            src=fitz.open(it["path"])
            new_pdf.insert_pdf(src, from_page=it["page"]-1, to_page=it["page"]-1)
            src.close()
        out="Presentation.pdf"
        new_pdf.save(out)
        new_pdf.close()
        with open(out,"rb") as f:
            st.download_button("⬇️ Download", f, file_name=out)

    for idx,it in enumerate(results,1):
        with st.container(border=True):
            c1,c2=st.columns([1,1])
            with c1:
                st.write(f"**{it['title']}**")
                st.write(f"Page {it['page']} - {it['book']}")
                st.text(it["text"][:600])
            with c2:
                doc=fitz.open(it["path"])
                pix=doc[it["page"]-1].get_pixmap(dpi=150)
                img=f"p_{idx}.png"
                pix.save(img)
                st.image(img, caption=f"Exact Page {it['page']} - Forward on WhatsApp")
                st.link_button("💬 Forward on WhatsApp", f"https://wa.me/?text={it['title'][:50]}")
