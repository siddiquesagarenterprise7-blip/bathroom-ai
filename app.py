import streamlit as st
import base64, json, io, requests
import fitz
from github import Github

st.set_page_config(page_title="Bathroom AI - NO RATE LIMIT", layout="wide")
st.markdown("""
<style>
div[data-baseweb="input"] input {font-size:22px!important; height:52px!important; font-weight:700!important;}
.stButton button {height:50px!important; font-size:15px!important;}
</style>
""", unsafe_allow_html=True)

try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    GITHUB_REPO_NAME = st.secrets["GITHUB_REPO"]
except: st.stop()

@st.cache_resource
def get_repo(): return Github(GITHUB_TOKEN).get_repo(GITHUB_REPO_NAME)
repo = get_repo()

def get_json_file(p,d):
    try:
        f=repo.get_contents(p)
        c=base64.b64decode(f.content).decode('utf-8').strip()
        return (json.loads(c), f.sha) if c else (d, f.sha)
    except: return d, None

def save_json_file(p,data,sha,msg):
    content=json.dumps(data, indent=2, ensure_ascii=False)
    try:
        if sha: repo.update_file(p,msg,content,sha)
        else:
            try: ex=repo.get_contents(p); repo.update_file(p,msg,content,ex.sha)
            except: repo.create_file(p,msg,content)
        st.cache_data.clear()
    except: pass

def get_or_create_release():
    try:
        for r in repo.get_releases():
            if r.tag_name=="pdfs-storage": return r
        return repo.create_git_release(tag="pdfs-storage", name="PDF Storage", message="storage", draft=False, prerelease=False)
    except: return None

def get_all_pdfs():
    files=[]
    try:
        headers={"Authorization": f"token {GITHUB_TOKEN}"}
        r=requests.get(f"https://api.github.com/repos/{GITHUB_REPO_NAME}/releases/tags/pdfs-storage", headers=headers, timeout=30)
        if r.status_code==200:
            for ast in r.json().get("assets",[]):
                nm=ast.get("name","")
                if nm.lower().endswith(".pdf") and nm not in files: files.append(nm)
    except: pass
    return files

# FIXED - NO AUTO PRELOAD, LOAD ON DEMAND ONLY
@st.cache_data(ttl=3600, show_spinner=True)
def get_pdf_bytes_cached(fname):
    try:
        headers={"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        r=requests.get(f"https://api.github.com/repos/{GITHUB_REPO_NAME}/releases/tags/pdfs-storage", headers=headers, timeout=60)
        if r.status_code==200:
            for ast in r.json().get("assets",[]):
                if ast.get("name")==fname:
                    asset_id=ast.get("id")
                    # Method 1: API asset download
                    dl_headers={"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/octet-stream"}
                    dl_url=f"https://api.github.com/repos/{GITHUB_REPO_NAME}/releases/assets/{asset_id}"
                    dr=requests.get(dl_url, headers=dl_headers, timeout=300, allow_redirects=True, stream=True)
                    if dr.status_code==200:
                        content=b"".join(dr.iter_content(chunk_size=8192))
                        if len(content)>5000: return content
                    # Method 2: browser URL
                    try:
                        br_url=ast.get("browser_download_url")
                        dr2=requests.get(br_url, headers={"Authorization": f"token {GITHUB_TOKEN}"}, timeout=300, allow_redirects=True, stream=True)
                        if dr2.status_code==200:
                            content=b"".join(dr2.iter_content(chunk_size=8192))
                            if len(content)>5000: return content
                    except: pass
    except Exception as e:
        st.error(f"Load error {fname}: {e}")
    return None

@st.cache_data(ttl=3600, show_spinner=True)
def get_page_image_cached(fname, page_no):
    pb=get_pdf_bytes_cached(fname)
    if not pb: return None
    try:
        doc=fitz.open(stream=pb, filetype="pdf")
        pix=doc.load_page(page_no-1).get_pixmap(dpi=100, alpha=False)
        b=pix.tobytes("png")
        doc.close()
        return b
    except: return None

def search_fast(fname, query):
    pb=get_pdf_bytes_cached(fname)
    if not pb: return []
    words=[w.lower() for w in query.replace("_"," ").split() if w.strip()][:4]
    res=[]
    try:
        doc=fitz.open(stream=pb, filetype="pdf")
        for i in range(len(doc)):
            txt=doc.load_page(i).get_text("text").lower()
            if any(w in txt for w in words) or query.lower() in txt:
                res.append((i+1, 1, words))
        doc.close()
    except: pass
    return res

if "selected" not in st.session_state: st.session_state.selected=[]
if "last_results" not in st.session_state: st.session_state.last_results=[]
if "presentation_images" not in st.session_state: st.session_state.presentation_images={}
if "page_num" not in st.session_state: st.session_state.page_num=1
if "presentation_pdf" not in st.session_state: st.session_state.presentation_pdf=None
if "customer_verified" not in st.session_state: st.session_state.customer_verified=False
if "is_admin" not in st.session_state: st.session_state.is_admin=False

if not st.session_state.customer_verified:
    st.title("Login")
    pwd=st.text_input("Admin Password", type="password")
    if st.button("Login as Admin", type="primary"):
        if pwd==st.secrets.get("ADMIN_PASSWORD","Bathroom@123"):
            st.session_state.is_admin=True; st.session_state.customer_verified=True; st.rerun()
    st.stop()

st.title("Pricelist Search")
brands,_=get_json_file("data/brands.json", ["Fantini","Gessi","Antoniolupi","Catalano","FALPER"])
s1,s2,s3=st.columns([1,2,1])
with s1: brand=st.selectbox("Brand", ["All Brands"]+brands)
with s2: query=st.text_input("Search Pricelist", placeholder="BREEZE", value="BREEZE")
with s3:
    st.write(""); st.write("")
    do_search=st.button("🔍 SEARCH ALL MATCHES", type="primary", use_container_width=True)

if do_search:
    allowed=get_all_pdfs()
    filt=[f for f in allowed if brand.lower() in f.lower()] if brand!="All Brands" else allowed
    if not filt: filt=allowed
    final=[]; prog=st.progress(0, text="Searching...")
    for idx,fn in enumerate(filt):
        pages=search_fast(fn, query)
        for pno,cnt,matched in pages: final.append((fn,pno,cnt,matched))
        prog.progress((idx+1)/len(filt))
    prog.empty()
    st.session_state.last_results=final; st.session_state.page_num=1; st.rerun()

tab_search, tab_pricelist, tab_basket, tab_admin = st.tabs(["🔍 Search Results", "📚 PRICE LIST", "🧺 Basket", "👑 Admin"])

with tab_search:
    if not st.session_state.last_results:
        st.info("Click SEARCH - 6 per page")
    else:
        results=st.session_state.last_results
        st.success(f"Found {len(results)} pages")
        pg=st.session_state.page_num; ps=6; total=(len(results)+ps-1)//ps
        if total>1:
            c1,c2,c3=st.columns([1,2,1])
            with c1:
                if st.button("⬅️ Previous", disabled=pg==1, key="prev_s"): st.session_state.page_num-=1; st.rerun()
            with c2: st.markdown(f"<div style='text-align:center;padding:10px;background:#1f2937;border-radius:8px'>Page {pg}/{total}</div>", unsafe_allow_html=True)
            with c3:
                if st.button("Next ➡️", disabled=pg==total, key="next_s", type="primary"): st.session_state.page_num+=1; st.rerun()
        display=results[(pg-1)*ps: pg*ps]
        cols=st.columns(3)
        for idx,(fn,pn,cnt,matched) in enumerate(display):
            with cols[idx%3]:
                with st.container(border=True):
                    img=get_page_image_cached(fn,pn)
                    if img: st.image(img, use_container_width=True)
                    else: st.warning(f"P{pn} - Load in PRICE LIST tab first")
                    st.write(f"P{pn} {fn[:18]}")
                    if st.checkbox("Add to Basket", key=f"chk_{fn}_{pn}_{idx}_{pg}", value=(fn,pn) in st.session_state.selected):
                        if (fn,pn) not in st.session_state.selected: st.session_state.selected.append((fn,pn)); st.session_state.presentation_images[f"{fn}_{pn}"]=img
                    else:
                        if (fn,pn) in st.session_state.selected: st.session_state.selected.remove((fn,pn))

with tab_pricelist:
    st.markdown("### 📚 All Pricelists - Maximise when needed")
    st.info("⚠️ Click Load only for file you need - Prevents rate limit - After Load, images will work in Search tab")
    files=get_all_pdfs()
    cols=st.columns(3)
    for idx,fn in enumerate(files):
        with cols[idx%3]:
            with st.container(border=True):
                st.write(f"**{fn}**")
                # NO AUTO LOAD - ONLY SHOW BUTTONS
                if st.button("🔄 Load & Preview Page 1", key=f"load_{fn}_{idx}", type="primary", use_container_width=True):
                    with st.spinner(f"Loading {fn}... 10-20 sec for 100MB"):
                        pb=get_pdf_bytes_cached(fn)
                        if pb:
                            st.success(f"✅ {len(pb)/1024/1024:.1f}MB Loaded")
                            img=get_page_image_cached(fn,1)
                            if img: st.image(img, use_container_width=True)
                        else:
                            st.error("❌ Failed - Click again or Clear Cache")
                if st.button("👁️ View Page 1", key=f"view_{fn}_{idx}", use_container_width=True):
                    img=get_page_image_cached(fn,1)
                    if img: st.image(img, use_container_width=True)
                    else: st.error("Click Load first")
                # Download button - loads on click
                if st.button("📥 Download File", key=f"dlbtn_{fn}_{idx}", use_container_width=True):
                    pb=get_pdf_bytes_cached(fn)
                    if pb:
                        st.download_button("💾 Save to Downloads", data=pb, file_name=fn, mime="application/pdf", key=f"dl_{fn}_{idx}", use_container_width=True, type="primary")
                    else:
                        st.error("Load first")

with tab_basket:
    st.markdown(f"### 🧺 Basket: {len(st.session_state.selected)}")
    if st.session_state.selected:
        cols=st.columns(4)
        for idx,(fn,pn) in enumerate(st.session_state.selected):
            with cols[idx%4]:
                ib=st.session_state.presentation_images.get(f"{fn}_{pn}")
                if ib: st.image(ib, use_container_width=True)
                if st.button("❌", key=f"rem_{fn}_{pn}_{idx}"): st.session_state.selected.remove((fn,pn)); st.rerun()
        if st.button(f"📑 Create PDF ({len(st.session_state.selected)})", type="primary", use_container_width=True):
            nd=fitz.open()
            for fn,pn in st.session_state.selected:
                pb=get_pdf_bytes_cached(fn)
                if pb:
                    src=fitz.open(stream=pb, filetype="pdf"); nd.insert_pdf(src, from_page=pn-1, to_page=pn-1); src.close()
            st.session_state.presentation_pdf=nd.tobytes(); nd.close(); st.rerun()
        if st.session_state.presentation_pdf:
            st.download_button("📥 Download Presentation.pdf", data=st.session_state.presentation_pdf, file_name="Presentation.pdf", mime="application/pdf", use_container_width=True, type="primary")

with tab_admin:
    st.markdown("### Upload")
    ups=st.file_uploader("Choose PDFs", type=["pdf"], accept_multiple_files=True)
    if st.button("⬆️ Upload", type="primary", use_container_width=True):
        rel=get_or_create_release()
        for f in ups:
            safe=f.name.replace(" ","_")
            fb=f.getvalue()
            try:
                for a in rel.get_assets():
                    if a.name==safe:
                        try: a.delete_asset()
                        except: pass
                rel.upload_asset_from_memory(io.BytesIO(fb), len(fb), safe, "application/pdf")
                st.success(f"✅ {safe}")
            except Exception as e: st.error(f"{safe}: {e}")
        st.cache_data.clear(); st.rerun()
    if st.button("🧹 Clear Cache", use_container_width=True, type="primary"):
        st.cache_data.clear(); st.cache_resource.clear(); st.rerun()
