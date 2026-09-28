import streamlit as st
import base64, json, io, requests
import fitz
from github import Github

st.set_page_config(page_title="Bathroom AI - FINAL COMPLETE", layout="wide")
st.markdown("""
<style>
div[data-baseweb="input"] input {font-size:20px!important; height:50px!important; font-weight:600!important;}
.stButton button {height:48px!important; font-weight:600!important;}
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
    except Exception as e: st.error(f"Save error: {e}")

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
    try:
        rel=get_or_create_release()
        if rel:
            for a in rel.get_assets():
                if a.name.lower().endswith(".pdf") and a.name not in files: files.append(a.name)
    except: pass
    return sorted(files)

@st.cache_data(ttl=3600, show_spinner=True)
def get_pdf_bytes_cached(fname):
    try:
        headers={"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
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
                    dr2=requests.get(ast.get("browser_download_url"), headers={"Authorization": f"token {GITHUB_TOKEN}"}, timeout=300, allow_redirects=True, stream=True)
                    if dr2.status_code==200:
                        content=b"".join(dr2.iter_content(chunk_size=8192))
                        if len(content)>5000: return content
    except: pass
    return None

@st.cache_data(ttl=3600, show_spinner=True)
def get_page_image_cached(fname, page_no):
    pb=get_pdf_bytes_cached(fname)
    if not pb: return None
    try:
        doc=fitz.open(stream=pb, filetype="pdf")
        # FIX RAINBOW GLITCH - Force RGB
        pix=doc.load_page(page_no-1).get_pixmap(dpi=110, colorspace=fitz.csRGB, alpha=False)
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

def get_allowed_files(mail, is_admin):
    allf=get_all_pdfs()
    if is_admin: return allf
    access,_=get_json_file("data/file_access.json", {})
    allowed=[]
    for f in allf:
        lst=access.get(f, ["all"])
        if "all" in lst or mail.lower() in [x.lower() for x in lst]:
            allowed.append(f)
    return allowed

# SESSION
if "customer_verified" not in st.session_state: st.session_state.customer_verified=False
if "is_admin" not in st.session_state: st.session_state.is_admin=False
if "customer_email" not in st.session_state: st.session_state.customer_email=""
if "selected" not in st.session_state: st.session_state.selected=[]
if "last_results" not in st.session_state: st.session_state.last_results=[]
if "presentation_images" not in st.session_state: st.session_state.presentation_images={}
if "page_num" not in st.session_state: st.session_state.page_num=1
if "presentation_pdf" not in st.session_state: st.session_state.presentation_pdf=None

# LOGIN - CUSTOMER + ADMIN BOTH BACK
if not st.session_state.customer_verified and not st.session_state.is_admin:
    st.title("Pricelist Login")
    t_cust, t_admin = st.tabs(["Customer Login / Signup", "Admin Login"])

    with t_admin:
        st.markdown("### Admin Login")
        pwd=st.text_input("Admin Password", type="password", key="admin_pwd")
        if st.button("Login as Admin", type="primary", use_container_width=True):
            if pwd==ADMIN_PASSWORD:
                st.session_state.is_admin=True; st.session_state.customer_verified=True; st.rerun()
            else: st.error("Wrong password")

    with t_cust:
        st.markdown("### Customer Login")
        mail=st.text_input("Your Mail ID for Login", key="cust_mail_login")
        if st.button("Login as Customer", use_container_width=True):
            cust,_=get_json_file("data/customers.json", [])
            f=next((c for c in cust if c.get("mail","").lower()==mail.lower().strip()), None)
            if f and f.get("approved"):
                st.session_state.customer_verified=True; st.session_state.customer_email=mail.lower().strip(); st.rerun()
            elif f and not f.get("approved"):
                st.warning("Your request pending - Admin will approve")
            else:
                st.error("Not registered - Please Signup below")

        st.divider()
        st.markdown("### New Customer Signup")
        with st.form("signup_form"):
            n=st.text_input("Name*"); cont=st.text_input("Contact*"); m=st.text_input("Mail*"); city=st.text_input("City*"); pin=st.text_input("Pincode*"); comp=st.text_input("Company")
            submitted=st.form_submit_button("Submit for Approval", type="primary", use_container_width=True)
            if submitted:
                if not m or not n:
                    st.error("Name and Mail required")
                else:
                    cust,sha=get_json_file("data/customers.json", [])
                    if any(c.get("mail","").lower()==m.lower().strip() for c in cust):
                        st.warning("Already registered")
                    else:
                        cust.append({"name":n,"contact":cont,"mail":m.lower().strip(),"city":city,"pincode":pin,"company":comp,"approved":False})
                        save_json_file("data/customers.json", cust, sha, "new customer signup")
                        st.success("Submitted - Admin will approve soon!")
    st.stop()

# MAIN APP
st.title("Pricelist Search")
top1,top2=st.columns([4,1])
with top1:
    who = "Admin" if st.session_state.is_admin else st.session_state.customer_email
    st.write(f"Login: {who} | Total Files: {len(get_all_pdfs())}")
with top2:
    if st.button("Logout", use_container_width=True):
        st.session_state.customer_verified=False; st.session_state.is_admin=False; st.session_state.customer_email=""; st.rerun()

brands,_=get_json_file("data/brands.json", DEFAULT_BRANDS)
s1,s2,s3=st.columns([1,2,1])
with s1: brand=st.selectbox("Brand", ["All Brands"]+brands)
with s2: query=st.text_input("Search Pricelist", placeholder="BREEZE", value="BREEZE")
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

tab_search, tab_pricelist, tab_basket, tab_admin = st.tabs(["Search Results", "PRICE LIST", "Basket", "Admin / Upload"])

with tab_search:
    if not st.session_state.last_results:
        st.info("Type BREEZE and click SEARCH - Results show here")
    else:
        results=st.session_state.last_results
        if not results: st.warning(f"No results for {query} - Try All Brands")
        else:
            st.success(f"Found {len(results)} pages for {query}")
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
                        else: st.warning(f"P{pn} - Load in PRICE LIST first")
                        st.write(f"P{pn} {fn[:18]}")
                        if st.checkbox("Add to Basket", key=f"chk_{fn}_{pn}_{idx}_{pg}", value=(fn,pn) in st.session_state.selected):
                            if (fn,pn) not in st.session_state.selected: st.session_state.selected.append((fn,pn)); st.session_state.presentation_images[f"{fn}_{pn}"]=img
                        else:
                            if (fn,pn) in st.session_state.selected: st.session_state.selected.remove((fn,pn))

with tab_pricelist:
    st.markdown("### All Pricelists - Maximise when needed")
    st.caption("This tab keeps search clean - Open only when you need")
    files=get_allowed_files(st.session_state.customer_email, st.session_state.is_admin)
    st.write(f"Total: {len(files)} files")
    if not files: st.warning("No files allowed")
    cols=st.columns(3)
    for idx,fn in enumerate(files):
        with cols[idx%3]:
            with st.container(border=True):
                st.write(f"**{fn}**")
                if st.button("Load & Preview", key=f"load_{idx}", type="primary", use_container_width=True):
                    with st.spinner(f"Loading {fn}..."):
                        pb=get_pdf_bytes_cached(fn)
                        if pb:
                            st.success(f"{len(pb)/1024/1024:.1f}MB Loaded")
                            img=get_page_image_cached(fn,1)
                            if img: st.image(img, use_container_width=True)
                        else: st.error("Failed")

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
        admin_section = st.radio("Select Admin Section", ["Customer Approval / List", "File Access", "Brands", "Upload"], horizontal=True)

        if admin_section == "Customer Approval / List":
            cust,sha_c=get_json_file("data/customers.json", [])
            st.markdown(f"### Customer Approval - Total: {len(cust)}")
            pending=[c for c in cust if not c.get("approved")]
            st.markdown(f"**Pending: {len(pending)} | Approved: {len(cust)-len(pending)}**")
            if pending:
                for i,c in enumerate(cust):
                    if not c.get("approved"):
                        with st.container(border=True):
                            st.write(f"{c.get('name')} | {c.get('mail')} | {c.get('contact')} | {c.get('city')}")
                            ca,cr=st.columns(2)
                            with ca:
                                if st.button("Approve", key=f"ap_{i}", type="primary", use_container_width=True):
                                    cust[i]["approved"]=True
                                    save_json_file("data/customers.json", cust, sha_c, "approve")
                                    st.rerun()
                            with cr:
                                if st.button("Reject", key=f"rej_{i}", use_container_width=True):
                                    cust.pop(i)
                                    save_json_file("data/customers.json", cust, sha_c, "reject")
                                    st.rerun()
            st.divider()
            st.markdown("**All Customers List:**")
            for c in cust:
                status="Approved" if c.get("approved") else "Pending"
                st.write(f"{status} - {c.get('name')} - {c.get('mail')}")

        elif admin_section == "File Access":
            st.markdown("### File Access")
            acc,sha_acc=get_json_file("data/file_access.json", {})
            for fn in get_all_pdfs():
                st.write(f"{fn} - {acc.get(fn,['all'])}")

        elif admin_section == "Brands":
            blist,sha_b=get_json_file("data/brands.json", DEFAULT_BRANDS)
            st.write(f"Current: {', '.join(blist)}")
            nb=st.text_input("New Brand")
            if st.button("Create Brand"):
                if nb.strip() not in blist:
                    blist.append(nb.strip())
                    save_json_file("data/brands.json", blist, sha_b, "add brand")
                    st.rerun()

        else:
            st.markdown("### Upload Pricelists")
            ups=st.file_uploader("Choose PDFs", type=["pdf"], accept_multiple_files=True)
            if st.button("Upload to Release", type="primary", use_container_width=True):
                rel=get_or_create_release()
                if not rel: st.error("Release not found")
                else:
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
