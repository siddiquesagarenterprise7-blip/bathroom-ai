import streamlit as st
import base64, json, io
import fitz
from github import Github

st.set_page_config(page_title="Bathroom AI - STOP at 3 MATCHES", layout="wide")

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
        file = repo.get_contents(path)
        content = base64.b64decode(file.content).decode('utf-8')
        return json.loads(content), file.sha
    except:
        return default, None

def save_json_file(path, data, sha, message):
    content = json.dumps(data, indent=2, ensure_ascii=False)
    if sha: repo.update_file(path, message, content, sha)
    else:
        try: repo.create_file(path, message, content)
        except:
            try:
                ex = repo.get_contents(path)
                repo.update_file(path, message, content, ex.sha)
            except: pass

def ensure_data_files():
    try: repo.get_contents("data")
    except:
        try: repo.create_file("data/.gitkeep", "init", "keep")
        except: pass
    brands, sha_b = get_json_file("data/brands.json", DEFAULT_BRANDS)
    if not brands: save_json_file("data/brands.json", DEFAULT_BRANDS, sha_b, "Restore brands")
    for p, d in [("data/customers.json", []), ("data/approvals.json", []), ("data/pdf_index.json", {}), ("data/file_types.json", {})]:
        data, sha = get_json_file(p, d)
        if sha is None: save_json_file(p, d, None, f"Init {p}")

ensure_data_files()

def get_or_create_release():
    try:
        for r in repo.get_releases():
            if r.tag_name == "pdfs-storage": return r
        return repo.create_git_release(tag="pdfs-storage", name="PDF Storage", message="150MB", draft=False, prerelease=False)
    except: return None

def get_all_pdfs_any_name():
    all_files = []
    try:
        contents = repo.get_contents("pdfs")
        for c in contents:
            if c.name.lower().endswith(".pdf"):
                all_files.append(c.name)
    except: pass
    try:
        release = get_or_create_release()
        if release:
            for asset in release.get_assets():
                if asset.name.lower().endswith(".pdf") and asset.name not in all_files:
                    all_files.append(asset.name)
    except: pass
    return all_files

def search_inside_pdf_stop_at_3(pdf_bytes, query, current_all_match_count):
    """
    Search inside PDF, but if we already have 3 ALL WORDS matches, stop.
    Returns: results, new_all_match_count, stopped_early
    """
    query_words = [w.lower() for w in query.strip().split() if w.strip()][:4]
    total_words = len(query_words)
    results = []
    stopped_early = False
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page_idx in range(len(doc)):
            # STOP if already found 3 ALL WORDS matching
            if current_all_match_count >= 3:
                stopped_early = True
                break

            page = doc.load_page(page_idx)
            text_lower = page.get_text("text").lower()
            matched = [q for q in query_words if q in text_lower]
            match_count = len(matched)
            if match_count > 0:
                # If this page is ALL WORDS match, increase counter
                if match_count == total_words:
                    current_all_match_count += 1
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                results.append((page_idx+1, match_count, matched, img_bytes))

                # If after adding this page we reached 3 ALL MATCHES, stop
                if current_all_match_count >= 3:
                    stopped_early = True
                    break
        doc.close()
    except: pass
    results.sort(key=lambda x: x[1], reverse=True)
    return results, current_all_match_count, stopped_early

# Login
if "customer_verified" not in st.session_state:
    st.session_state.customer_verified = False
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False
if "customer_email" not in st.session_state:
    st.session_state.customer_email = ""

if not st.session_state.customer_verified and not st.session_state.is_admin:
    st.title("🛁 Bathroom Pricelist Login")
    tab1, tab2 = st.tabs(["👤 Customer Login / Signup", "🔐 Admin Login"])
    with tab2:
        pwd = st.text_input("Admin Password", type="password")
        if st.button("Login as Admin", type="primary", use_container_width=True):
            if pwd == ADMIN_PASSWORD:
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
                    st.error("Mail ID not found. Please Signup below.")
                elif not found.get("approved", False):
                    st.warning("⏳ Pending approval from Admin.")
                else:
                    st.session_state.customer_verified = True
                    st.session_state.customer_email = login_mail
                    st.rerun()
        st.divider()
        with st.form("signup_form"):
            st.write("**New Customer Signup**")
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
                        st.error("Already registered.")
                    else:
                        customers.append({"name":name,"contact":contact,"mail":mail.strip(),"city":city,"pincode":pincode,"company":company,"approved": False})
                        save_json_file("data/customers.json", customers, sha, f"New customer {name}")
                        st.success("✅ Submitted for Admin Approval!")
    st.stop()

st.title("🛁 Pricelist Search - STOP at 3 MATCHES")
if st.session_state.is_admin:
    st.success("✅ Working Fine + Stop at 3 ALL MATCHES + Customer Approval Restored")
else:
    st.success(f"Welcome {st.session_state.customer_email}")

if st.button("Logout"):
    st.session_state.customer_verified = False
    st.session_state.is_admin = False
    st.rerun()

brands_data, _ = get_json_file("data/brands.json", DEFAULT_BRANDS)
brand_options = ["All Brands"] + brands_data
col1, col2 = st.columns([1,2])
with col1: brand_filter = st.selectbox("Brand", brand_options)
with col2: search_query = st.text_input("Search Pricelist", placeholder="e.g. Mint shower head")

search_btn = st.button("🔍 SEARCH - Stop at 3 ALL MATCHES", use_container_width=True, type="primary")

approvals_data, _ = get_json_file("data/approvals.json", [])
def is_approved_file(filename):
    if not approvals_data: return True
    for a in approvals_data:
        if a["file"]==filename and a.get("approved"): return True
    return False

if search_btn:
    if not search_query.strip():
        st.warning("Type word to search")
    else:
        all_files = get_all_pdfs_any_name()
        st.write(f"📄 Pricelist files: {all_files}")

        if not all_files:
            st.error("No Pricelist PDFs! Upload in Admin Panel")
        else:
            filtered = all_files
            if brand_filter!="All Brands":
                filtered_temp = [f for f in all_files if brand_filter.lower() in f.lower()]
                if filtered_temp: filtered = filtered_temp

            if not st.session_state.is_admin:
                filtered = [f for f in filtered if is_approved_file(f)]

            query_words = search_query.strip().split()
            total_q = len(query_words)
            st.info(f"Searching **{query_words}** — Will **STOP after 3 pages with ALL {total_q} words matching** → Super Fast!")

            final_results = []
            all_match_counter = 0
            progress = st.progress(0)
            status = st.empty()
            stopped = False

            for idx, filename in enumerate(filtered):
                if all_match_counter >= 3:
                    status.write(f"✅ STOPPED — Found 3 ALL WORDS matches — No need to search more!")
                    stopped = True
                    break

                status.write(f"🔍 Searching {idx+1}/{len(filtered)}: {filename} | Found ALL-MATCH so far: {all_match_counter}/3")
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
                                    r = requests.get(asset.browser_download_url, timeout=90)
                                    pdf_bytes = r.content
                                    break
                    if pdf_bytes:
                        pages, all_match_counter, early = search_inside_pdf_stop_at_3(pdf_bytes, search_query, all_match_counter)
                        for page_no, match_count, matched_words, img_bytes in pages:
                            final_results.append((filename, page_no, match_count, matched_words, img_bytes))
                        if early:
                            stopped = True
                            status.write(f"✅ STOPPED at {filename} Page {pages[-1][0] if pages else ''} — Reached 3 ALL MATCHES!")
                            break
                except Exception as e:
                    st.write(f"Error {filename}: {e}")
                progress.progress((idx+1)/len(filtered))

            progress.empty()
            status.empty()
            final_results.sort(key=lambda x: x[2], reverse=True)

            if not final_results:
                st.error(f"No match for '{search_query}'")
            else:
                if stopped:
                    st.success(f"✅ STOPPED EARLY — Found {all_match_counter} pages with ALL {total_q} words matching — Showing {len(final_results)} pages (Fast!)")
                else:
                    st.success(f"✅ Found {len(final_results)} pages — Sorted by Max Matching")

                files_dict = {}
                for filename, page_no, match_count, matched_words, img_bytes in final_results:
                    if filename not in files_dict: files_dict[filename]=[]
                    files_dict[filename].append((page_no, match_count, matched_words, img_bytes))

                for filename, pages in files_dict.items():
                    pages.sort(key=lambda x: x[1], reverse=True)
                    with st.container(border=True):
                        st.write(f"### 📄 {filename} — {len(pages)} pages")
                        for page_no, match_count, matched_words, img_bytes in pages[:15]:
                            if match_count == total_q: badge = f"🟢 ALL {match_count} WORDS"
                            elif match_count>=2: badge = f"🟡 {match_count} WORDS"
                            else: badge = f"🔵 {match_count} WORD"
                            st.write(f"**Page {page_no}** — {badge} — Matched: {', '.join(matched_words)}")
                            st.image(img_bytes, caption=f"Page {page_no} - {filename}", use_container_width=True)
                            st.divider()

st.divider()
st.header("💰 All Pricelists - Download")
all_files = get_all_pdfs_any_name()
if not all_files: st.info("No Pricelists yet")
else:
    for name in all_files:
        with st.container(border=True):
            c1,c2 = st.columns([3,1])
            with c1: st.write(f"**{name}**")
            with c2:
                try:
                    import requests
                    pdf_bytes = None
                    try:
                        fc = repo.get_contents(f"pdfs/{name}")
                        pdf_bytes = base64.b64decode(fc.content)
                    except:
                        release = get_or_create_release()
                        if release:
                            for asset in release.get_assets():
                                if asset.name == name:
                                    r = requests.get(asset.browser_download_url, timeout=60)
                                    pdf_bytes = r.content
                                    break
                    if pdf_bytes:
                        st.download_button("📥 Download", data=pdf_bytes, file_name=name, mime="application/pdf", key=f"dl_{name}", use_container_width=True)
                except: pass

if st.session_state.is_admin:
    st.divider()
    st.header("👑 Admin - ONLY PRICELISTS - ANY NAME")

    with st.expander("📊 Status", expanded=False):
        all_files = get_all_pdfs_any_name()
        st.write(f"**Pricelist PDFs:** {all_files}")
        st.write(f"**Count:** {len(all_files)}")
        customers_data, _ = get_json_file("data/customers.json", [])
        st.write(f"**Customers:** {len(customers_data)}")
        st.write(f"**Pending Approvals:** {len([c for c in customers_data if not c.get('approved')])}")

    # RESTORED CUSTOMER APPROVAL - THIS WAS MISSING
    with st.expander("👥 Customer Approvals - RESTORED ✅", expanded=True):
        customers_data, sha_c = get_json_file("data/customers.json", [])
        st.write(f"Total Customers: {len(customers_data)}")
        if not customers_data:
            st.info("No customers yet")
        else:
            for i, c in enumerate(customers_data):
                status_txt = "✅ Approved" if c.get("approved") else "⏳ Pending"
                with st.container(border=True):
                    col1, col2, col3 = st.columns([3,1,1])
                    with col1:
                        st.write(f"**{c.get('name')}** | {c.get('mail')} | {c.get('contact')} | {c.get('city')} | {status_txt}")
                        if c.get("company"): st.write(f"Company: {c.get('company')}")
                    with col2:
                        if not c.get("approved"):
                            if st.button("✅ Approve", key=f"app_cust_{i}", type="primary"):
                                customers_data[i]["approved"] = True
                                save_json_file("data/customers.json", customers_data, sha_c, f"Approve customer {c.get('mail')}")
                                st.success(f"Approved {c.get('mail')}")
                                st.rerun()
                    with col3:
                        if st.button("❌ Delete", key=f"del_cust_{i}"):
                            customers_data.pop(i)
                            save_json_file("data/customers.json", customers_data, sha_c, f"Delete customer {c.get('mail')}")
                            st.rerun()

    with st.expander("🏷️ Manage Brands", expanded=False):
        brands_data_list, sha_b = get_json_file("data/brands.json", DEFAULT_BRANDS)
        st.write(f"Current Brands: {brands_data_list}")
        new_brand = st.text_input("Add New Brand")
        if st.button("Add Brand"):
            if new_brand.strip() and new_brand.strip() not in brands_data_list:
                brands_data_list.append(new_brand.strip())
                save_json_file("data/brands.json", brands_data_list, sha_b, f"Add brand {new_brand}")
                st.rerun()
        for i, b in enumerate(brands_data_list):
            col1, col2 = st.columns([4,1])
            with col1: st.write(f"• {b}")
            with col2:
                if st.button("Delete", key=f"del_b_{i}"):
                    brands_data_list.pop(i)
                    save_json_file("data/brands.json", brands_data_list, sha_b, f"Delete {b}")
                    st.rerun()

    with st.expander("📤 Upload Pricelists - ANY NAME - SEARCHABLE", expanded=False):
        st.info("✅ ANY NAME allowed - Will be searchable!")
        up_brand = st.selectbox("Select Brand", brands_data, key="up_brand_final")
        up_files = st.file_uploader("Choose PRICELIST PDFs - ANY NAME", type=["pdf"], accept_multiple_files=True, key="up_final")
        if st.button("⬆️ Upload Pricelist - ANY NAME", type="primary"):
            for f in up_files:
                try:
                    safe_name = f.name.replace(" ", "_")
                    file_bytes = f.getvalue()
                    size_mb = len(file_bytes)/(1024*1024)
                    fname = safe_name
                    st.write(f"Uploading {fname} - {size_mb:.1f}MB...")

                    if size_mb > 90:
                        release = get_or_create_release()
                        for asset in release.get_assets():
                            if asset.name == fname: asset.delete_asset()
                        release.upload_asset_from_memory(io.BytesIO(file_bytes), len(file_bytes), fname, "application/pdf")
                    else:
                        path = f"pdfs/{fname}"
                        try:
                            ex = repo.get_contents(path)
                            repo.update_file(path, f"Update {fname}", file_bytes, ex.sha)
                        except:
                            repo.create_file(path, f"Add {fname}", file_bytes)
                    st.success(f"✅ Uploaded {fname} - SEARCHABLE!")

                    approvals_data, appr_sha = get_json_file("data/approvals.json", [])
                    if not any(x["file"]==fname for x in approvals_data):
                        approvals_data.append({"brand":up_brand,"file":fname,"approved":True})
                        save_json_file("data/approvals.json", approvals_data, appr_sha, f"Add {fname}")
                except Exception as e:
                    st.error(f"Failed {f.name}: {e}")

    with st.expander("✅ Approve Pricelist Files"):
        approvals_list, sha = get_json_file("data/approvals.json", [])
        for i, a in enumerate(approvals_list):
            col_a, col_b = st.columns([4,1])
            with col_a: st.write(f"{a['brand']} - {a['file']} - {'✅' if a.get('approved') else '⏳'}")
            with col_b:
                if not a.get("approved"):
                    if st.button("Approve", key=f"appr_{i}"):
                        approvals_list[i]["approved"]=True
                        save_json_file("data/approvals.json", approvals_list, sha, f"Approve {a['file']}")
                        st.rerun()
