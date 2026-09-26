import streamlit as st, os, fitz
from pathlib import Path
st.set_page_config(page_title="Product and Price Finder", page_icon="🔍", layout="wide")
st.title("🔍 Product and Price Finder")

PDF_DIR="data"
os.makedirs(PDF_DIR, exist_ok=True)

st.sidebar.title("📚 Books")
up=st.sidebar.file_uploader("Upload PDF price books", type=["pdf"], accept_multiple_files=True)
if up:
    for f in up:
        open(os.path.join(PDF_DIR,f.name),"wb").write(f.getbuffer())
    st.sidebar.success("Saved!")

pdfs=list(Path(PDF_DIR).glob("*.pdf"))
st.sidebar.write(f"Books: {len(pdfs)}")
for p in pdfs:
    st.sidebar.caption(f"• {p.name}")

if st.sidebar.button("🔄 Clear & Refresh"):
    st.cache_data.clear()
    st.rerun()

@st.cache_data
def get_pages():
    pages=[]
    for pdf_path in pdfs:
        try:
            doc=fitz.open(str(pdf_path))
            for i in range(len(doc)):
                txt=doc[i].get_text()
                if len(txt.strip())>20:
                    pages.append({"book":pdf_path.name,"page":i+1,"text":txt,"low":txt.lower(),"path":str(pdf_path)})
            doc.close()
        except:
            pass
    return pages

pages=get_pages()
st.write(f"Total pages: {len(pages)}")

query=st.text_input("Ask: blue basin, zero wc, catalano, 110zp00", placeholder="Type here e.g. zero")

if query:
    q=query.lower()
    words=q.split()
    # OLD LOGIC BUT FIXED: match ANY word
    results=[]
    for p in pages:
        for w in words:
            if w in p["low"]:
                results.append(p)
                break
    results=results[:15]

    st.success(f"Found {len(results)} for '{query}'")

    for idx,it in enumerate(results,1):
        with st.container(border=True):
            c1,c2=st.columns([1,1])
            with c1:
                st.write(f"**{idx}. {it['book']} - Page {it['page']}**")
                st.text(it["text"][:800])
                st.link_button("💬 WhatsApp", f"https://wa.me/?text={it['book']} Page {it['page']}")
            with c2:
                doc=fitz.open(it["path"])
                pix=doc[it["page"]-1].get_pixmap(dpi=160)
                pix.save(f"p{idx}.png")
                st.image(f"p{idx}.png", caption=f"Exact Page p.{it['page']}")
                doc.close()
