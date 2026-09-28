import streamlit as st
import base64, json, io
import fitz
from github import Github

st.set_page_config(page_title="Bathroom AI - IMAGES 100% FIX", layout="wide")

try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    GITHUB_REPO_NAME = st.secrets["GITHUB_REPO"]
    ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "Bathroom@123")
except:
    st.error("Add Secrets")
    st.stop()

@st.cache_resource
def get_repo():
    return Github(GITHUB_TOKEN).get_repo(GITHUB_REPO_NAME)
repo = get_repo()

DEFAULT_BRANDS = ["Fantini", "Gessi", "Hansgrohe", "Jaquar", "Grohe", "Kohler"]

def get_json_file(path, default):
    try:
        f = repo.get_contents(path)
        c = base64.b64decode(f.content).decode('utf-8').strip()
        if not c: return default, f.sha
        return json.loads(c), f.sha
    except: return default, None

def save_json_file(path, data, sha, msg):
    content = json.dumps(data, indent=2, ensure_ascii=False)
    try:
        if sha: repo.update_file(path, msg, content, sha)
        else:
            try:
                ex=repo.get_contents(path)
                repo.update_file(path, msg, content, ex.sha)
            except: repo.create_file(path, msg, content)
        st.cache_data.clear()
    except Exception as e: st.error(f"Save fail: {e}")

def ensure_files():
    try: repo.get_contents("data")
    except:
        try: repo.create_file("data/.gitkeep", "init", "keep")
        except: pass
    for p,d in [("data/brands.json", DEFAULT_BRANDS), ("data/customers.json", []), ("data/file_access.json", {})]:
        data,_ = get_json_file(p, None)
        if data is None: save_json_file(p, d, None, "init")
ensure_files()

def get_or_create_release():
    try:
        for r in repo.get_releases():
            if r.tag_name=="pdfs-storage": return r
        return repo.create_git_release(tag="pdfs-storage", name="PDF Storage", message="150MB", draft=False, prerelease=False)
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
    except:
        try:
            rel=get_or_create_release()
            if rel:
                import requests
                for a in rel.get_assets():
                    if a.name==fname:
                        r=requests.get(a.browser_download_url, timeout=90)
                        if r.status_code==200: return r.content
        except: pass
    return None

# ULTRA SIMPLE IMAGE - NO PIL - DIRECT PNG BYTES - WILL LOAD
@st.cache_data(ttl=3600, show_spinner=False)
def get_page_image_cached(fname, page_no):
    try:
        pb = get_pdf_bytes_cached(fname)
        if not pb:
            return None
        doc = fitz.open(stream=pb, filetype="pdf")
        if page_no <1 or page_no > len(doc):
            doc.close()
            return None
        page = doc.load_page(page_no-1)
        # LOW DPI 85 = FAST + NO MEMORY ERROR
        pix = page.get_pixmap(dpi=85, alpha=False)
        png_bytes = pix.tobytes("png")
        doc.close()
        return png_bytes
    except Exception as e:
        # Don't hide error
        print(f"Image error {fname} p{page_no}: {e}")
        return None

def search_fast(fname, query):
    pb = get_pdf_bytes_cached(fname)
    if not pb: return []
    words=[w.lower() for w in query.strip().split() if w.strip()][:4]
    if not words: return []
    res=[]
    try:
        doc=fitz.open(stream=pb, filetype="pdf")
        for i in range(len(doc)):
            txt=doc.load_page(i).get_text("text").lower()
            matched=[w for w in words if w in txt]
            if len(matched)==len(words):
                res.append((i+1, len(matched), matched))
        doc.close()
    except: pass
    return res

def get_allowed_files(mail, is_admin):
    allf=get_all_pdfs()
    if is_admin: return allf
    access,_=get_json_file("data/file_access.json", {})
    allowed=[]
    for f in allf:
        m=access.get(f, ["all"])
        if "all" in m or mail.lower() in [x.lower() for x in m]:
            allowed.append(f)
    return allowed

if "customer_verified" not in st.session_state: st.session_state.customer_verified=False
if "is_admin" not in st.session_state: st.session_state.is_admin=False
if "customer_email" not in st.session_state: st.session_state.customer_email=""
if "selected" not in st.session_state: st.session_state.selected=[]
if "last_results" not in st.session_state: st.session_state.last_results=[]
if "presentation_images" not in st.session_state: st.session_state.presentation_images={}
if "page_num" not in st.session_state: st.session_state.page_num=1

if st.session_state.last_results and len(st.session_state.last_results)>0:
    first=st.session_state.last_results[0]
    if isinstance(first,(list,tuple)) and len(first)==5:
        st.session_state.last_results=[]
        st.session_state.page_num=1

if not st.session_state.customer_verified and not st.session_state.is_admin:
    st.title("🛁 Pricelist Login")
    t1,t2=st.tabs(["Customer","Admin"])
    with t2:
        pwd=st.text_input("Admin Password", type="password", key="admin_pwd")
        if st.button("Login as Admin", type="primary", use_container_width=True):
            if pwd==ADMIN_PASSWORD:
                st.session_state.is_admin=True
                st.session_state.customer_verified=True
                st.rerun()
    with t1:
        mail=st.text_input("Mail ID", key="login_mail")
        if st.button("Login"):
            cust,_=get_json_file("data/customers.json", [])
            f=next((c for c in cust if c.get("mail","").lower()==mail.lower().strip()), None)
            if f and f.get("approved"):
                st.session_state.customer_verified=True
                st.session_state.customer_email=mail
                st.rerun()
            else: st.error("Not found or pending")
        with st.form("signup"):
            st.write("New Signup")
            n=st.text_input("Name*"); cont=st.text_input("Contact*"); m=st.text_input("Mail*"); city=st.text_input("City*"); pin=st.text_input("Pincode*")
            if st.form_submit_button("Submit"):
                cust,sha=get_json_file("data/customers.json", [])
                cust.append({"name":n,"contact":cont,"mail":m,"city":city,"pincode":pin,"company":"","approved":False})
                save_json_file("data/customers.json", cust, sha, "new")
                st.success("Submitted!")
    st.stop()

st.title("Pricelist Search")
c1,c2=st.columns([3,1])
with c1: st.markdown(f"**Login:** {st.session_state.customer_email if not st.session_state.is_admin else 'Admin'}")
with c2:
    if st.button("Logout", use_container_width=True, key="logout_btn"):
        st.session_state.customer_verified=False; st.session_state.is_admin=False; st.session_state.last_results=[]; st.session_state.selected=[]; st.session_state.page_num=1
        st.rerun()

s1,s2,s3=st.columns([1,2,1])
with s1:
    brands,_=get_json_file("data/brands.json", DEFAULT_BRANDS)
    brand=st.selectbox("Brand", ["All Brands"]+brands, key="brand_select")
with s2:
    query=st.text_input("Search Pricelist", placeholder="mint spout", key="search_input")
with s3:
    st.write(""); st.write("")
    do_search=st.button("🔍 SEARCH ALL MATCHES", type="primary", use_container_width=True, key="search_btn")

if st.session_state.selected:
    st.divider()
    st.markdown(f"### 🧺 Basket: {len(st.session_state.selected)} sheets")
    cols=st.columns(min(6, len(st.session_state.selected)))
    for idx,(fn,pn) in enumerate(st.session_state.selected):
        with cols[idx%6]:
            ib=st.session_state.presentation_images.get(f"{fn}_{pn}")
            if ib: st.image(ib, use_container_width=True)
            st.caption(f"{fn} P{pn}")
            if st.button("❌", key=f"rem_{fn}_{pn}_{idx}_basket"):
                st.session_state.selected.remove((fn,pn))
                st.session_state.presentation_images.pop(f"{fn}_{pn}", None)
                st.rerun()
    if st.button(f"📑 Create PDF ({len(st.session_state.selected)})", type="primary", use_container_width=True, key="create_pdf"):
        try:
            nd=fitz.open()
            for fn,pn in st.session_state.selected:
                pb=get_pdf_bytes_cached(fn)
                if pb:
                    src=fitz.open(stream=pb, filetype="pdf")
                    nd.insert_pdf(src, from_page=pn-1, to_page=pn-1)
                    src.close()
            out=nd.tobytes()
            nd.close()
            st.download_button("📥 Download Presentation.pdf", data=out, file_name="Presentation.pdf", mime="application/pdf", use_container_width=True, key="dl_pres")
        except Exception as e: st.error(str(e))
    if st.button("🗑️ Clear Basket", use_container_width=True, key="clear_basket"):
        st.session_state.selected=[]; st.session_state.presentation_images={}; st.rerun()

if do_search:
    q = st.session_state.search_input
    if not q or not q.strip():
        st.warning("Type a word in Search Pricelist box")
    else:
        allowed=get_allowed_files(st.session_state.customer_email, st.session_state.is_admin)
        filt=allowed
        if brand!="All Brands":
            tmp=[f for f in allowed if brand.lower() in f.lower()]
            if tmp: filt=tmp
        final=[]
        prog=st.progress(0)
        for idx,fn in enumerate(filt):
            pages=search_fast(fn, q)
            for pno, cnt, matched in pages:
                final.append((fn, pno, cnt, matched))
            prog.progress((idx+1)/len(filt) if filt else 1)
        prog.empty()
        st.session_state.last_results=final
        st.session_state.page_num=1
        st.rerun()

left,right=st.columns([1,2.2])
with left:
    st.markdown("### Uploaded Files:")
    for fn in get_allowed_files(st.session_state.customer_email, st.session_state.is_admin):
        with st.container(border=True):
            st.write(f"**{fn}**")
            a,b=st.columns(2)
            with a:
                if st.button("👁️ View", key=f"view_{fn}_left", use_container_width=True):
                    ib=get_page_image_cached(fn, 1)
                    if ib:
                        st.image(ib, use_container_width=True)
                    else:
                        st.error("Failed to load preview - PDF bytes missing")
            with b:
                pb=get_pdf_bytes_cached(fn)
                if pb: st.download_button("📥 Download", data=pb, file_name=fn, mime="application/pdf", key=f"dl_{fn}_left", use_container_width=True)
    st.divider()
    cust_data,sha_c=get_json_file("data/customers.json", [])
    pend=[c for c in cust_data if not c.get("approved")]
    if pend and st.session_state.is_admin:
        st.toast(f"🔴 {len(pend)} pending!", icon="🔔")
        st.markdown(f"### Pending: 🔴 {len(pend)} NEW")
    else: st.markdown("### Pending Customers approval:")
    for i,c in enumerate(cust_data):
        if not c.get("approved"):
            with st.container(border=True):
                st.write(f"**{c.get('name')}** {c.get('mail')}")
                if st.session_state.is_admin:
                    if st.button("✅ Approve", key=f"ap_{i}_left", type="primary", use_container_width=True):
                        cust_data[i]["approved"]=True
                        save_json_file("data/customers.json", cust_data, sha_c, "approve")
                        st.rerun()

with right:
    if not st.session_state.last_results:
        st.info("Search shows ALL — 6 per page — If 3 results, 3 empty — Images cached")
    else:
        results=st.session_state.last_results
        st.success(f"Found {len(results)} pages — 6 per page — Images cached")

        page_size=6
        total_pages=(len(results)+page_size-1)//page_size
        if total_pages>1:
            cp,ci,cn=st.columns([1,2,1])
            with cp:
                if st.button("⬅️ Previous", disabled=st.session_state.page_num==1, use_container_width=True, key="prev_final2"):
                    st.session_state.page_num-=1
                    st.rerun()
            with ci:
                st.markdown(f"<div style='text-align:center;padding:10px;background:#1f2937;border-radius:8px'><b>Page {st.session_state.page_num}/{total_pages} — Total {len(results)} — 6 per page</b></div>", unsafe_allow_html=True)
            with cn:
                if st.button("Next ➡️", disabled=st.session_state.page_num==total_pages, use_container_width=True, type="primary", key="next_final2"):
                    st.session_state.page_num+=1
                    st.rerun()
            pg=st.session_state.page_num
            start=(pg-1)*page_size
            display=results[start:start+page_size]
            st.caption(f"Showing {start+1}-{min(start+page_size, len(results))} of {len(results)}")
        else:
            pg=1
            display=results

        cols=st.columns(3)
        for idx in range(6):
            col=cols[idx%3]
            with col:
                if idx < len(display):
                    fn,pn,mc,matched = display[idx]
                    with st.container(border=True):
                        # DIRECT IMAGE LOAD
                        img_bytes = get_page_image_cached(fn, pn)
                        if img_bytes:
                            st.image(img_bytes, use_container_width=True)
                        else:
                            st.error(f"Image failed: Page {pn}")
                            # Fallback: try again without cache
                            pb = get_pdf_bytes_cached(fn)
                            if pb:
                                try:
                                    doc=fitz.open(stream=pb, filetype="pdf")
                                    pix=doc.load_page(pn-1).get_pixmap(dpi=80)
                                    st.image(pix.tobytes("png"), use_container_width=True)
                                    doc.close()
                                except Exception as e:
                                    st.write(f"Error: {e}")

                        st.markdown(f"**Page {pn}**")
                        st.caption(f"{fn}")
                        st.write(f"ALL {mc}: {', '.join(matched)}")
                        is_sel=(fn,pn) in st.session_state.selected
                        if st.checkbox("Add to Basket", key=f"chk_{fn}_{pn}_{idx}_{pg}_{st.session_state.page_num}_cb", value=is_sel):
                            if (fn,pn) not in st.session_state.selected:
                                st.session_state.selected.append((fn,pn))
                                st.session_state.presentation_images[f"{fn}_{pn}"]=img_bytes
                        else:
                            if (fn,pn) in st.session_state.selected:
                                st.session_state.selected.remove((fn,pn))
                                st.session_state.presentation_images.pop(f"{fn}_{pn}", None)
                else:
                    with st.container(border=True):
                        st.caption("Empty slot")

if st.session_state.is_admin:
    st.divider()
    st.header("👑 Admin")
    with st.expander("🔐 Manage File Access", expanded=True):
        acc,sha_acc=get_json_file("data/file_access.json", {})
        cust,_=get_json_file("data/customers.json", [])
        mails=[c.get("mail") for c in cust if c.get("approved")]
        for fn in get_all_pdfs():
            with st.container(border=True):
                st.write(f"**{fn}** — Current: {', '.join(acc.get(fn,['all']))}")
                sel=st.multiselect(f"Allow {fn} for:", options=mails, default=[] if "all" in acc.get(fn,["all"]) else [m for m in acc.get(fn,[]) if m in mails], key=f"acc_{fn}_final")
                if st.button(f"Save {fn}", key=f"save_{fn}_final", type="primary"):
                    acc[fn]=sel if sel else ["all"]
                    save_json_file("data/file_access.json", acc, sha_acc, "access")
                    st.rerun()
    with st.expander("🏷️ Create Brand", expanded=True):
        blist,sha_b=get_json_file("data/brands.json", DEFAULT_BRANDS)
        st.write(f"Current: {', '.join(blist)}")
        nb=st.text_input("New Brand Name", key="new_brand_input")
        if st.button("➕ Create Brand", type="primary", key="create_brand_btn"):
            if nb.strip() and nb.strip() not in blist:
                blist.append(nb.strip())
                save_json_file("data/brands.json", blist, sha_b, f"Add {nb}")
                st.rerun()
    with st.expander("📤 Upload Pricelists", expanded=True):
        ups=st.file_uploader("Choose PDFs", type=["pdf"], accept_multiple_files=True, key="uploader")
        if st.button("⬆️ Upload", key="upload_btn"):
            for f in ups:
                try:
                    safe=f.name.replace(" ","_")
                    fb=f.getvalue()
                    if len(fb)/(1024*1024)>90:
                        rel=get_or_create_release()
                        for a in rel.get_assets():
                            if a.name==safe: a.delete_asset()
                        rel.upload_asset_from_memory(io.BytesIO(fb), len(fb), safe, "application/pdf")
                    else:
                        path=f"pdfs/{safe}"
                        try:
                            ex=repo.get_contents(path)
                            repo.update_file(path, f"Update {safe}", fb, ex.sha)
                        except: repo.create_file(path, f"Add {safe}", fb)
                    acc,sha_acc=get_json_file("data/file_access.json", {})
                    acc[safe]=["all"]
                    save_json_file("data/file_access.json", acc, sha_acc, "default")
                    st.success(f"Uploaded {safe}")
                except Exception as e: st.error(str(e))
