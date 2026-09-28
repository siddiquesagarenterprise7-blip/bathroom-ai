import streamlit as st
import base64, json, io
import fitz
from PIL import Image
from github import Github

st.set_page_config(page_title="PRODUCT SEARCH -PRESENTATION", layout="wide")

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
                ex = repo.get_contents(path)
                repo.update_file(path, msg, content, ex.sha)
            except: repo.create_file(path, msg, content)
        st.cache_data.clear()
    except Exception as e: st.error(f"Save fail {e}")

def ensure_never_delete():
    try: repo.get_contents("data")
    except:
        try: repo.create_file("data/.gitkeep", "init", "keep")
        except: pass
    for p,d in [("data/brands.json", DEFAULT_BRANDS), ("data/customers.json", []), ("data/approvals.json", [])]:
        data,_ = get_json_file(p, None)
        if data is None: save_json_file(p, d, None, "init")
ensure_never_delete()

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

def search_exact_sheets(pdf_bytes, query):
    words=[w.lower() for w in query.strip().split() if w.strip()][:4]
    total=len(words)
    results=[]
    try:
        doc=fitz.open(stream=pdf_bytes, filetype="pdf")
        for i in range(len(doc)):
            if len(results)>=3: break
            page=doc.load_page(i)
            txt=page.get_text("text").lower()
            matched=[w for w in words if w in txt]
            if len(matched)==total and total>0:
                pix=page.get_pixmap(dpi=150)
                pil=Image.open(io.BytesIO(pix.tobytes("png")))
                results.append((i+1, len(matched), matched, pil))
        doc.close()
    except: pass
    return results

# SESSION - KEEP SELECTED ACROSS SEARCHES
if "customer_verified" not in st.session_state: st.session_state.customer_verified=False
if "is_admin" not in st.session_state: st.session_state.is_admin=False
if "customer_email" not in st.session_state: st.session_state.customer_email=""
if "selected" not in st.session_state: st.session_state.selected=[] # THIS NOW KEEPS ACROSS MULTIPLE SEARCHES
if "last_results" not in st.session_state: st.session_state.last_results=[]
if "presentation_images" not in st.session_state: st.session_state.presentation_images={} # Store images for basket

# LOGIN
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
            st.write("New Signup")
            n=st.text_input("Name*"); cont=st.text_input("Contact*"); m=st.text_input("Mail*"); city=st.text_input("City*"); pin=st.text_input("Pincode*")
            if st.form_submit_button("Submit for Approval"):
                cust,sha=get_json_file("data/customers.json", [])
                cust.append({"name":n,"contact":cont,"mail":m,"city":city,"pincode":pin,"company":"","approved":False})
                save_json_file("data/customers.json", cust, sha, "new cust")
                st.success("Submitted")
    st.stop()

# TOP BAR
st.title("Pricelist Search - MULTI SEARCH PRESENTATION")
login_display = st.session_state.customer_email if not st.session_state.is_admin else "Admin"
st.markdown(f"**Login Name:** {login_display}")

col_logout, col_brand, col_search = st.columns([0.7,1.2,2.1])
with col_logout:
    if st.button("Logout"):
        st.session_state.customer_verified=False; st.session_state.is_admin=False; st.session_state.selected=[]; st.session_state.presentation_images={}; st.rerun()
with col_brand:
    brands_data,_=get_json_file("data/brands.json", DEFAULT_BRANDS)
    brand=st.selectbox("Brand", ["All Brands"]+brands_data, label_visibility="collapsed")
with col_search:
    query=st.text_input("Search Pricelist", placeholder="e.g. mint spout", label_visibility="collapsed")

# PRESENTATION BASKET - ALWAYS VISIBLE ON TOP
st.divider()
basket_col1, basket_col2 = st.columns([3,1])
with basket_col1:
    st.markdown(f"### 🧺 Presentation Basket: **{len(st.session_state.selected)} sheets selected from multiple searches**")
    if st.session_state.selected:
        st.write("You can search again with different words and add more sheets — All will stay here:")
        # Show basket as small thumbnails
        b_cols = st.columns(min(6, len(st.session_state.selected)))
        for idx, (fname,pno) in enumerate(st.session_state.selected):
            b_col = b_cols[idx % 6]
            with b_col:
                img = st.session_state.presentation_images.get(f"{fname}_{pno}")
                if img:
                    st.image(img, use_container_width=True)
                st.caption(f"{fname}\nPage {pno}")
                if st.button("❌ Remove", key=f"rem_basket_{fname}_{pno}_{idx}"):
                    st.session_state.selected.remove((fname,pno))
                    st.session_state.presentation_images.pop(f"{fname}_{pno}", None)
                    st.rerun()
with basket_col2:
    if st.session_state.selected:
        if st.button(f"📑 Create Presentation PDF\n({len(st.session_state.selected)} Sheets)", type="primary", use_container_width=True):
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
                st.download_button("📥 Download Presentation.pdf", data=out, file_name="Presentation.pdf", mime="application/pdf", use_container_width=True, key="dl_present_top")
                st.success("Ready!")
            except Exception as e:
                st.error(f"Failed: {e}")
        if st.button("🗑️ Clear All", use_container_width=True):
            st.session_state.selected=[]
            st.session_state.presentation_images={}
            st.rerun()

# SEARCH BUTTON - NOW DOES NOT CLEAR BASKET
if st.button("🔍 SEARCH - Add more to basket (Multi Search)", type="primary", use_container_width=True):
    all_files=get_all_pdfs()
    filtered=all_files
    if brand!="All Brands":
        tmp=[f for f in all_files if brand.lower() in f.lower()]
        if tmp: filtered=tmp
    if not query.strip():
        st.warning("Type to search")
    else:
        final=[]
        for fname in filtered:
            if len(final)>=3: break
            pdf_bytes=get_pdf_bytes(fname)
            if pdf_bytes:
                pages=search_exact_sheets(pdf_bytes, query)
                for p in pages:
                    final.append((fname, p[0], p[1], p[2], p[3]))
                    if len(final)>=3: break
        st.session_state.last_results=final[:3]

# MAIN SPLIT
left, right = st.columns([1, 2.2])

with left:
    st.markdown("### Uploaded Files:")
    st.markdown("**<span style='background-color: yellow;'>Uploaded files to list down here. With View and Download button</span>**", unsafe_allow_html=True)
    files=get_all_pdfs()
    for fname in files:
        with st.container(border=True):
            st.write(f"**{fname}**")
            c1,c2=st.columns(2)
            with c1:
                if st.button("👁️ View", key=f"view_{fname}", use_container_width=True):
                    pdf_bytes=get_pdf_bytes(fname)
                    if pdf_bytes:
                        doc=fitz.open(stream=pdf_bytes, filetype="pdf")
                        pg=doc.load_page(0)
                        pix=pg.get_pixmap(dpi=120)
                        pil=Image.open(io.BytesIO(pix.tobytes("png")))
                        st.image(pil, caption=f"First page {fname}", use_container_width=True)
                        doc.close()
            with c2:
                pdf_bytes=get_pdf_bytes(fname)
                if pdf_bytes:
                    st.download_button("📥 Download", data=pdf_bytes, file_name=fname, mime="application/pdf", key=f"dl_{fname}", use_container_width=True)

    st.divider()
    st.markdown("### Pending Customers approval:")
    cust_data, sha_c = get_json_file("data/customers.json", [])
    for i,c in enumerate(cust_data):
        if not c.get("approved"):
            with st.container(border=True):
                st.write(f"**{c.get('name')}**\n{c.get('mail')}\n{c.get('contact')} | {c.get('city')}")
                if st.session_state.is_admin:
                    if st.button("✅ Approve", key=f"appr_{i}", type="primary", use_container_width=True):
                        cust_data[i]["approved"]=True
                        save_json_file("data/customers.json", cust_data, sha_c, f"Approve {c.get('mail')}")
                        st.rerun()

    st.divider()
    st.markdown("### List of Customers:")
    cust_data,_=get_json_file("data/customers.json", [])
    for c in cust_data:
        if c.get("approved"):
            st.write(f"• **{c.get('name')}** - {c.get('mail')}")

with right:
    st.markdown("### Search results below like these. Customer can select from these files to add to create a presentation file")
    if not st.session_state.last_results:
        st.info("Search e.g. 'mint spout' -> Select 1-2 sheets -> Search again 'washbasin' -> Select more -> All stays in basket on top")
    else:
        results=st.session_state.last_results
        st.success(f"Found {len(results)} sheets - Select to add to basket (Basket keeps selections from multiple searches)")
        cols=st.columns(3)
        for idx, (fname, pno, match_count, matched, pil_img) in enumerate(results):
            col=cols[idx % 3]
            with col:
                with st.container(border=True):
                    st.image(pil_img, use_container_width=True)
                    st.caption(f"Page {pno} - {fname}")
                    st.write(f"ALL {match_count}: {', '.join(matched)}")
                    # Checkbox that ADDS to basket and KEEPS it
                    is_selected = (fname,pno) in st.session_state.selected
                    chk_key=f"chk_{fname}_{pno}_{query}"
                    # Use checkbox with value based on basket
                    if st.checkbox("Add to Presentation Basket", key=chk_key, value=is_selected):
                        if (fname,pno) not in st.session_state.selected:
                            st.session_state.selected.append((fname,pno))
                            st.session_state.presentation_images[f"{fname}_{pno}"] = pil_img
                            st.toast(f"Added Page {pno} to basket - Total {len(st.session_state.selected)}")
                    else:
                        if (fname,pno) in st.session_state.selected:
                            st.session_state.selected.remove((fname,pno))
                            st.session_state.presentation_images.pop(f"{fname}_{pno}", None)

# ADMIN UPLOAD
if st.session_state.is_admin:
    st.divider()
    st.subheader("Admin Upload")
    up_files=st.file_uploader("Upload Pricelists - ANY NAME", type=["pdf"], accept_multiple_files=True)
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
                st.success(f"Uploaded {safe}")
            except Exception as e: st.error(f"{e}")
