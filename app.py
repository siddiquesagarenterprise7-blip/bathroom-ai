import streamlit as st
import base64, json, io, requests
import fitz
from github import Github

st.set_page_config(page_title="Bathroom AI - BREEZE FIX", layout="wide")

st.markdown("""
<style>
div[data-baseweb="input"] input {font-size:22px!important; height:52px!important; font-weight:700!important;}
.stButton button {height:52px!important; font-size:18px!important;}
</style>
""", unsafe_allow_html=True)

try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    GITHUB_REPO_NAME = st.secrets["GITHUB_REPO"]
    ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "Bathroom@123")
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
        for c in repo.get_contents("pdfs"):
            if c.name.lower().endswith(".pdf"): files.append(c.name)
    except: pass
    try:
        rel=get_or_create_release()
        if rel:
            for a in rel.get_assets():
                if a.name.lower().endswith(".pdf") and a.name not in files: files.append(a.name)
    except: pass
    return files

@st.cache_data(ttl=3600, show_spinner=False)
def get_pdf_bytes_cached(fname):
    try:
        fc=repo.get_contents(f"pdfs/{fname}")
        return base64.b64decode(fc.content)
    except: pass
    try:
        rel=get_or_create_release()
        if rel:
            for a in rel.get_assets():
                if a.name==fname:
                    for hdr in [{"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/octet-stream"}, {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/octet-stream"}, {"Authorization": f"token {GITHUB_TOKEN}"}]:
                        try:
                            r=requests.get(a.url if "octet" in hdr["Accept"] else a.browser_download_url, headers=hdr, timeout=180, allow_redirects=True)
                            if r.status_code==200 and len(r.content)>5000: return r.content
                        except: pass
                    try:
                        r=requests.get(a.browser_download_url, timeout=180)
                        if r.status_code==200 and len(r.content)>5000: return r.content
                    except: pass
    except: pass
    return None

@st.cache_data(ttl=3600, show_spinner=False)
def get_page_image_cached(fname, page_no):
    pb=get_pdf_bytes_cached(fname)
    if not pb: return None
    try:
        doc=fitz.open(stream=pb, filetype="pdf")
        pix=doc.load_page(page_no-1).get_pixmap(dpi=110, alpha=False) # Higher DPI for your BREEZE image clarity
        b=pix.tobytes("png")
        doc.close()
        return b
    except: return None

def search_fast(fname, query):
    pb=get_pdf_bytes_cached(fname)
    if not pb: return []
    words=[w.lower() for w in query.replace("_"," ").split() if w.strip()][:4]
    if not words: return []
    res=[]
    try:
        doc=fitz.open(stream=pb, filetype="pdf")
        for i in range(len(doc)):
            txt=doc.load_page(i).get_text("text").lower()
            # Also search in case BREEZE_STONE written as BREEZE STONE
            if any(w in txt for w in words) or "breeze" in txt:
                matched=[w for w in words if w in txt]
                if not matched and "breeze" in txt: matched=["breeze"]
                res.append((i+1, len(matched), matched))
        doc.close()
    except: pass
    return res

def get_allowed_files(mail, is_admin):
    allf=get_all_pdfs()
    if is_admin: return allf
    access,_=get_json_file("data/file_access.json", {})
    return [f for f in allf if "all" in access.get(f,["all"]) or mail.lower() in [x.lower() for x in access.get(f,[])]]

if "customer_verified" not in st.session_state: st.session_state.customer_verified=False
if "is_admin" not in st.session_state: st.session_state.is_admin=False
if "customer_email" not in st.session_state: st.session_state.customer_email=""
if "selected" not in st.session_state: st.session_state.selected=[]
if "last_results" not in st.session_state: st.session_state.last_results=[]
if "presentation_images" not in st.session_state: st.session_state.presentation_images={}
if "page_num" not in st.session_state: st.session_state.page_num=1
if "presentation_pdf" not in st.session_state: st.session_state.presentation_pdf=None

if not st.session_state.customer_verified and not st.session_state.is_admin:
    st.title("🛁 Pricelist Login")
    t1,t2=st.tabs(["Customer","Admin"])
    with t2:
        pwd=st.text_input("Admin Password", type="password")
        if st.button("Login as Admin", type="primary", use_container_width=True):
            if pwd==st.secrets.get("ADMIN_PASSWORD","Bathroom@123"):
                st.session_state.is_admin=True; st.session_state.customer_verified=True; st.rerun()
    with t1:
        mail=st.text_input("Mail ID")
        if st.button("Login"):
            cust,_=get_json_file("data/customers.json", [])
            f=next((c for c in cust if c.get("mail","").lower()==mail.lower().strip()), None)
            if f and f.get("approved"): st.session_state.customer_verified=True; st.session_state.customer_email=mail; st.rerun()
            else: st.error("Not found")
    st.stop()

st.title("Pricelist Search")
c1,c2=st.columns([3,1])
with c1: st.write(f"Login: {st.session_state.customer_email if not st.session_state.is_admin else 'Admin'}")
with c2:
    if st.button("Logout", use_container_width=True): st.session_state.customer_verified=False; st.session_state.is_admin=False; st.session_state.last_results=[]; st.session_state.selected=[]; st.rerun()

brands,_=get_json_file("data/brands.json", ["Fantini","Gessi","Antoniolupi","Catalano"])
s1,s2,s3=st.columns([1,2,1])
with s1: brand=st.selectbox("Brand", ["All Brands"]+brands)
with s2: query=st.text_input("Search Pricelist", placeholder="BREEZE", value="BREEZE")
with s3: 
    st.write(""); st.write("")
    do_search=st.button("🔍 SEARCH ALL MATCHES", type="primary", use_container_width=True)

if st.session_state.selected:
    st.divider()
    st.markdown(f"### 🧺 Basket: {len(st.session_state.selected)}")
    cols=st.columns(min(6, len(st.session_state.selected)))
    for idx,(fn,pn) in enumerate(st.session_state.selected):
        with cols[idx%6]:
            ib=st.session_state.presentation_images.get(f"{fn}_{pn}")
            if ib: st.image(ib, use_container_width=True)
            st.caption(f"P{pn}")
            if st.button("❌", key=f"rem_{fn}_{pn}_{idx}"): 
                st.session_state.selected.remove((fn,pn)); st.session_state.presentation_pdf=None; st.rerun()
    if st.button(f"📑 Create PDF ({len(st.session_state.selected)})", type="primary", use_container_width=True):
        nd=fitz.open()
        for fn,pn in st.session_state.selected:
            pb=get_pdf_bytes_cached(fn)
            if pb:
                src=fitz.open(stream=pb, filetype="pdf"); nd.insert_pdf(src, from_page=pn-1, to_page=pn-1); src.close()
        st.session_state.presentation_pdf=nd.tobytes(); nd.close(); st.rerun()
    if st.session_state.presentation_pdf:
        st.download_button("📥 Download Presentation.pdf", data=st.session_state.presentation_pdf, file_name="Presentation.pdf", mime="application/pdf", use_container_width=True, type="primary")
    if st.button("🗑️ Clear Basket", use_container_width=True): st.session_state.selected=[]; st.session_state.presentation_pdf=None; st.rerun()

if do_search:
    allowed=get_allowed_files(st.session_state.customer_email, st.session_state.is_admin)
    filt=[f for f in allowed if brand.lower() in f.lower()] if brand!="All Brands" else allowed
    if not filt: filt=allowed # If brand filter finds nothing, search all
    final=[]; prog=st.progress(0)
    for idx,fn in enumerate(filt):
        pages=search_fast(fn, query)
        for pno,cnt,matched in pages: final.append((fn,pno,cnt,matched))
        prog.progress((idx+1)/len(filt))
    prog.empty()
    st.session_state.last_results=final; st.session_state.page_num=1; st.rerun()

left,right=st.columns([1,2.2])
with left:
    st.markdown("### Uploaded Files:")
    for fn in get_allowed_files(st.session_state.customer_email, st.session_state.is_admin):
        with st.container(border=True):
            st.write(f"**{fn[:35]}**")
            pb=get_pdf_bytes_cached(fn)
            if pb: 
                st.success(f"✅ {len(pb)/1024/1024:.1f}MB")
                if st.button("👁️ View", key=f"v_{fn}"): 
                    img=get_page_image_cached(fn,1)
                    if img: st.image(img, use_container_width=True, caption="Page 1")
            else:
                st.error("❌ Not loaded")
                if st.button("🔄 Reload", key=f"rl_{fn}"): st.cache_data.clear(); st.rerun()
            if pb: st.download_button("📥 Download", data=pb, file_name=fn, mime="application/pdf", key=f"dl_{fn}", use_container_width=True)

with right:
    if not st.session_state.last_results: st.info("Click SEARCH - BREEZE_STONE will show like your photo")
    else:
        results=st.session_state.last_results
        if not results: st.warning(f"No results for {query} - Try BREEZE without brand filter (Select All Brands)")
        else:
            st.success(f"Found {len(results)} pages for {query} - Like your BREEZE_STONE photo")
            pg=st.session_state.page_num; ps=6; total=(len(results)+ps-1)//ps
            if total>1:
                c1,c2,c3=st.columns([1,2,1])
                with c1:
                    if st.button("⬅️ Previous", disabled=pg==1, use_container_width=True): st.session_state.page_num-=1; st.rerun()
                with c2: st.markdown(f"<div style='text-align:center;padding:10px;background:#1f2937;border-radius:8px'>Page {pg}/{total}</div>", unsafe_allow_html=True)
                with c3:
                    if st.button("Next ➡️", disabled=pg==total, use_container_width=True, type="primary"): st.session_state.page_num+=1; st.rerun()
            display=results[(pg-1)*ps: pg*ps]
            cols=st.columns(3)
            for idx,(fn,pn,cnt,matched) in enumerate(display):
                with cols[idx%3]:
                    with st.container(border=True):
                        img=get_page_image_cached(fn,pn)
                        if img: st.image(img, use_container_width=True)
                        else: st.write(f"Loading P{pn}...")
                        st.write(f"**{fn[:20]} P{pn}** - {', '.join(matched)}")
                        is_sel=(fn,pn) in st.session_state.selected
                        if st.checkbox("Add to Basket", key=f"chk_{fn}_{pn}_{idx}_{pg}", value=is_sel):
                            if (fn,pn) not in st.session_state.selected: st.session_state.selected.append((fn,pn)); st.session_state.presentation_images[f"{fn}_{pn}"]=img
                        else:
                            if (fn,pn) in st.session_state.selected: st.session_state.selected.remove((fn,pn))

if st.session_state.is_admin:
    if st.button("🧹 Clear Cache - If images not loading"): st.cache_data.clear(); st.cache_resource.clear(); st.rerun()
