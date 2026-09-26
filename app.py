import streamlit as st
import os
from pathlib import Path
st.set_page_config(page_title="Product Price AI", page_icon="🛁", layout="wide")

import fitz

st.sidebar.title("📚 Upload Books")
uploaded = st.sidebar.file_uploader("Drag & drop PDF price books", type=["pdf"], accept_multiple_files=True)

PDF_DIR="data"
os.makedirs(PDF_DIR, exist_ok=True)

if uploaded:
    for f in uploaded:
        with open(os.path.join(PDF_DIR, f.name),"wb") as o:
            o.write(f.getbuffer())
    st.sidebar.success(f"Added {len(uploaded)}")

pdfs=list(Path(PDF_DIR).glob("*.pdf"))
st.sidebar.write(f"Books: {len(pdfs)}")
for p in pdfs:
    st.sidebar.caption(f"• {p.name}")

if st.sidebar.button("🔄 Clear Cache & Refresh"):
    st.cache_data.clear()
    st.rerun()

st.title("🛁 Product Price AI")

query=st.text_input("🔍 Ask: blue counter basin, 110zp00, Catalano", placeholder="Type product code like 110zp00")

# Build fresh every time - no cache problem
index=[]
if pdfs:
    with st.spinner(f"Reading {len(pdfs)} books..."):
        for pdf_path in pdfs:
            try:
                doc=fitz.open(str(pdf_path))
                for i in range(len(doc)):
                    txt=doc[i].get_text()
                    if len(txt.strip())<20:
                        continue
                    # Search EVERY page, not only price pages
                    index.append({"book":pdf_path.name,"page":i+1,"text":txt,"search":txt.lower(),"path":str(pdf_path),"title":txt[:100].replace("\n"," ")})
                doc.close()
            except Exception as e:
                st.write(f"Error {pdf_path.name}: {e}")

st.write(f"Total pages indexed: {len(index)}")

if not query:
    st.info("👆 Type product code like '110zp00' or 'blue basin' and press Enter")
    st.stop()

q=query.lower().strip()
results=[]
for it in index:
    if q in it["search"]:
        results.append(it)
    elif all(w in it["search"] for w in q.split()):
        results.append(it)

results=results[:10]

if not results:
    st.error(f"No results for '{query}'. Try shorter: e.g. '110', 'Catalano', 'Baths'")
    st.stop()

st.success(f"Found {len(results)} pages for '{query}'")

if st.button(f"📑 Make Presentation PDF with {len(results)} pages", type="primary"):
    new_pdf=fitz.open()
    for it in results:
        try:
            src=fitz.open(it["path"])
            new_pdf.insert_pdf(src, from_page=it["page"]-1, to_page=it["page"]-1)
            src.close()
        except:
            pass
    out=f"Presentation_{query.replace(' ','_')}.pdf"
    new_pdf.save(out)
    new_pdf.close()
    with open(out,"rb") as f:
        st.download_button("⬇️ DOWNLOAD Presentation PDF", f, file_name=out, type="primary")

for idx,it in enumerate(results,1):
    with st.container(border=True):
        col1,col2=st.columns([1,1])
        with col1:
            st.markdown(f"**{idx}. Page {it['page']} - {it['book']}**")
            st.code(it["text"][:800])
            st.link_button("💬 Forward on WhatsApp", f"https://wa.me/?text={it['book']} Page {it['page']}: {it['title'][:100]}")
        with col2:
            try:
                doc=fitz.open(it["path"])
                pix=doc[it["page"]-1].get_pixmap(dpi=150)
                img=f"prev_{idx}.png"
                pix.save(img)
                st.image(img, caption=f"Exact Page Image - p.{it['page']}")
                doc.close()
            except Exception as e:
                st.write(e)
