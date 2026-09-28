import streamlit as st
import base64, json, io
import fitz
from github import Github

st.set_page_config(page_title="Bathroom AI - Max Matching", layout="wide")

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
            except:
                pass

def get_or_create_release():
    try:
        for r in repo.get_releases():
            if r.tag_name == "pdfs-storage":
                return r
        return repo.create_git_release(tag="pdfs-storage", name="PDF Storage", message="150MB", draft=False, prerelease=False)
    except:
        return None

def get_all_pdf_files():
    all_files = []
    try:
        contents = repo.get_contents("pdfs")
        for c in contents:
            if c.name.lower().endswith(".pdf") and not c.name.upper().startswith("PRICELIST_"):
                all_files.append(c.name)
    except: pass
    try:
        release = get_or_create_release()
        if release:
            for asset in release.get_assets():
                if asset.name.lower().endswith(".pdf") and not asset.name.upper().startswith("PRICELIST_"):
                    if asset.name not in all_files:
                        all_files.append(asset.name)
    except: pass
    return all_files

def get_all_pricelists():
    pricelists = []
    try:
        contents = repo.get_contents("pdfs")
        for c in contents:
            if c.name.upper().startswith("PRICELIST_") and c.name.lower().endswith(".pdf"):
                pricelists.append((c.name, "folder", None))
    except: pass
    try:
        release = get_or_create_release()
        if release:
            for asset in release.get_assets():
                if asset.name.upper().startswith("PRICELIST_") and asset.name.lower().endswith(".pdf"):
                    pricelists.append((asset.name, "release", asset))
    except: pass
    return pricelists

# MAXIMUM MATCHING: All 3 words > 2 words > 1 word
def search_max_matching(pdf_bytes, query):
    query_words = [w.lower() for w in query.strip().split() if w.strip()]
    if not query_words:
        return []
    # Only take first 3-4 words for matching to avoid too many
    query_words = query_words[:4]
    results = [] # [(page_no, match_count, matched_words, image_bytes)]
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page_idx in range(len(doc)):
            page = doc.load_page(page_idx)
            text_lower = page.get_text("text").lower()
            matched = []
            for q in query_words:
                if q in text_lower:
                    matched.append(q)
            match_count = len(matched)
            if match_count > 0:
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")
                results.append((page_idx + 1, match_count, matched, img_bytes))
        doc.close()
    except:
        pass
    # Sort by maximum matching first: 3 > 2 > 1
    results.sort(key=lambda x: x[1], reverse=True)
    return results

if "customer_verified" not in st.session_state:
    st.session_state.customer_verified = False
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False
if "customer_email" not in st.session_state:
    st.session_state.customer_email = ""

DEFAULT_BRANDS = ["Fantini", "Gessi", "Hansgrohe", "Jaquar", "Grohe"]

if not st.session_state.customer_verified and not st.session_state.is_admin:
    st.title("🛁 Bathroom Product Login")
    tab1, tab2 = st.tabs(["👤 Customer", "🔐 Admin"])
    with tab2:
        pwd = st.text_input("Admin Password", type="password")
        if st.button("Login as Admin", type="primary", use_container_width=True):
            if pwd == ADMIN_PASSWORD:
                st.session_state.is_admin = True
                st.session_state.customer_verified = True
                st.rerun()
            else:
                st.error("Wrong")
    with tab1:
        with st.container(border=True):
            login_mail = st.text_input("Enter Mail ID")
            if st.button("Login"):
                customers, _ = get_json_file("data/customers.json", [])
                found = next((c for c in customers if c.get("mail","").lower() == login_mail.lower().strip()), None)
                if not found:
                    st.error("Not found")
                elif not found.get("approved", False):
                    st.warning("Pending approval")
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
            company = st.text_input("Company (Optional)")
            submit = st.form_submit_button("Submit", use_container_width=True)
            if submit:
                customers, sha = get_json_file("data/customers.json", [])
                customers.append({"name":name,"contact":contact,"mail":mail.strip(),"city":city,"pincode":pincode,"company":company,"approved": False})
                save_json_file("data/customers.json", customers, sha, f"New {name}")
                st.success("Submitted!")
    st.stop()

st.title("🛁 Bathroom Product Search")
if st.session_state.is_admin:
    st.success("✅ Admin Mode - Maximum Matching: All3 > All2 > All1")
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
with col2: search_query = st.text_input("Search Products", placeholder="e.g. Mint shower head round")

search_btn = st.button("🔍 Search - Max Matching (All3>All2>All1)", use_container_width=True, type="primary")

approvals_data, _ = get_json_file("data/approvals.json", [])
def is_approved(filename):
    for a in approvals_data:
        if a["file"]==filename and a.get("approved"): return True
    return False

if search_btn or search_query.strip() or brand_filter!="All Brands":
    all_files = get_all_pdf_files()
    filtered_by_brand = all_files
    if brand_filter!="All Brands":
        filtered_by_brand = [f for f in filtered_by_brand if brand_filter.lower() in f.lower()]
    if not st.session_state.is_admin:
        filtered_by_brand = [f for f in filtered_by_brand if is_approved(f)]

    if not search_query.strip():
        st.write(f"Found {len(filtered_by_brand)} products")
    else:
        query_words = search_query.strip().split()
        st.info(f"Searching for **{query_words}** — Will show **{len(query_words)} words matched first, then {len(query_words)-1}, then 1**")

        all_matched = [] # [(filename, pdf_bytes, pages)]
        progress = st.progress(0)
        status = st.empty()

        for idx, filename in enumerate(filtered_by_brand):
            status.write(f"Checking {idx+1}/{len(filtered_by_brand)}: {filename}")
            try:
                pdf_bytes = None
                try:
                    fc = repo.get_contents(f"pdfs/{filename}")
                    pdf_bytes = base64.b64decode(fc.content)
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
                    pages = search_max_matching(pdf_bytes, search_query)
                    if pages:
                        all_matched.append((filename, pdf_bytes, pages))
            except:
                pass
            progress.progress((idx+1)/len(filtered_by_brand) if filtered_by_brand else 1)

        progress.empty()
        status.empty()

        if not all_matched:
            st.warning(f"No match for {query_words}")
        else:
            # Sort files by max matching count
            all_matched.sort(key=lambda x: max(p[1] for p in x[2]), reverse=True)
            st.success(f"Found in {len(all_matched)} file(s) - Sorted by Max Matching")

            for filename, pdf_bytes, pages in all_matched:
                with st.container(border=True):
                    best_match = pages[0][1] if pages else 0
                    st.write(f"### 📄 {filename} — Best Match: {best_match}/{len(query_words)} words")
                    # Group by match count
                    for page_no, match_count, matched_words, img_bytes in pages:
                        if match_count == len(query_words):
                            badge = "🟢 ALL WORDS MATCH"
                        elif match_count == len(query_words)-1:
                            badge = "🟡 2 WORDS MATCH"
                        else:
                            badge = f"🔵 {match_count} WORD MATCH"
                        st.write(f"**Page {page_no}** — {badge} — Matched: {', '.join(matched_words)}")
                        st.image(img_bytes, caption=f"Page {page_no} - {match_count} words matched", use_container_width=True)
                        st.divider()
                    st.download_button(f"📥 Download {filename}", data=pdf_bytes, file_name=filename, mime="application/pdf", key=f"dl_{filename}")

st.divider()
st.header("💰 Pricelists")
pricelists = get_all_pricelists()
if not pricelists:
    st.info("No pricelists yet.")
else:
    for item in pricelists:
        name = item[0]
        with st.container(border=True):
            c1,c2 = st.columns([3,1])
            with c1: st.write(f"**{name.replace('PRICELIST_','').replace('.pdf','')} Pricelist**")
            with c2:
                try:
                    import requests
                    pdf_bytes = None
                    if item[1]=="folder":
                        fc = repo.get_contents(f"pdfs/{name}")
                        pdf_bytes = base64.b64decode(fc.content)
                    else:
                        r = requests.get(item[2].browser_download_url)
                        pdf_bytes = r.content
                    if pdf_bytes:
                        st.download_button("📥 Download", data=pdf_bytes, file_name=name, mime="application/pdf", key=f"pl_{name}", use_container_width=True)
                except:
                    pass

if st.session_state.is_admin:
    st.divider()
    st.header("👑 Admin Panel")
    with st.expander("📤 Upload Product PDFs - 150MB SINGLE FILE", expanded=False):
        up_brand = st.selectbox("Select Brand", brands_data, key="up_prod_brand")
        up_files = st.file_uploader("Choose PDFs", type=["pdf"], accept_multiple_files=True, key="up_prod")
        if st.button("Upload 150MB Single", type="primary"):
            for f in up_files:
                try:
                    safe_name = f.name.replace(" ", "_")
                    file_bytes = f.getvalue()
                    if len(file_bytes)/(1024*1024) > 90:
                        release = get_or_create_release()
                        for asset in release.get_assets():
                            if asset.name == f"{up_brand}_{safe_name}":
                                asset.delete_asset()
                        release.upload_asset_from_memory(io.BytesIO(file_bytes), len(file_bytes), f"{up_brand}_{safe_name}", "application/pdf")
                        st.success(f"✅ Uploaded SINGLE FILE to Releases!")
                    else:
                        path = f"pdfs/{up_brand}_{safe_name}"
                        try:
                            ex = repo.get_contents(path)
                            repo.update_file(path, f"Update {safe_name}", file_bytes, ex.sha)
                        except:
                            repo.create_file(path, f"Add {safe_name}", file_bytes)
                        st.success(f"✅ Uploaded!")
                    curr_approvals, curr_sha = get_json_file("data/approvals.json", [])
                    fname = f"{up_brand}_{safe_name}"
                    if not any(x["file"]==fname for x in curr_approvals):
                        curr_approvals.append({"brand":up_brand,"file":fname,"approved":False})
                        save_json_file("data/approvals.json", curr_approvals, curr_sha, f"Add {fname}")
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
