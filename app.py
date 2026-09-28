import streamlit as st
import base64, json, io
import fitz
from PIL import Image
from github import Github

st.set_page_config(page_title="Bathroom AI - FINAL FULL", layout="wide")

try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    GITHUB_REPO_NAME = st.secrets["GITHUB_REPO"]
    ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "Bathroom@123")
except:
    st.error("Add Secrets in Streamlit Cloud")
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
                ex = repo.get_contents(path)
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

def get_pdf_bytes(fname):
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
                        return r.content
        except: pass
    return None

def search_all_matching(pdf_bytes, query):
    words=[w.lower() for w in query.strip().split() if w.strip()][:4]
    total=len(words)
    results=[]
    if total==0: return results
    try:
        doc=fitz.open(stream=pdf_bytes, filetype="pdf")
        for i in range(len(doc)):
            page=doc.load_page(i)
            txt=page.get_text("text").lower()
            matched=[w for w in words if w in txt]
            if len(matched)==total:
                pix = page.get_pixmap(dpi=130, alpha=False)
                img_bytes = pix.tobytes("png")
                results.append((i+1, len(matched), matched, img_bytes))
        doc.close()
    except: pass
    return results

def get_allowed_files(customer_mail, is_admin):
    all_files=get_all_pdfs()
    if is_admin: return all_files
    access,_=get_json_file("data/file_access.json", {})
    allowed=[]
    for fname in all_files:
        mails=access.get(fname, ["all"])
        if "all" in mails or customer_mail.lower() in [m.lower() for m in mails]:
            allowed.append(fname)
    return allowed

if "customer_verified" not in st.session_state: st.session_state.customer_verified=False
if "is_admin" not in st.session_state: st.session_state.is_admin=False
if "customer_email" not in st.session_state: st.session_state.customer_email=""
if "selected" not in st.session_state: st.session_state.selected=[]
if "last_results" not in st.session_state: st.session_state.last_results=[]
if "presentation_images" not in st.session_state: st.session_state.presentation_images={}
if "page_num" not in st.session_state: st.session_state.page_num=1

if not st.session_state.customer_verified and not st.session_state.is_admin:
    st.title("🛁 Pricelist Login")
    t1,t2=st.tabs(["Customer","Admin"])
    with t2:
        pwd=st.text_input("Admin Password", type="password")
        if st.button("Login as Admin", type="primary", use_container_width=True):
            if pwd==ADMIN_PASSWORD:
                st.session_state.is_admin=True
                st.session_state.customer_verified=True
                st.rerun()
    with t1:
        mail=st.text_input("Mail ID")
        if st.button("Login"):
            cust,_=get_json_file("data/customers.json", [])
            f=next((c for c in cust if c.get("mail","").lower()==mail.lower().strip()), None)
            if f and f.get("approved"):
                st.session_state.customer_verified=True
                st.session_state.customer_email=mail
                st.rerun()
            else: st.error("Not found or pending")
        with st.form("signup"):
            st.write("New Signup - Admin gets 🔴 notification")
            n=st.text_input("Name*"); cont=st.text_input("Contact*"); m=st.text_input("Mail*"); city=st.text_input("City*"); pin=st.text_input("Pincode*")
            if st.form_submit_button("Submit"):
                cust,sha=get_json_file("data/customers.json", [])
                cust.append({"name":n,"contact":cont,"mail":m,"city":city,"pincode":pin,"company":"","approved":False})
                save_json_file("data/customers.json", cust, sha, "new cust")
                st.success("Submitted!")
    st.stop()

st.title("Pricelist Search")
top1, top2 = st.columns([3,1])
with top1:
    login_display = st.session_state.customer_email if not st.session_state.is_admin else "Admin"
    st.markdown(f"**Login Name:** {login_display} | {'Admin' if st.session_state.is_admin else 'Customer'}")
with top2:
    if st.button("Logout", use_container_width=True):
        st.session_state.customer_verified=False; st.session_state.is_admin=False; st.session_state.selected=[]; st.rerun()

s1,s2,s3 = st.columns([1,2,1])
with s1:
    brands_data,_=get_json_file("data/brands.json", DEFAULT_BRANDS)
    brand=st.selectbox("Brand", ["All Brands"]+brands_data)
with s2:
    query=st.text_input("Search Pricelist", placeholder="e.g. mint spout")
with s3:
    st.write(""); st.write("")
    do_search = st.button("🔍 SEARCH ALL MATCHES", type="primary", use_container_width=True)

if st.session_state.selected:
    st.divider()
    st.markdown(f"### 🧺 Presentation Basket: **{len(st.session_state.selected)} sheets from multiple searches**")
    st.caption("Search again with different word and add more — All stays here")
    b_cols = st.columns(min(6, len(st.session_state.selected)))
    for idx, (fname,pno) in enumerate(st.session_state.selected):
        b_col = b_cols[idx % 6]
        with b_col:
            img_bytes = st.session_state.presentation_images.get(f"{fname}_{pno}")
            if img_bytes: st.image(img_bytes, use_container_width=True)
            st.caption(f"{fname} P{pno}")
            if st.button("❌ Remove", key=f"rem_{fname}_{pno}_{idx}"):
                st.session_state.selected.remove((fname,pno))
                st.session_state.presentation_images.pop(f"{fname}_{pno}", None)
                st.rerun()
    c1,c2 = st.columns([3,1])
    with c1:
        if st.button(f"📑 Create Presentation PDF ({len(st.session_state.selected)} Sheets)", type="primary", use_container_width=True):
            try:
                new_doc=fitz.open()
                for fname,pno in st.session_state.selected:
                    pdf_bytes=get_pdf_bytes(fname)
                    if pdf_bytes:
                        src=fitz.open(stream=pdf_bytes, filetype="pdf")
                        new_doc.insert_pdf(src, from_page=pno-1, to_page=pno-1)
                        src.close()
                out=new_doc.tobytes()
                new_doc.close()
                st.download_button("📥 Download Presentation.pdf", data=out, file_name="Presentation.pdf", mime="application/pdf", use_container_width=True)
                st.success("Ready!")
            except Exception as e: st.error(f"{e}")
    with c2:
        if st.button("🗑️ Clear Basket", use_container_width=True):
            st.session_state.selected=[]; st.session_state.presentation_images={}; st.rerun()

if do_search:
    if not query.strip():
        st.warning("Type word")
    else:
        all_allowed = get_allowed_files(st.session_state.customer_email, st.session_state.is_admin)
        filtered = all_allowed
        if brand!="All Brands":
            tmp=[f for f in all_allowed if brand.lower() in f.lower()]
            if tmp: filtered=tmp
        final=[]
        prog=st.progress(0)
        for idx,fname in enumerate(filtered):
            pdf_bytes=get_pdf_bytes(fname)
            if pdf_bytes:
                pages=search_all_matching(pdf_bytes, query)
                for p in pages:
                    final.append((fname, p[0], p[1], p[2], p[3]))
            prog.progress((idx+1)/len(filtered))
        prog.empty()
        st.session_state.last_results=final
        st.session_state.page_num=1

left, right = st.columns([1, 2.2])

with left:
    st.markdown("### Uploaded Files:")
    files = get_allowed_files(st.session_state.customer_email, st.session_state.is_admin)
    if not files: st.info("No files assigned. Contact Admin.")
    for fname in files:
        with st.container(border=True):
            st.write(f"**{fname}**")
            c1,c2=st.columns(2)
            with c1:
                if st.button("👁️ View", key=f"view_{fname}", use_container_width=True):
                    pdf_bytes=get_pdf_bytes(fname)
                    if pdf_bytes:
                        doc=fitz.open(stream=pdf_bytes, filetype="pdf")
                        img_bytes = doc.load_page(0).get_pixmap(dpi=100, alpha=False).tobytes("png")
                        st.image(img_bytes, use_container_width=True)
                        doc.close()
            with c2:
                pdf_bytes=get_pdf_bytes(fname)
                if pdf_bytes:
                    st.download_button("📥 Download", data=pdf_bytes, file_name=fname, mime="application/pdf", key=f"dl_{fname}", use_container_width=True)

    st.divider()
    cust_data, sha_c = get_json_file("data/customers.json", [])
    pending=[c for c in cust_data if not c.get("approved")]
    if pending and st.session_state.is_admin:
        st.toast(f"🔴 {len(pending)} new signup pending!", icon="🔔")
        st.markdown(f"### Pending Customers approval: 🔴 {len(pending)} NEW")
    else:
        st.markdown("### Pending Customers approval:")
    for i,c in enumerate(cust_data):
        if not c.get("approved"):
            with st.container(border=True):
                st.write(f"**{c.get('name')}** {c.get('mail')} {c.get('contact')}")
                if st.session_state.is_admin:
                    if st.button("✅ Approve", key=f"ap_{i}", type="primary", use_container_width=True):
                        cust_data[i]["approved"]=True
                        save_json_file("data/customers.json", cust_data, sha_c, "approve")
                        st.rerun()
                    if st.button("❌ Delete", key=f"del_{i}", use_container_width=True):
                        cust_data.pop(i)
                        save_json_file("data/customers.json", cust_data, sha_c, "del")
                        st.rerun()

    st.divider()
    st.markdown("### List of Customers:")
    for c in cust_data:
        if c.get("approved"):
            st.write(f"• {c.get('name')} - {c.get('mail')}")

with right:
    if not st.session_state.last_results:
        st.info("Search shows ALL pages where ALL words match — 6 per page — If 3 results, 3 empty slots — Select to basket — Search again to add more — Use Next button for page 2")
    else:
        results=st.session_state.last_results
        st.success(f"Found {len(results)} pages where ALL words match — 6 per page")

        page_size=6
        total_pages=(len(results)+page_size-1)//page_size

        if total_pages>1:
            c_prev, c_info, c_next = st.columns([1,2,1])
            with c_prev:
                if st.button("⬅️ Previous", disabled=st.session_state.page_num==1, use_container_width=True):
                    st.session_state.page_num -= 1
                    st.rerun()
            with c_info:
                st.markdown(f"<div style='text-align:center; padding:10px; background:#1f2937; border-radius:8px;'><b>Page {st.session_state.page_num} / {total_pages} — Total {len(results)} found — 6 per page</b></div>", unsafe_allow_html=True)
            with c_next:
                if st.button("Next ➡️", disabled=st.session_state.page_num==total_pages, use_container_width=True, type="primary"):
                    st.session_state.page_num += 1
                    st.rerun()
            pg = st.session_state.page_num
            start=(pg-1)*page_size
            display=results[start:start+page_size]
            st.caption(f"Showing {start+1}-{min(start+page_size, len(results))} of {len(results)}")
        else:
            pg=1
            display=results
            st.caption(f"Showing all {len(results)} results")

        cols=st.columns(3)
        for idx in range(6):
            col=cols[idx % 3]
            with col:
                if idx < len(display):
                    fname, pno, mc, matched, img_bytes = display[idx]
                    with st.container(border=True):
                        st.image(img_bytes, caption=f"Page {pno} - {fname}", use_container_width=True)
                        st.write(f"ALL {mc}: {', '.join(matched)}")
                        is_sel=(fname,pno) in st.session_state.selected
                        if st.checkbox("Add to Basket", key=f"chk_{fname}_{pno}_{idx}_{pg}", value=is_sel):
                            if (fname,pno) not in st.session_state.selected:
                                st.session_state.selected.append((fname,pno))
                                st.session_state.presentation_images[f"{fname}_{pno}"]=img_bytes
                        else:
                            if (fname,pno) in st.session_state.selected:
                                st.session_state.selected.remove((fname,pno))
                                st.session_state.presentation_images.pop(f"{fname}_{pno}", None)
                else:
                    with st.container(border=True):
                        st.write(" "); st.caption("Empty slot"); st.write(" "); st.write(" "); st.write(" ")

if st.session_state.is_admin:
    st.divider()
    st.header("👑 Admin - File Access Control")

    with st.expander("🔐 Manage File Access - Fantini to A, Hansgrohe to B", expanded=True):
        access_data, sha_acc = get_json_file("data/file_access.json", {})
        cust_data,_ = get_json_file("data/customers.json", [])
        mails=[c.get("mail") for c in cust_data if c.get("approved")]
        if not mails:
            st.warning("No approved customers yet — Approve in Pending above")
        for fname in get_all_pdfs():
            with st.container(border=True):
                st.write(f"**{fname}** — Current: {', '.join(access_data.get(fname, ['all']))}")
                sel=st.multiselect(f"Allow {fname} for:", options=mails, default=[] if "all" in access_data.get(fname, ["all"]) else [m for m in access_data.get(fname, []) if m in mails], key=f"acc_{fname}")
                if st.button(f"Save Access {fname}", key=f"save_{fname}", type="primary"):
                    access_data[fname]=sel if sel else ["all"]
                    save_json_file("data/file_access.json", access_data, sha_acc, "access")
                    st.success(f"Saved {fname} -> {access_data[fname]}")
                    st.rerun()

    with st.expander("🏷️ Create Brand - Add New Brand", expanded=True):
        brands_list, sha_b = get_json_file("data/brands.json", DEFAULT_BRANDS)
        st.write(f"Current Brands: {', '.join(brands_list)}")
        new_b=st.text_input("New Brand Name (e.g. Fantini, Gessi)")
        if st.button("➕ Create Brand", type="primary"):
            if new_b.strip():
                if new_b.strip() not in brands_list:
                    brands_list.append(new_b.strip())
                    save_json_file("data/brands.json", brands_list, sha_b, f"Add brand {new_b}")
                    st.success(f"Brand '{new_b}' created!")
                    st.rerun()
                else: st.warning("Already exists")
            else: st.warning("Enter brand name")

    with st.expander("📤 Upload Pricelists - ANY NAME", expanded=True):
        up_files=st.file_uploader("Choose PDFs", type=["pdf"], accept_multiple_files=True)
        if st.button("⬆️ Upload"):
            for f in up_files:
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
                    access_data, sha_acc = get_json_file("data/file_access.json", {})
                    access_data[safe]=["all"]
                    save_json_file("data/file_access.json", access_data, sha_acc, "default all")
                    st.success(f"Uploaded {safe}")
                except Exception as e: st.error(f"{e}")
