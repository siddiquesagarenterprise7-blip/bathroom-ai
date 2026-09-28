import streamlit as st
import base64, json, io
import fitz
from github import Github

st.set_page_config(page_title="Bathroom AI - 150MB Single File", layout="wide")

try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    GITHUB_REPO_NAME = st.secrets["GITHUB_REPO"]
    ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "Bathroom@123")
except:
    st.error("Add Secrets: GITHUB_TOKEN, GITHUB_REPO, ADMIN_PASSWORD")
    st.stop()

@st.cache_resource
def get_repo():
    return Github(GITHUB_TOKEN).get_repo(GITHUB_REPO_NAME)
repo = get_repo()

def get_json_file(path, default):
    try:
        file = repo.get_contents(path)
        content = base64.b64decode(file.content).decode('utf-8')
        return json.loads(content), file.sha
    except:
        return default, None

def save_json_file(path, data, sha, message):
    content = json.dumps(data, indent=2, ensure_ascii=False)
    if sha:
        repo.update_file(path, message, content, sha)
    else:
        try:
            repo.create_file(path, message, content)
        except:
            try:
                existing = repo.get_contents(path)
                repo.update_file(path, message, content, existing.sha)
            except Exception as e:
                st.error(f"Save failed {path}: {e}")

def get_or_create_release():
    try:
        for r in repo.get_releases():
            if r.tag_name == "pdfs-storage":
                return r
        return repo.create_git_release(tag="pdfs-storage", name="PDF Storage 150MB", message="Large files up to 150MB single file - NO SPLIT", draft=False, prerelease=False)
    except Exception as e:
        st.error(f"Release error: {e}")
        return None

if "customer_verified" not in st.session_state:
    st.session_state.customer_verified = False
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False
if "customer_email" not in st.session_state:
    st.session_state.customer_email = ""

DEFAULT_BRANDS = ["Fantini", "Gessi", "Hansgrohe", "Jaquar", "Grohe"]

if not st.session_state.customer_verified and not st.session_state.is_admin:
    st.title("🛁 Bathroom Product Login")
    tab1, tab2 = st.tabs(["👤 Customer Login / Signup", "🔐 Admin Login"])
    with tab2:
        admin_pwd = st.text_input("Admin Password", type="password", key="admin_tab")
        if st.button("Login as Admin", type="primary", use_container_width=True):
            if admin_pwd == ADMIN_PASSWORD:
                st.session_state.is_admin = True
                st.session_state.customer_verified = True
                st.rerun()
            else:
                st.error("Wrong Password")
    with tab1:
        with st.container(border=True):
            login_mail = st.text_input("Enter your Mail ID to Login")
            if st.button("Login"):
                customers, _ = get_json_file("data/customers.json", [])
                found = next((c for c in customers if c.get("mail","").lower() == login_mail.lower().strip()), None)
                if not found:
                    st.error("Mail ID not found. Signup below.")
                elif not found.get("approved", False):
                    st.warning("⏳ Pending Admin approval.")
                else:
                    st.session_state.customer_verified = True
                    st.session_state.customer_email = login_mail
                    st.rerun()
        st.divider()
        with st.form("signup_form"):
            name = st.text_input("Name*")
            contact = st.text_input("Contact No*")
            mail = st.text_input("Mail ID*")
            city = st.text_input("City*")
            pincode = st.text_input("Pincode*")
            company = st.text_input("Company Name (Optional)")
            submit = st.form_submit_button("Submit for Approval", use_container_width=True)
            if submit:
                if not all([name.strip(), contact.strip(), mail.strip(), city.strip(), pincode.strip()]):
                    st.error("Fill all *")
                else:
                    customers, sha = get_json_file("data/customers.json", [])
                    if any(c.get("mail","").lower() == mail.lower().strip() for c in customers):
                        st.error("Already registered.")
                    else:
                        customers.append({"name":name,"contact":contact,"mail":mail.strip(),"city":city,"pincode":pincode,"company":company,"approved": False})
                        save_json_file("data/customers.json", customers, sha, f"New {name}")
                        st.success("✅ Submitted! Wait for approval.")
    st.stop()

st.title("🛁 Bathroom Product Search")
if st.session_state.is_admin:
    st.success("✅ Admin Mode - 150MB Single File - NO SPLIT - FIXED")
else:
    st.success(f"Welcome {st.session_state.customer_email}")

if st.button("Logout"):
    st.session_state.customer_verified = False
    st.session_state.is_admin = False
    st.rerun()

brands_data, _ = get_json_file("data/brands.json", DEFAULT_BRANDS)
if not brands_data: brands_data = DEFAULT_BRANDS
brand_options = ["All Brands"] + brands_data
col1, col2 = st.columns([1,2])
with col1: brand_filter = st.selectbox("Brand", brand_options)
with col2: search_query = st.text_input("Search Products", placeholder="e.g. 200mm Round shower")
search_btn = st.button("🔍 Search Products", use_container_width=True)
if "page_num" not in st.session_state: st.session_state.page_num = 0

approvals_data, _ = get_json_file("data/approvals.json", [])
def is_approved(filename):
    for a in approvals_data:
        if a["file"]==filename and a.get("approved"): return True
    return False

if search_btn or search_query or brand_filter!="All Brands" or st.session_state.page_num>0:
    all_files = []
    try:
        contents = repo.get_contents("pdfs")
        all_files += [c.name for c in contents if c.name.lower().endswith(".pdf") and not c.name.upper().startswith("PRICELIST_")]
    except: pass
    try:
        release = get_or_create_release()
        if release:
            for asset in release.get_assets():
                if asset.name.lower().endswith(".pdf") and not asset.name.upper().startswith("PRICELIST_"):
                    all_files.append(asset.name)
    except: pass

    filtered = all_files
    if brand_filter!="All Brands": filtered = [f for f in filtered if brand_filter.lower() in f.lower()]
    if search_query: filtered = [f for f in filtered if search_query.lower() in f.lower()]
    if not st.session_state.is_admin: filtered = [f for f in filtered if is_approved(f)]

    st.write(f"Found {len(filtered)} products")
    per_page=20
    total=len(filtered)
    total_pages=(total+per_page-1)//per_page if total>0 else 1
    start=st.session_state.page_num*per_page
    end=min(start+per_page, total)
    c1,c2=st.columns(2)
    with c1:
        if st.button("⬅️ Previous", disabled=st.session_state.page_num==0):
            st.session_state.page_num-=1; st.rerun()
    with c2:
        if st.button("Next ➡️", disabled=st.session_state.page_num>=total_pages-1):
            st.session_state.page_num+=1; st.rerun()

    for filename in filtered[start:end]:
        with st.container(border=True):
            st.write(f"**{filename}**")
            try:
                pdf_bytes = None
                try:
                    file_content = repo.get_contents(f"pdfs/{filename}")
                    pdf_bytes = base64.b64decode(file_content.content)
                except:
                    release = get_or_create_release()
                    if release:
                        import requests
                        for asset in release.get_assets():
                            if asset.name == filename:
                                r = requests.get(asset.browser_download_url)
                                pdf_bytes = r.content
                                break
                if pdf_bytes:
                    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                    page = doc.load_page(0)
                    pix = page.get_pixmap(dpi=180)
                    img_bytes = pix.tobytes("png")
                    st.image(img_bytes, use_container_width=True)
                    st.download_button(f"📥 Download {filename}", data=pdf_bytes, file_name=filename, mime="application/pdf", key=f"dl_{filename}")
            except Exception as e:
                st.error(f"{e}")

st.divider()
st.header("💰 Pricelists - View & Download")
pricelists = []
try:
    contents = repo.get_contents("pdfs")
    pricelists += [(c.name, "folder") for c in contents if c.name.upper().startswith("PRICELIST_")]
except: pass
try:
    release = get_or_create_release()
    if release:
        for asset in release.get_assets():
            if asset.name.upper().startswith("PRICELIST_"):
                pricelists.append((asset.name, "release", asset))
except: pass

if not pricelists:
    st.info("No pricelists yet.")
else:
    for item in pricelists:
        name = item[0]
        with st.container(border=True):
            col_pl1, col_pl2 = st.columns([3,1])
            with col_pl1:
                st.write(f"**{name.replace('PRICELIST_','').replace('.pdf','')} Pricelist**")
            with col_pl2:
                try:
                    import requests
                    pdf_bytes = None
                    if item[1] == "folder":
                        file_content = repo.get_contents(f"pdfs/{name}")
                        pdf_bytes = base64.b64decode(file_content.content)
                    else:
                        r = requests.get(item[2].browser_download_url)
                        pdf_bytes = r.content
                    if pdf_bytes:
                        st.download_button(f"📥 Download", data=pdf_bytes, file_name=name, mime="application/pdf", key=f"pl_dl_{name}", use_container_width=True)
                except Exception as e:
                    st.error(f"{e}")

if st.session_state.is_admin:
    st.divider()
    st.header("👑 Admin Panel - 150MB Single File NO SPLIT - FIXED")
    with st.expander("🏷️ Create / Manage Brands", expanded=True):
        brands_data, sha = get_json_file("data/brands.json", DEFAULT_BRANDS)
        if not brands_data: brands_data = DEFAULT_BRANDS
        for i, b in enumerate(brands_data):
            col_b1, col_b2 = st.columns([3,1])
            with col_b1: st.write(f"• {b}")
            with col_b2:
                if st.button("Delete", key=f"del_brand_{i}"):
                    brands_data.pop(i)
                    save_json_file("data/brands.json", brands_data, sha, f"Deleted {b}")
                    st.rerun()
        new_brand = st.text_input("New Brand Name", placeholder="e.g. Kohler")
        if st.button("Add Brand", type="primary"):
            if not new_brand.strip(): st.error("Enter brand")
            elif new_brand.strip() in brands_data: st.error("Exists")
            else:
                brands_data.append(new_brand.strip())
                save_json_file("data/brands.json", brands_data, sha, f"Added {new_brand}")
                st.rerun()

    with st.expander("👥 Approve Customer Logins", expanded=False):
        customers, sha = get_json_file("data/customers.json", [])
        pending = [c for c in customers if not c.get("approved", False)]
        st.write(f"Pending: {len(pending)} | Total: {len(customers)}")
        for i, c in enumerate(customers):
            if not c.get("approved", False):
                col_a, col_b, col_c = st.columns([3,1,1])
                with col_a: st.write(f"**{c['name']}** | {c['mail']}")
                with col_b:
                    if st.button("✅ Approve", key=f"cust_app_{i}"):
                        customers[i]["approved"] = True
                        save_json_file("data/customers.json", customers, sha, f"Approved {c['mail']}")
                        st.rerun()
                with col_c:
                    if st.button("❌ Delete", key=f"cust_del_{i}"):
                        customers.pop(i)
                        save_json_file("data/customers.json", customers, sha, f"Deleted {c['mail']}")
                        st.rerun()

    with st.expander("📤 Upload Product PDFs - 150MB SINGLE FILE NO SPLIT", expanded=False):
        st.success("✅ FIXED - NO SPLIT - 150MB as single file via Releases")
        try: repo.get_contents("pdfs")
        except:
            try: repo.create_file("pdfs/.gitkeep", "Create", "keep")
            except: pass
        up_brand = st.selectbox("Select Brand", brands_data, key="up_prod_brand")
        up_files = st.file_uploader("Choose PDFs - Max 150MB Single File", type=["pdf"], accept_multiple_files=True, key="up_prod")
        if st.button("Upload 150MB Single File to GitHub", type="primary"):
            if not up_files: st.error("Select file")
            for f in up_files:
                try:
                    safe_name = f.name.replace(" ", "_")
                    file_bytes = f.getvalue()
                    size_mb = len(file_bytes)/(1024*1024)
                    st.write(f"Uploading {safe_name} - {size_mb:.1f}MB")

                    if size_mb > 150:
                        st.error(f">150MB blocked. Compress.")
                        continue

                    if size_mb > 90:
                        release = get_or_create_release()
                        if not release:
                            st.error("Release failed. Check token.")
                            continue
                        for asset in release.get_assets():
                            if asset.name == f"{up_brand}_{safe_name}":
                                asset.delete_asset()
                        # FIXED LINE - NO SPLIT SINGLE FILE
                        release.upload_asset_from_memory(io.BytesIO(file_bytes), len(file_bytes), f"{up_brand}_{safe_name}", "application/pdf")
                        st.success(f"✅ Uploaded {size_mb:.1f}MB as SINGLE FILE to Releases! NO SPLIT!")
                    else:
                        path = f"pdfs/{up_brand}_{safe_name}"
                        try:
                            existing = repo.get_contents(path)
                            repo.update_file(path, f"Update {safe_name}", file_bytes, existing.sha)
                        except:
                            repo.create_file(path, f"Add {safe_name}", file_bytes)
                        st.success(f"✅ Uploaded {size_mb:.1f}MB as SINGLE FILE to pdfs/ folder")

                    curr_approvals, curr_sha = get_json_file("data/approvals.json", [])
                    fname = f"{up_brand}_{safe_name}"
                    if not any(x["file"]==fname for x in curr_approvals):
                        curr_approvals.append({"brand":up_brand,"file":fname,"approved":False})
                        save_json_file("data/approvals.json", curr_approvals, curr_sha, f"Add approval {fname}")
                except Exception as e:
                    st.error(f"Failed: {e}")

    with st.expander("💰 Upload Pricelists - 150MB Single File", expanded=False):
        pl_brand = st.selectbox("Select Brand for Pricelist", brands_data, key="pl_brand")
        pl_files = st.file_uploader("Choose Pricelist PDFs - Max 150MB", type=["pdf"], accept_multiple_files=True, key="pl_files")
        if st.button("Upload Pricelist 150MB Single", type="primary", key="up_pl_btn"):
            for f in pl_files:
                try:
                    safe_name = f.name.replace(" ", "_")
                    file_bytes = f.getvalue()
                    size_mb = len(file_bytes)/(1024*1024)
                    fname = f"PRICELIST_{pl_brand}_{safe_name}"
                    if size_mb > 90:
                        release = get_or_create_release()
                        for asset in release.get_assets():
                            if asset.name == fname:
                                asset.delete_asset()
                        # FIXED LINE - NO SPLIT SINGLE FILE
                        release.upload_asset_from_memory(io.BytesIO(file_bytes), len(file_bytes), fname, "application/pdf")
                        st.success(f"✅ Pricelist {size_mb:.1f}MB SINGLE FILE to Releases! NO SPLIT!")
                    else:
                        path = f"pdfs/{fname}"
                        try:
                            existing = repo.get_contents(path)
                            repo.update_file(path, f"Update {pl_brand}", file_bytes, existing.sha)
                        except:
                            repo.create_file(path, f"Add {pl_brand}", file_bytes)
                        st.success(f"✅ Pricelist SINGLE FILE uploaded!")
                except Exception as e:
                    st.error(f"{e}")

    with st.expander("✅ Approve Files"):
        approvals_list, sha = get_json_file("data/approvals.json", [])
        for i, a in enumerate(approvals_list):
            col_a, col_b = st.columns([3,1])
            with col_a: st.write(f"{a['brand']} - {a['file']} - {'✅' if a.get('approved') else '⏳'}")
            with col_b:
                if not a.get("approved"):
                    if st.button("Approve", key=f"pdf_app_{i}"):
                        approvals_list[i]["approved"]=True
                        save_json_file("data/approvals.json", approvals_list, sha, f"Approved {a['file']}")
                        st.rerun()
