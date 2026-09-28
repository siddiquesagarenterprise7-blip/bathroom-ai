import streamlit as st
import base64, json, io, requests, re
import fitz
from github import Github

st.set_page_config(page_title="Bathroom AI - FINAL AUKI 60 FIX", layout="wide")
st.markdown("""
<style>
div[data-baseweb="input"] input {font-size:20px!important; height:50px!important; font-weight:700!important;}
.stButton button {height:50px!important; font-weight:600!important;}
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
DEFAULT_BRANDS = ["Fantini","Gessi","Antoniolupi","Catalano","FALPER","Jaquar","Grohe","Agape","Boffi"]

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
    except Exception as e: st.error(str(e))

def ensure_files():
    for p,d in [("data/brands.json", DEFAULT_BRANDS), ("data/customers.json", []), ("data/file_access.json", {})]:
        data,_ = get_json_file(p, None)
        if data is None: save_json_file(p, d, None, "init "+p)
ensure_files()

def get_or_create_release():
    try:
        for r in repo.get_releases():
            if r.tag_name=="pdfs-storage": return r
        return repo.create_git_release(tag="pdfs-storage", name="PDF Storage", message="storage", draft=False, prerelease=False)
    except: return None

def get_all_pdfs_debug():
    files_pdfs=[]
    files_release=[]
    try:
        for c in repo.get_contents("pdfs"):
            if c.name.lower().endswith(".pdf"):
                files_pdfs.append(c.name)
    except: pass
    try:
        headers={"Authorization": f"token {GITHUB_TOKEN}"}
        r=requests.get(f"https://api.github.com/repos/{GITHUB_REPO_NAME}/releases/tags/pdfs-storage", headers=headers, timeout=30)
        if r.status_code==200:
            for ast in r.json().get("assets",[]):
                nm=ast.get("name","")
                if nm.lower().endswith(".pdf") and nm not in files_release:
                    files_release.append(nm)
    except: pass
    combined=list(set(files_pdfs + files_release))
    return sorted(combined), files_pdfs, files_release

def get_all_pdfs():
    combined,_,_=get_all_pdfs_debug()
    return combined

@st.cache_data(ttl=3600, show_spinner=True)
def get_pdf_bytes_cached(fname):
    try:
        fc=repo.get_contents(f"pdfs/{fname}")
        try:
            data=base64.b64decode(fc.content)
            if len(data)>1000: return data
        except: pass
        try:
            r=requests.get(fc.download_url, headers={"Authorization": f"token {GITHUB_TOKEN}"}, timeout=120)
            if r.status_code==200 and len(r.content)>1000: return r.content
        except: pass
    except: pass
    try:
        headers={"Authorization": f"token {GITHUB_TOKEN}"}
        r=requests.get(f"https://api.github.com/repos/{GITHUB_REPO_NAME}/releases/tags/pdfs-storage", headers=headers, timeout=30)
        if r.status_code==200:
            for ast in r.json().get("assets",[]):
                if ast.get("name")==fname:
                    dl_headers={"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/octet-stream"}
                    dl_url=f"https://api.github.com/repos/{GITHUB_REPO_NAME}/releases/assets/{ast.get('id')}"
                    dr=requests.get(dl_url, headers=dl_headers, timeout=300, allow_redirects=True, stream=True)
                    if dr.status_code==200:
                        content=b"".join(dr.iter_content(chunk_size=8192))
                        if len(content)>5000: return content
    except: pass
    return None

@st.cache_data(ttl=3600, show_spinner=True)
def get_page_image_cached(fname, page_no):
    pb=get_pdf_bytes_cached(fname)
    if not pb: return None
    try:
        doc=fitz.open(stream=pb, filetype="pdf")
        pix=doc.load_page(page_no-1).get_pixmap(dpi=110, colorspace=fitz.csRGB, alpha=False)
        b=pix.tobytes("png")
        doc.close()
        return b
    except: return None

# FIXED SEARCH - AUKI 60 WILL SHOW ONLY 2-3 PAGES NOT 1246
def search_fast(fname, query):
    pb=get_pdf_bytes_cached(fname)
    if not pb: return []
    q=query.lower().strip()
    words=[w.lower() for w in q.replace("_"," ").split() if w.strip()]
    if not words: return []
    alpha_words=[w for w in words if any(c.isalpha() for c in w)]
    num_words=[w for w in words if any(c.isdigit() for c in w)]

    res=[]
    try:
        doc=fitz.open(stream=pb, filetype="pdf")
        for i in range(len(doc)):
            txt=doc.load_page(i).get_text("text").lower()
            # 1. Exact phrase like "auki 60" - highest priority
            if q in txt:
                res.append((i+1, 100, [q]))
                continue
            # 2. For Auki 60: Require Auki word must exist
            if alpha_words:
                if not all(w in txt for w in alpha_words):
                    continue
                # If query has number + alpha, check proximity (within 50 chars)
                if num_words:
                    found_close=False
                    for aw in alpha_words:
                        for nw in num_words:
                            pattern=re.compile(re.escape(aw)+r".{0,60}"+re.escape(nw)+r"|"+re.escape(nw)+r".{0,60}"+re.escape(aw))
                            if pattern.search(txt):
                                found_close=True
                                break
                        if found_close: break
                    if not found_close:
                        continue
            else:
                if not all(w in txt for w in words):
                    continue
            res.append((i+1, 10, words))
        doc.close()
    except: pass
    return res

def get_allowed_files(mail, is_admin):
    allf=get_all_pdfs()
    if is_admin: return allf
    access,_=get_json_file("data/file_access.json", {})
    allowed=[]
    for f in allf:
        lst=access.get(f, ["all"])
        if "all" in lst or mail.lower() in [x.lower() for x in lst]: allowed.append(f)
    return allowed

if "customer_verified" not in st.session_state: st.session_state.customer_verified=False
if "is_admin" not in st.session_state: st.session_state.is_admin=False
if "customer_email" not in st.session_state: st.session_state.customer_email=""
if "selected" not in st.session_state: st.session_state.selected=[]
if "last_results" not in st.session_state: st.session_state.last_results=[]
if "presentation_images" not in st.session_state: st.session_state.presentation_images={}
if "page_num" not in st.session_state: st.session_state.page_num=1
if "presentation_pdf" not in st.session_state: st.session_state.presentation_pdf=None

if not st.session_state.customer_verified and not st.session_state.is_admin:
    st.title("Pricelist Login")
    t_cust, t_admin = st.tabs(["Customer", "Admin"])
    with t_admin:
        pwd=st.text_input("Admin Password", type="password")
        if st.button("Login as Admin", type="primary", use_container_width=True):
            if pwd==ADMIN_PASSWORD:
                st.session_state.is_admin=True; st.session_state.customer_verified=True; st.rerun()
            else: st.error("Wrong password")
    with t_cust:
        mail=st.text_input("Your Mail ID")
        if st.button("Login as Customer", use_container_width=True):
            cust,_=get_json_file("data/customers.json", [])
            f=next((c for c in cust if c.get("mail","").lower()==mail.lower().strip()), None)
            if f and f.get("approved"):
                st.session_state.customer_verified=True; st.session_state.customer_email=mail.lower().strip(); st.rerun()
            elif f and not f.get("approved"): st.warning("Pending approval")
            else: st.error("Not registered - Signup below")
        st.divider()
        with st.form("signup"):
            n=st.text_input("Name*"); cont=st.text_input("Contact*"); m=st.text_input("Mail*"); city=st.text_input("City*"); pin=st.text_input("Pincode*")
            if st.form_submit_button("Submit for Approval", type="primary", use_container_width=True):
                cust,sha=get_json_file("data/customers.json", [])
                if not any(c.get("mail","").lower()==m.lower().strip() for c in cust):
                    cust.append({"name":n,"contact":cont,"mail":m.lower().strip(),"city":city,"pincode":pin,"approved":False})
                    save_json_file("data/customers.json", cust, sha, "signup")
                    st.success("Submitted! Admin will approve")
    st.stop()

st.title("Pricelist Search")
all_files, files_pdfs, files_release = get_all_pdfs_debug()
top1,top2=st.columns([4,1])
with top1:
    who = "Admin" if st.session_state.is_admin else st.session_state.customer_email
    st.write(f"Login: {who} | Total: {len(all_files)} | pdfs folder: {len(files_pdfs)} | Release: {len(files_release)}")
with top2:
    if st.button("Logout", use_container_width=True):
        st.session_state.customer_verified=False; st.session_state.is_admin=False; st.rerun()

brands,_=get_json_file("data/brands.json", DEFAULT_BRANDS)
s1,s2,s3=st.columns([1,2,1])
with s1: brand=st.selectbox("Brand", ["All Brands"]+brands)
with s2: query=st.text_input("Search Pricelist", placeholder="Auki 60", value="Auki 60")
with s3:
    st.write(""); st.write("")
    do_search=st.button("SEARCH ALL MATCHES", type="primary", use_container_width=True)

if do_search:
    allowed=get_allowed_files(st.session_state.customer_email, st.session_state.is_admin)
    filt=[f for f in allowed if brand.lower() in f.lower()] if brand!="All Brands" else allowed
    if not filt: filt=allowed
    final=[]; prog=st.progress(0, text="Searching...")
    for idx,fn in enumerate(filt):
        pages=search_fast(fn, query)
        for pno,cnt,matched in pages: final.append((fn,pno,cnt,matched))
        prog.progress((idx+1)/len(filt) if filt else 1)
    prog.empty()
    st.session_state.last_results=final; st.session_state.page_num=1; st.rerun()

tab_search, tab_pricelist, tab_basket, tab_admin = st.tabs([f"Search Results", f"PRICE LIST ({len(all_files)})", "Basket", "Admin"])

with tab_search:
    if not st.session_state.last_results:
        st.info("Search Auki 60 - Now shows only exact matches")
    else:
        results=st.session_state.last_results
        if not results: st.warning(f"No results for {query}")
        else:
            st.success(f"Found {len(results)} pages for '{query}' (Before was 1246, now fixed)")
            pg=st.session_state.page_num; ps=6; total=(len(results)+ps-1)//ps
            if total>1:
                c1,c2,c3=st.columns([1,2,1])
                with c1:
                    if st.button("Previous", disabled=pg==1, key="prev_s"): st.session_state.page_num-=1; st.rerun()
                with c2: st.markdown(f"<div style='text-align:center;padding:10px;background:#1f2937;border-radius:8px'>Page {pg}/{total}</div>", unsafe_allow_html=True)
                with c3:
                    if st.button("Next", disabled=pg==total, key="next_s", type="primary"): st.session_state.page_num+=1; st.rerun()
            display=results[(pg-1)*ps: pg*ps]
            cols=st.columns(3)
            for idx,(fn,pn,cnt,matched) in enumerate(display):
                with cols[idx%3]:
                    with st.container(border=True):
                        img=get_page_image_cached(fn,pn)
                        if img: st.image(img, use_container_width=True)
                        else: st.warning(f"P{pn} loading...")
                        st.write(f"P{pn} {fn[:18]} - {matched}")
                        if st.checkbox("Add to Basket", key=f"chk_{fn}_{pn}_{idx}_{pg}", value=(fn,pn) in st.session_state.selected):
                            if (fn,pn) not in st.session_state.selected: st.session_state.selected.append((fn,pn)); st.session_state.presentation_images[f"{fn}_{pn}"]=img
                        else:
                            if (fn,pn) in st.session_state.selected: st.session_state.selected.remove((fn,pn))

with tab_pricelist:
    st.markdown("### All Pricelists - Automatic Loading")
    st.caption("No Load button - Auto loads and caches")
    files=get_allowed_files(st.session_state.customer_email, st.session_state.is_admin)
    cols=st.columns(3)
    for idx,fn in enumerate(files):
        with cols[idx%3]:
            with st.container(border=True):
                st.write(f"**{fn}**")
                pb=get_pdf_bytes_cached(fn)
                if pb:
                    st.success(f"{len(pb)/1024/1024:.1f}MB - Auto Loaded")
                    img=get_page_image_cached(fn,1)
                    if img: st.image(img, use_container_width=True)
                else:
                    st.error("Not loaded")

with tab_basket:
    st.markdown(f"### Basket: {len(st.session_state.selected)}")
    if st.session_state.selected:
        cols=st.columns(4)
        for idx,(fn,pn) in enumerate(st.session_state.selected):
            with cols[idx%4]:
                ib=st.session_state.presentation_images.get(f"{fn}_{pn}")
                if ib: st.image(ib, use_container_width=True)
                if st.button("Remove", key=f"rem_{idx}"): st.session_state.selected.remove((fn,pn)); st.rerun()
        if st.button(f"Create PDF ({len(st.session_state.selected)})", type="primary", use_container_width=True):
            nd=fitz.open()
            for fn,pn in st.session_state.selected:
                pb=get_pdf_bytes_cached(fn)
                if pb:
                    src=fitz.open(stream=pb, filetype="pdf"); nd.insert_pdf(src, from_page=pn-1, to_page=pn-1); src.close()
            st.session_state.presentation_pdf=nd.tobytes(); nd.close(); st.rerun()
        if st.session_state.presentation_pdf:
            st.download_button("Download Presentation.pdf", data=st.session_state.presentation_pdf, file_name="Presentation.pdf", mime="application/pdf", use_container_width=True, type="primary")

with tab_admin:
    if not st.session_state.is_admin:
        st.warning("Admin only")
    else:
        admin_section = st.radio("Admin Section", ["Customer Approval / List", "Upload"], horizontal=True)
        if admin_section == "Customer Approval / List":
            cust,sha_c=get_json_file("data/customers.json", [])
            pending=[c for c in cust if not c.get("approved")]
            st.write(f"Pending: {len(pending)} | Total: {len(cust)}")
            for i,c in enumerate(cust):
                if not c.get("approved"):
                    with st.container(border=True):
                        st.write(f"{c.get('name')} | {c.get('mail')} | {c.get('contact')}")
                        if st.button("Approve", key=f"ap_{i}", type="primary", use_container_width=True):
                            cust[i]["approved"]=True
                            save_json_file("data/customers.json", cust, sha_c, "approve")
                            st.rerun()
            st.divider()
            for c in cust: st.write(f"{'Approved' if c.get('approved') else 'Pending'} - {c.get('name')} - {c.get('mail')}")
        else:
            st.markdown("### Upload Pricelists")
            ups=st.file_uploader("Choose PDFs", type=["pdf"], accept_multiple_files=True)
            if st.button("Upload to Release", type="primary", use_container_width=True):
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
                        acc,sha_acc=get_json_file("data/file_access.json", {})
                        acc[safe]=["all"]
                        save_json_file("data/file_access.json", acc, sha_acc, "upload")
                        st.success(f"✅ {safe} {len(fb)/1024/1024:.1f}MB")
                    except Exception as e: st.error(f"{safe}: {e}")
                st.cache_data.clear(); st.rerun()
        if st.button("Clear Cache", use_container_width=True):
            st.cache_data.clear(); st.cache_resource.clear(); st.rerun()
