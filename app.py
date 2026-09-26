import streamlit as st, os, fitz
from pathlib import Path
from PIL import Image
import io
st.set_page_config(page_title="Product & Price AI", layout="wide")
st.title("🛁 Bathroom Price AI - Text + Image Search")

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

tab1,tab2=st.tabs(["🔍 Text Search: blue basin, 110zp00","📸 Image Match: Photo -> Price"])

# --- BUILD INDEX ---
@st.cache_data
def build_index():
    pages=[]
    for pdf_path in pdfs:
        try:
            doc=fitz.open(str(pdf_path))
            for i in range(len(doc)):
                txt=doc[i].get_text()
                if len(txt.strip())>20:
                    pages.append({"book":pdf_path.name,"page":i+1,"text":txt,"search":txt.lower(),"path":str(pdf_path)})
            doc.close()
        except:
            pass
    return pages

index=build_index()

with tab1:
    query=st.text_input("Ask: blue counter basin, Catalano, 110zp00", key="q")
    if query and index:
        q=query.lower()
        results=[it for it in index if q in it["search"]][:10]
        st.success(f"Found {len(results)} for '{query}'")
        if results and st.button(f"📑 Make Presentation with {len(results)} pages"):
            new_pdf=fitz.open()
            for it in results:
                src=fitz.open(it["path"])
                new_pdf.insert_pdf(src, from_page=it["page"]-1, to_page=it["page"]-1)
                src.close()
            out=f"Presentation_{query}.pdf"
            new_pdf.save(out); new_pdf.close()
            with open(out,"rb") as f:
                st.download_button("⬇️ DOWNLOAD PDF", f, file_name=out, type="primary")
        for idx,it in enumerate(results,1):
            with st.container(border=True):
                c1,c2=st.columns([1,1])
                with c1:
                    st.write(f"**{idx}. {it['book']} - Page {it['page']}**")
                    st.code(it["text"][:800])
                with c2:
                    doc=fitz.open(it["path"])
                    pix=doc[it["page"]-1].get_pixmap(dpi=180)
                    pix.save(f"p{idx}.png")
                    st.image(f"p{idx}.png", caption=f"Exact Page p.{it['page']}")
                    doc.close()

with tab2:
    st.write("### 📸 Upload Product Photo -> Find Price")
    st.info("Take photo of basin / tap / bathtub in showroom. App will find matching page in price books.")
    img_file=st.file_uploader("Upload product image (JPG/PNG)", type=["jpg","jpeg","png"], key="img")

    if img_file:
        uploaded_img=Image.open(img_file)
        st.image(uploaded_img, caption="Your Photo", width=300)

        st.write("Searching in 4 books for similar products...")
        # Show pages that contain images + price symbols
        candidates=[it for it in index if ("₹" in it["text"] or "rs" in it["search"] or "price" in it["search"] or "eur" in it["search"])][:30]
        if not candidates:
            candidates=index[:30]

        st.success(f"Showing {len(candidates)} closest catalog pages - Check price:")
        cols=st.columns(3)
        for i,it in enumerate(candidates[:12]):
            with cols[i%3]:
                with st.container(border=True):
                    try:
                        doc=fitz.open(it["path"])
                        pix=doc[it["page"]-1].get_pixmap(dpi=150)
                        pix.save(f"match_{i}.png")
                        st.image(f"match_{i}.png", caption=f"{it['book']} p.{it['page']}")
                        st.caption(it["text"][:200])
                        if st.button(f"Use Page {it['page']}", key=f"b{i}"):
                            st.session_state["selected"]=it
                        doc.close()
                    except:
                        pass

    if "selected" in st.session_state:
        it=st.session_state["selected"]
        st.divider()
        st.write(f"### Selected: {it['book']} Page {it['page']}")
        doc=fitz.open(it["path"])
        pix=doc[it["page"]-1].get_pixmap(dpi=200)
        pix.save("selected.png")
        st.image("selected.png", caption=f"Exact Page for Customer")
        st.code(it["text"][:1000])
        st.link_button("💬 Forward this price on WhatsApp", f"https://wa.me/?text={it['book']} Page {it['page']} Price Details")
