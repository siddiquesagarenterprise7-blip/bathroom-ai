import streamlit as st
import base64, json
import fitz
from github import Github

st.set_page_config(page_title="Bathroom AI - Brands + Pricelist", layout="wide")

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

if "customer_verified" not in st.session_state:
    st.session_state.customer_verified = False
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False
if "customer_email" not in st.session_state:
    st.session_state.customer_email = ""

# DEFAULT BRANDS
DEFAULT_BRANDS = ["Fantini", "Gessi", "Hansgrohe", "Jaquar", "Grohe"]

# ====== LOGIN PAGE ======
if not st.session_state.customer_verified and not st.session_state.is_admin:
    st.title("🛁 Bathroom Product Login")
    tab1, tab2 = st.tabs(["👤 Customer Login / Signup", "🔐 Admin Login"])
    with tab2:
        st.subheader("Admin Login")
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
            st.write("**Already Signed Up? Login**")
            login_mail = st.text_input("Enter your Mail ID to Login")
            if st.button("Login"):
                customers, _ = get_json_file("data/customers.json", [])
                found = next((c for c in customers if c.get("mail","").lower() == login_mail.lower().strip()), None)
                if not found:
                    st.error("Mail ID not found. Please Signup below.")
                elif not found.get("approved", False):
                    st.warning("⏳ Your account is pending Admin approval. Contact Admin.")
                else:
                    st.session_state.customer_verified = True
                    st.session_state.customer_email = login_mail
                    st.session_state.is_admin = False
                    st.rerun()
        st.divider()
        st.write("**New Customer Signup**")
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
                    st.error("Fill all * fields")
                else:
                    customers, sha = get_json_file("data/customers.json", [])
                    if any(c.get("mail","").lower() == mail.lower().strip() for c in customers):
                        st.error("This Mail ID already registered. Use Login above.")
                    else:
                        customers.append({"name":name,"contact":contact,"mail":mail.strip(),"city":city,"pincode":pincode,"company":company,"approved": False})
                        save_json_file("data/customers.json", customers, sha, f"New customer {name} pending")
                        st.success("✅ Signup submitted! Wait for Admin approval.")
    st.stop()

# ====== MAIN APP ======
st.title("🛁 Bathroom Product Search")
if st.session_state.is_admin:
    st.success("✅ Admin Mode - You can approve customers, create brands, PDFs & Pricelists")
else:
    st.success(f"Welcome {st.session_state.customer_email}")

if st.button("Logout"):
    st.session_state.customer_verified = False
    st.session_state.is_admin = False
    st.session_state.customer_email = ""
    st.rerun()

# Load Brands Dynamically
brands_data, brands_sha = get_json_file("data/brands.json", DEFAULT_BRANDS)
if not brands_data:
    brands_data = DEFAULT_BRANDS
brand_options = ["All Brands"] + brands_data

col1, col2 = st.columns([1,2])
with col1:
    brand_filter = st.selectbox("Brand", brand_options)
with col2:
    search_query = st.text_input("Search Products", placeholder="e.g. 200mm Round shower")

search_btn = st.button("🔍 Search Products", use_container_width=True)
if "page_num" not in st.session_state:
    st.session_state.page_num = 0

approvals_data, approvals_sha = get_json_file("data/approvals.json", [])
def is_approved(filename):
    for a in approvals_data:
        if a["file"]==filename and a.get("approved"):
            return True
    return False

if search_btn or search_query or brand_filter!="All Brands" or st.session_state.page_num>0:
    try:
        contents = repo.get_contents("pdfs")
        all_files = [c.name for c in contents if c.name.lower().endswith(".pdf") and not c.name.startswith("PRICELIST_")]
    except:
        all_files = []
        st.warning("Create pdfs/.gitkeep in GitHub first")
    filtered = all_files
    if brand_filter!="All Brands":
        filtered = [f for f in filtered if brand_filter.lower() in f.lower()]
    if search_query:
        filtered = [f for f in filtered if search_query.lower() in f.lower()]
    if not st.session_state.is_admin:
        filtered = [f for f in filtered if is_approved(f)]
    st.write(f"Found {len(filtered)} products")
    per_page=20
    total=len(filtered)
    total_pages=(total+per_page-1)//per_page if total>0 else 1
    start=st.session_state.page_num*per_page
    end=min(start+per_page, total)
    c1,c2=st.columns(2)
    with c1:
        if st.button("⬅️ Previous", disabled=st.session_state.page_num==0):
            st.session_state.page_num-=1
            st.rerun()
    with c2:
        if st.button("Next ➡️", disabled=st.session_state.page_num>=total_pages-1):
            st.session_state.page_num+=1
            st.rerun()
    for filename in filtered[start:end]:
        with st.container(border=True):
            st.write(f"**{filename}**")
            try:
                file_content = repo.get_contents(f"pdfs/{filename}")
                pdf_bytes = base64.b64decode(file_content.content)
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                page = doc.load_page(0)
                pix = page.get_pixmap(dpi=180)
                img_bytes = pix.tobytes("png")
                st.image(img_bytes, use_container_width=True)
                st.download_button(f"📥 Download {filename}", data=img_bytes, file_name=f"{filename}_page1.png", mime="image/png", key=f"dl_{filename}")
            except Exception as e:
                st.error(f"Preview failed: {e}")

st.divider()

# ====== PRICELIST SECTION - VISIBLE TO CUSTOMER ======
st.header("💰 Pricelists - View & Download")
try:
    contents = repo.get_contents("pdfs")
    pricelists = [c.name for c in contents if c.name.upper().startswith("PRICELIST_") and c.name.lower().endswith(".pdf")]
except:
    pricelists = []

if not pricelists:
    st.info("No pricelists uploaded yet. Admin can upload in Admin Panel.")
else:
    for pl in pricelists:
        with st.container(border=True):
            col_pl1, col_pl2 = st.columns([3,1])
            with col_pl1:
                # Remove PRICELIST_ prefix for display
                display_name = pl.replace("PRICELIST_","").replace(".pdf","")
                st.write(f"**{display_name} Pricelist**")
                st.caption(pl)
            with col_pl2:
                try:
                    file_content = repo.get_contents(f"pdfs/{pl}")
                    pdf_bytes = base64.b64decode(file_content.content)
                    st.download_button(f"📥 Download Pricelist", data=pdf_bytes, file_name=pl, mime="application/pdf", key=f"pl_dl_{pl}", use_container_width=True)
                except Exception as e:
                    st.error(f"{e}")

# ====== ADMIN PANEL ======
if st.session_state.is_admin:
    st.divider()
    st.header("👑 Admin Panel")

    # 1. CREATE BRANDS
    with st.expander("🏷️ Create / Manage Brands - NEW", expanded=True):
        st.write("Current Brands:")
        brands_data, sha = get_json_file("data/brands.json", DEFAULT_BRANDS)
        if not brands_data:
            brands_data = DEFAULT_BRANDS

        # Show brands with delete
        for i, b in enumerate(brands_data):
            col_b1, col_b2 = st.columns([3,1])
            with col_b1:
                st.write(f"• {b}")
            with col_b2:
                if st.button("Delete", key=f"del_brand_{i}"):
                    brands_data.pop(i)
                    save_json_file("data/brands.json", brands_data, sha, f"Deleted brand {b}")
                    st.rerun()

        st.divider()
        st.write("**Add New Brand**")
        new_brand = st.text_input("New Brand Name", placeholder="e.g. Kohler")
        if st.button("Add Brand", type="primary"):
            if not new_brand.strip():
                st.error("Enter brand name")
            elif new_brand.strip() in brands_data:
                st.error("Brand already exists")
            else:
                brands_data.append(new_brand.strip())
                save_json_file("data/brands.json", brands_data, sha, f"Added brand {new_brand}")
                st.success(f"Added brand {new_brand}")
                st.rerun()

    # 2. APPROVE CUSTOMERS
    with st.expander("👥 Approve Customer Logins", expanded=False):
        customers, sha = get_json_file("data/customers.json", [])
        if not customers:
            st.write("No customers yet")
        else:
            pending = [c for c in customers if not c.get("approved", False)]
            st.write(f"Pending: {len(pending)} | Total: {len(customers)}")
            for i, c in enumerate(customers):
                if not c.get("approved", False):
                    col_a, col_b, col_c = st.columns([3,1,1])
                    with col_a:
                        st.write(f"**{c['name']}** | {c['mail']} | {c['contact']} | {c['city']}")
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

    # 3. UPLOAD PRODUCTS
    with st.expander("📤 Upload Product PDFs (Permanent)", expanded=False):
        up_brand = st.selectbox("Select Brand for Product", brands_data, key="up_prod_brand")
        up_files = st.file_uploader("Choose Product PDFs", type=["pdf"], accept_multiple_files=True, key="up_prod")
        if st.button("Upload Products to GitHub", type="primary"):
            for f in up_files:
                try:
                    safe_name = f.name.replace(" ", "_")
                    path = f"pdfs/{up_brand}_{safe_name}"
                    content = f.read()
                    try:
                        existing = repo.get_contents(path)
                        repo.update_file(path, f"Update {safe_name}", content, existing.sha)
                    except:
                        repo.create_file(path, f"Add {safe_name}", content)
                    curr_approvals, curr_sha = get_json_file("data/approvals.json", [])
                    if not any(x["file"]==f"{up_brand}_{safe_name}" for x in curr_approvals):
                        curr_approvals.append({"brand":up_brand,"file":f"{up_brand}_{safe_name}","approved":False})
                        save_json_file("data/approvals.json", curr_approvals, curr_sha, f"Add approval {safe_name}")
                    st.success(f"Uploaded {safe_name}")
                except Exception as e:
                    st.error(f"{f.name} failed: {e}")

    # 4. UPLOAD PRICELISTS
    with st.expander("💰 Upload Pricelists - Customer Can Download", expanded=False):
        st.write("Upload brand pricelists. Name will be visible to all approved customers.")
        pl_brand = st.selectbox("Select Brand for Pricelist", brands_data, key="pl_brand")
        pl_files = st.file_uploader("Choose Pricelist PDFs (1 per brand recommended)", type=["pdf"], accept_multiple_files=True, key="pl_files")
        if st.button("Upload Pricelist", type="primary", key="up_pl_btn"):
            for f in pl_files:
                try:
                    safe_name = f.name.replace(" ", "_")
                    # Prefix PRICELIST_ to identify as pricelist
                    path = f"pdfs/PRICELIST_{pl_brand}_{safe_name}"
                    if not path.lower().endswith(".pdf"):
                        path += ".pdf"
                    content = f.read()
                    try:
                        existing = repo.get_contents(path)
                        repo.update_file(path, f"Update pricelist {pl_brand}", content, existing.sha)
                        st.success(f"Updated Pricelist {pl_brand}")
                    except:
                        repo.create_file(path, f"Add pricelist {pl_brand}", content)
                        st.success(f"Uploaded Pricelist {pl_brand} - {safe_name}")
                except Exception as e:
                    st.error(f"{f.name} failed: {e}")

        # List existing pricelists with delete
        try:
            contents = repo.get_contents("pdfs")
            existing_pl = [c for c in contents if c.name.upper().startswith("PRICELIST_")]
            if existing_pl:
                st.write(f"Existing Pricelists: {len(existing_pl)}")
                for pl in existing_pl:
                    col1, col2 = st.columns([3,1])
                    with col1:
                        st.write(f"• {pl.name}")
                    with col2:
                        if st.button("Delete", key=f"del_pl_{pl.name}"):
                            try:
                                repo.delete_file(pl.path, f"Delete pricelist {pl.name}", pl.sha)
                                st.success(f"Deleted {pl.name}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"{e}")
        except:
            pass

    with st.expander("✅ Approve Product PDF Files"):
        approvals_list, sha = get_json_file("data/approvals.json", [])
        for i, a in enumerate(approvals_list):
            col_a, col_b = st.columns([3,1])
            with col_a:
                st.write(f"{a['brand']} - {a['file']} - {'✅' if a.get('approved') else '⏳'}")
            with col_b:
                if not a.get("approved"):
                    if st.button("Approve", key=f"pdf_app_{i}"):
                        approvals_list[i]["approved"]=True
                        save_json_file("data/approvals.json", approvals_list, sha, f"Approved {a['file']}")
                        st.rerun()
