import streamlit as st
import base64, json
import fitz # PyMuPDF
from github import Github

st.set_page_config(page_title="Bathroom AI - Final 8 Features", layout="wide", initial_sidebar_state="expanded")

# ========== 1. SECRETS ==========
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    GITHUB_REPO_NAME = st.secrets["GITHUB_REPO"]
    ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "Bathroom@123")
except Exception as e:
    st.error(f"Secrets Missing: {e}. Add GITHUB_TOKEN, GITHUB_REPO, ADMIN_PASSWORD in Streamlit Secrets")
    st.stop()

@st.cache_resource
def get_github_repo():
    g = Github(GITHUB_TOKEN)
    return g.get_repo(GITHUB_REPO_NAME)

try:
    repo = get_github_repo()
except Exception as e:
    st.error(f"GitHub Connection Failed: {e}. Check GITHUB_REPO = 'siddiquesagarenterprise7-blip/bathroom-ai'")
    st.stop()

# ========== 2. GITHUB JSON STORAGE (Replaces Google Sheets) ==========
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
            # if created in between, try update
            try:
                existing = repo.get_contents(path)
                repo.update_file(path, message, content, existing.sha)
            except Exception as e:
                st.error(f"Save failed {path}: {e}")

# ========== 3. CUSTOMER SIGNUP (Feature #1) ==========
if "customer_verified" not in st.session_state:
    st.session_state.customer_verified = False
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False

if not st.session_state.customer_verified and not st.session_state.is_admin:
    st.title("🛁 Customer Signup Required")
    st.write("Please signup once to access product search — Data saved permanently to GitHub")
    with st.form("signup_form"):
        name = st.text_input("Name*")
        contact = st.text_input("Contact No*")
        mail = st.text_input("Mail ID*")
        city = st.text_input("City*")
        pincode = st.text_input("Pincode*")
        company = st.text_input("Company Name (Optional)")
        submit = st.form_submit_button("Submit & Continue", use_container_width=True)
        if submit:
            if not all([name.strip(), contact.strip(), mail.strip(), city.strip(), pincode.strip()]):
                st.error("Please fill all * mandatory fields")
            else:
                with st.spinner("Saving to GitHub..."):
                    customers, sha = get_json_file("data/customers.json", [])
                    customers.append({
                        "name": name, "contact": contact, "mail": mail,
                        "city": city, "pincode": pincode, "company": company
                    })
                    save_json_file("data/customers.json", customers, sha, f"New customer: {name}")
                    st.session_state.customer_verified = True
                st.success("Signup saved! Loading app...")
                st.rerun()
    st.stop()

# ========== 4. SIDEBAR - ADMIN LOGIN (Feature #B) ==========
with st.sidebar:
    st.header("🔐 Admin Login")
    if not st.session_state.is_admin:
        pwd = st.text_input("Admin Password", type="password", key="admin_pwd")
        if st.button("Login as Admin", use_container_width=True):
            if pwd == ADMIN_PASSWORD:
                st.session_state.is_admin = True
                st.session_state.customer_verified = True
                st.success("Admin Login Success!")
                st.rerun()
            else:
                st.error("Wrong Password")
        st.divider()
        st.info("Customer view: Search + Brand filter + Pagination + Download Original")
    else:
        st.success("✅ Logged in as Admin")
        if st.button("Logout Admin", use_container_width=True):
            st.session_state.is_admin = False
            st.session_state.customer_verified = False
            st.rerun()
        st.divider()
        st.write(f"Repo: `{GITHUB_REPO_NAME}`")

# ========== 5. MAIN APP (Features #2,3,4,5,6,7,8) ==========
st.title("🛁 Bathroom Product Search")
st.caption("8 Features: Signup | Search | Brand Filter | Original Image | Pagination 20 | Download | GitHub Permanent | Approval")

col1, col2 = st.columns([1, 2])
with col1:
    brand_filter = st.selectbox("Brand", ["All Brands", "Fantini", "Gessi", "Hansgrohe", "Others"])
with col2:
    search_query = st.text_input("Search", placeholder="e.g. 200mm Round shower, Fantini, Wall mixer")

col_s1, col_s2 = st.columns([1, 1])
with col_s1:
    search_btn = st.button("🔍 Search", use_container_width=True)
with col_s2:
    if st.button("Clear", use_container_width=True):
        st.session_state.page_num = 0
        st.rerun()

uploaded_image = st.file_uploader("Image Search (Optional - Visual search placeholder)", type=["jpg", "jpeg", "png"])

# Pagination state
if "page_num" not in st.session_state:
    st.session_state.page_num = 0

# Get approvals
approvals_data, approvals_sha = get_json_file("data/approvals.json", [])

def is_approved(filename):
    if not approvals_data:
        return False
    for a in approvals_data:
        if a["file"] == filename:
            return a.get("approved", False)
    return False

# ========== SEARCH LOGIC ==========
if search_btn or search_query or brand_filter!= "All Brands" or st.session_state.page_num > 0:
    try:
        with st.spinner("Searching GitHub pdfs/..."):
            try:
                contents = repo.get_contents("pdfs")
                all_files = [c.name for c in contents if c.name.lower().endswith(".pdf")]
            except:
                all_files = []
                st.warning("No `pdfs/` folder found in GitHub. Create folder `pdfs/.gitkeep` in GitHub first, then upload via Admin panel.")

            # Apply Brand Filter
            filtered = all_files
            if brand_filter!= "All Brands":
                filtered = [f for f in filtered if f.lower().startswith(brand_filter.lower()) or brand_filter.lower() in f.lower()]

            # Apply Text Search
            if search_query:
                q = search_query.lower()
                filtered = [f for f in filtered if q in f.lower()]

            # Apply Approval Filter - Customer sees only approved
            if not st.session_state.is_admin:
                filtered = [f for f in filtered if is_approved(f)]
            # Admin sees all but shows status

            total = len(filtered)
            st.write(f"**Found {total} results** {'(Approved only)' if not st.session_state.is_admin else '(Admin sees all)'}")

            if total == 0:
                st.info("No results. Upload PDFs via Admin panel and approve them.")
            else:
                # Pagination 20 per page
                per_page = 20
                total_pages = (total + per_page - 1) // per_page
                start = st.session_state.page_num * per_page
                end = min(start + per_page, total)

                st.write(f"Showing {start+1}-{end} of {total} | Page {st.session_state.page_num+1}/{total_pages}")

                c_prev, c_next = st.columns(2)
                with c_prev:
                    if st.button("⬅️ Previous", disabled=st.session_state.page_num==0):
                        st.session_state.page_num -= 1
                        st.rerun()
                with c_next:
                    if st.button("Next ➡️", disabled=st.session_state.page_num >= total_pages-1):
                        st.session_state.page_num += 1
                        st.rerun()

                for filename in filtered[start:end]:
                    with st.container(border=True):
                        col_img, col_info = st.columns([2, 1])
                        approved_badge = "✅ Approved" if is_approved(filename) else "⏳ Pending Approval"
                        with col_info:
                            st.markdown(f"**{filename}**")
                            st.caption(approved_badge)
                            if not is_approved(filename) and st.session_state.is_admin:
                                st.warning("Pending - Approve below")

                        with col_img:
                            try:
                                file_content = repo.get_contents(f"pdfs/{filename}")
                                pdf_bytes = base64.b64decode(file_content.content)
                                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                                page = doc.load_page(0)
                                pix = page.get_pixmap(dpi=180)
                                img_bytes = pix.tobytes("png")
                                st.image(img_bytes, caption=f"Original - {filename} Page 1", use_container_width=True)
                                st.download_button(
                                    f"📥 Download Original {filename} Page 1",
                                    data=img_bytes,
                                    file_name=f"{filename}_page1.png",
                                    mime="image/png",
                                    key=f"dl_{filename}_{start}",
                                    use_container_width=True
                                )
                            except Exception as e:
                                st.error(f"Preview failed: {e}")

                # Bottom pagination
                if total > per_page:
                    st.divider()
                    c_prev2, c_next2 = st.columns(2)
                    with c_prev2:
                        if st.button("⬅️ Previous Page", key="prev2", disabled=st.session_state.page_num==0):
                            st.session_state.page_num -= 1
                            st.rerun()
                    with c_next2:
                        if st.button("Next Page ➡️", key="next2", disabled=st.session_state.page_num >= total_pages-1):
                            st.session_state.page_num += 1
                            st.rerun()

    except Exception as e:
        st.error(f"Search Error: {e}")

# ========== 6. ADMIN PANEL ==========
if st.session_state.is_admin:
    st.divider()
    st.header("👑 Admin Panel - Permanent GitHub Storage")

    with st.expander("📤 Upload PDFs to GitHub (Permanent) - Feature #7", expanded=True):
        up_brand = st.selectbox("Select Brand for Upload", ["Fantini", "Gessi", "Hansgrohe", "Others"], key="up_brand_final")
        up_files = st.file_uploader("Choose PDFs", type=["pdf"], accept_multiple_files=True, key="up_files_final")
        if st.button("Upload to GitHub - Permanent", type="primary", use_container_width=True):
            if not up_files:
                st.warning("Select PDFs first")
            else:
                for f in up_files:
                    try:
                        content = f.read()
                        # Sanitize name
                        safe_name = f.name.replace(" ", "_")
                        path = f"pdfs/{up_brand}_{safe_name}"
                        # Check if exists
                        try:
                            existing = repo.get_contents(path)
                            repo.update_file(path, f"Update {safe_name}", content, existing.sha)
                            st.success(f"Updated {safe_name}")
                        except:
                            repo.create_file(path, f"Add {safe_name}", content)
                            st.success(f"Uploaded {safe_name} to {path}")

                        # Add to approvals as not approved
                        curr_approvals, curr_sha = get_json_file("data/approvals.json", [])
                        # Avoid duplicate
                        if not any(x["file"] == f"{up_brand}_{safe_name}" for x in curr_approvals):
                            curr_approvals.append({"brand": up_brand, "file": f"{up_brand}_{safe_name}", "approved": False})
                            save_json_file("data/approvals.json", curr_approvals, curr_sha, f"Add approval for {safe_name}")
                        else:
                            st.info(f"{safe_name} already in approvals list")
                    except Exception as e:
                        st.error(f"{f.name} failed: {e}")

    with st.expander("✅ Approve Files - Feature #B (Google Sheet Approval Alternative)", expanded=True):
        approvals_list, sha = get_json_file("data/approvals.json", [])
        if not approvals_list:
            st.write("No files in approval list. Upload PDFs first.")
        else:
            for i, a in enumerate(approvals_list):
                col_a, col_b, col_c = st.columns([2, 1, 1])
                with col_a:
                    status = "✅ Approved" if a.get("approved") else "⏳ Pending"
                    st.write(f"**{a.get('brand')}** - `{a.get('file')}` - {status}")
                with col_b:
                    if not a.get("approved"):
                        if st.button("Approve", key=f"approve_btn_{i}"):
                            approvals_list[i]["approved"] = True
                            save_json_file("data/approvals.json", approvals_list, sha, f"Approved {a.get('file')}")
                            st.success(f"Approved {a.get('file')}")
                            st.rerun()
                with col_c:
                    if st.button("Delete", key=f"del_btn_{i}"):
                        approvals_list.pop(i)
                        save_json_file("data/approvals.json", approvals_list, sha, f"Removed {a.get('file')}")
                        st.rerun()

    with st.expander("👥 View Customers - Saved in data/customers.json"):
        customers, _ = get_json_file("data/customers.json", [])
        if customers:
            st.json(customers[-10:]) # last 10
            st.write(f"Total customers: {len(customers)}")
        else:
            st.write("No customers yet")

else:
    st.info("💡 Admin panel hidden. Login via left sidebar to upload & approve PDFs.")

# Footer
st.divider()
st.caption(f"Repo: {GITHUB_REPO_NAME} | Permanent Storage via GitHub | No Google JSON needed | Admin Password in Secrets")
