import streamlit as st
import base64, json
import fitz
from github import Github

st.set_page_config(page_title="Bathroom AI - Final 8", layout="wide")

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
    content = json.dumps(data, indent=2)
    if sha:
        repo.update_file(path, message, content, sha)
    else:
        try:
            repo.create_file(path, message, content)
        except:
            try:
                existing = repo.get_contents(path)
                repo.update_file(path, message, content, existing.sha)
            except:
                st.error(f"Save failed {path}")

if "customer_verified" not in st.session_state:
    st.session_state.customer_verified = False
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False
if "customer_email" not in st.session_state:
    st.session_state.customer_email = ""

# ====== CUSTOMER + ADMIN LOGIN ON SAME PAGE ======
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
        st.write("New customer? Signup below. Existing? Enter your Mail ID to login")

        # EXISTING CUSTOMER LOGIN
        with st.container(border=True):
            st.write("**Already Signed Up? Login**")
            login_mail = st.text_input("Enter your Mail ID to Login")
            if st.button("Login"):
                customers, _ = get_json_file("data/customers.json", [])
                found = None
                for c in customers:
                    if c.get("mail","").lower() == login_mail.lower().strip():
                        found = c
                        break
                if not found:
                    st.error("Mail ID not found. Please Signup below.")
                elif not found.get("approved", False):
                    st.warning("⏳ Your account is pending Admin approval. Contact Admin.")
                else:
                    st.session_state.customer_verified = True
                    st.session_state.customer_email = login_mail
                    st.session_state.is_admin = False
                    st.success("Login Success!")
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
                    # check duplicate
                    if any(c.get("mail","").lower() == mail.lower().strip() for c in customers):
                        st.error("This Mail ID already registered. Use Login above.")
                    else:
                        customers.append({
                            "name":name,"contact":contact,"mail":mail.strip(),
                            "city":city,"pincode":pincode,"company":company,
                            "approved": False # NEEDS ADMIN APPROVAL
                        })
                        save_json_file("data/customers.json", customers, sha, f"New customer {name} pending approval")
                        st.success("✅ Signup submitted! Wait for Admin approval. You will be able to login after Admin approves.")
    st.stop()

# ====== CHECK IF CUSTOMER IS STILL APPROVED (Admin can revoke) ======
if not st.session_state.is_admin:
    customers, _ = get_json_file("data/customers.json", [])
    current = None
    for c in customers:
        if c.get("mail","").lower() == st.session_state.customer_email.lower():
            current = c
            break
    if current and not current.get("approved", False):
        st.warning("Your access revoked / pending approval. Contact Admin.")
        if st.button("Logout"):
            st.session_state.customer_verified = False
            st.session_state.customer_email = ""
            st.rerun()
        st.stop()

# ====== MAIN APP ======
st.title("🛁 Bathroom Product Search")
if st.session_state.is_admin:
    st.success("✅ Admin Mode - You can approve customers & PDFs")
else:
    st.success(f"Welcome {st.session_state.customer_email}")

if st.button("Logout"):
    st.session_state.customer_verified = False
    st.session_state.is_admin = False
    st.session_state.customer_email = ""
    st.rerun()

col1, col2 = st.columns([1,2])
with col1:
    brand_filter = st.selectbox("Brand", ["All Brands", "Fantini", "Gessi", "Hansgrohe", "Others"])
with col2:
    search_query = st.text_input("Search", placeholder="200mm Round shower")

search_btn = st.button("🔍 Search", use_container_width=True)
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
        all_files = [c.name for c in contents if c.name.lower().endswith(".pdf")]
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
    st.write(f"Found {len(filtered)} results")
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

# ====== ADMIN PANEL - APPROVE CUSTOMERS + PDFS ======
if st.session_state.is_admin:
    st.divider()
    st.header("👑 Admin Panel")

    with st.expander("👥 Approve Customer Logins - NEW", expanded=True):
        customers, sha = get_json_file("data/customers.json", [])
        if not customers:
            st.write("No customers yet")
        else:
            pending = [c for c in customers if not c.get("approved", False)]
            approved = [c for c in customers if c.get("approved", False)]
            st.write(f"Pending: {len(pending)} | Approved: {len(approved)}")

            if pending:
                st.subheader("⏳ Pending Approval")
                for i, c in enumerate(customers):
                    if not c.get("approved", False):
                        col_a, col_b, col_c = st.columns([3,1,1])
                        with col_a:
                            st.write(f"**{c['name']}** | {c['mail']} | {c['contact']} | {c['city']}")
                        with col_b:
                            if st.button("✅ Approve", key=f"cust_app_{i}"):
                                customers[i]["approved"] = True
                                save_json_file("data/customers.json", customers, sha, f"Approved customer {c['mail']}")
                                st.success(f"Approved {c['mail']}")
                                st.rerun()
                        with col_c:
                            if st.button("❌ Delete", key=f"cust_del_{i}"):
                                customers.pop(i)
                                save_json_file("data/customers.json", customers, sha, f"Deleted customer {c['mail']}")
                                st.rerun()
            if approved:
                st.subheader("✅ Approved Customers")
                for c in approved:
                    st.write(f"{c['name']} - {c['mail']} - {c['city']} - Approved")

    with st.expander("📤 Upload PDFs", expanded=False):
        up_brand = st.selectbox("Brand", ["Fantini","Gessi","Hansgrohe","Others"])
        up_files = st.file_uploader("PDFs", type=["pdf"], accept_multiple_files=True)
        if st.button("Upload to GitHub", type="primary"):
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

    with st.expander("✅ Approve PDF Files"):
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
