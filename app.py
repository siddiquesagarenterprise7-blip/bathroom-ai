import streamlit as st
import base64, json, io
import fitz
from github import Github

st.set_page_config(page_title="Bathroom AI - ONLY 3 PAGES", layout="wide")

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
    for p, d in [("data/customers.json", []), ("data/approvals.json", []), ("data/file_types.json", {})]:
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

# FIXED: Search and STOP at 3 ALL MATCHES, return ONLY 3 pages
def search_stop_at_3_all_match(pdf_bytes, query):
    query_words = [w.lower() for w in query.strip().split() if w.strip()][:4]
    total_q = len(query_words)
    all_match_pages = [] # Only pages with ALL words
    scanned_pages = 0

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page_idx in range(len(doc)):
            scanned_pages += 1
            # STOP if we already have 3 ALL MATCHES
            if len(all_match_pages) >= 3:
                break

            page = doc.load_page(page_idx)
            text_lower = page.get_text("text").lower()
            matched = [q for q in query_words if q in text_lower]

            if len(matched) == total_q and total_q>0:
                # FIXED IMAGE - Lower DPI + Proper render
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) # 144 DPI - Fast + Visible
                img_bytes = pix.tobytes("png")
                all_match_pages.append((page_idx+1, len(matched), matched, img_bytes))
        doc.close()
    except Exception as e:
        st.write(f"Search error: {e}")

    return all_match_pages, scanned_pages

# Fallback: If no 3 ALL MATCH found, search for max matching (2 words, 1 word)
def search_max_matching_fallback(pdf_bytes, query):
    query_words = [w.lower() for w in query.strip().split() if w.strip()][:4]
    results = []
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page_idx in range(len(doc)):
            page = doc.load_page(page_idx)
            text_lower = page.get_text("text").lower()
            matched = [q for q in query_words if q in text_lower]
            if matched:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img_bytes = pix.tobytes("png")
                results.append((page_idx+1, len(matched), matched, img_bytes))
        doc.close()
    except: pass
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:10] # Show max 10 if no 3 ALL found

# Login
if "customer_verified" not in st.session_state:
    st.session_state.customer_verified = False
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False
if "customer_email" not in st.session_state:
    st.session_state.customer_email = ""

if not st.session_state.customer_verified and not st.session_state.is_admin:
    st.title("🛁 Bathroom Pricelist Login")
    tab1, tab2 = st.tabs(["👤 Customer", "🔐 Admin"])
    with tab2:
        pwd = st.text_input("Admin Password", type="password")
        if st.button("Login as Admin", type="primary", use_container_width=True):
            if pwd == ADMIN_PASSWORD:
                st.session_state.is_admin = True
                st.session_state.customer_verified = True
                st.rerun()
    with tab1:
        with st.container(border=True):
            login_mail = st.text_input("Enter Mail ID")
            if st.button("Login"):
                customers, _ = get_json_file("data/customers.json", [])
                found = next((c for c in customers if c.get("mail","").lower() == login_mail.lower().strip()), None)
                if found and found.get("approved"):
                    st.session_state.customer_verified = True
                    st.session_state.customer_email = login_mail
                    st.rerun()
                else: st.error("Not found or pending")
        with st.form("signup_form"):
            st.write("**New Customer Signup**")
            name = st.text_input("Name*")
            contact = st.text_input("Contact No*")
            mail = st.text_input("Mail ID*")
            city = st.text_input("City*")
            pincode = st.text_input("Pincode*")
            company = st.text_input("Company (Optional)")
            if st.form_submit_button("Submit for Approval", use_container_width=True):
                customers, sha = get_json_file("data/customers.json", [])
                customers.append({"name":name,"contact":contact,"mail":mail.strip(),"city":city,"pincode":pincode,"company":company,"approved": False})
                save_json_file("data/customers.json", customers, sha, f"New {name}")
                st.success("✅ Submitted for Approval!")
    st.stop()

st.title("🛁 Pricelist Search - ONLY 3 PAGES")
if st.session_state.is_admin:
    st.success("✅ FIXED - Shows ONLY 3 Pages with ALL WORDS + Images Fixed")
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
with col2: search_query = st.text_input("Search Pricelist", placeholder="e.g. mint spout")

search_btn = st.button("🔍 SEARCH - Show ONLY 3 Pages", use_container_width=True, type="primary")

if search_btn:
    if not search_query.strip():
        st.warning("Type word to search")
    else:
        all_files = get_all_pdfs_any_name()
        st.write(f"📄 Files: {all_files}")

        if not all_files:
            st.error("No PDFs!")
        else:
            filtered = all_files
            if brand_filter!="All Brands":
                tmp = [f for f in all_files if brand_filter.lower() in f.lower()]
                if tmp: filtered = tmp

            query_words = search_query.strip().split()
            total_q = len(query_words)
            st.info(f"Searching **{query_words}** — Will **STOP after 3 pages with ALL {total_q} words** and show ONLY 3")

            final_all_match = []
            progress = st.progress(0)
            status = st.empty()

            for idx, filename in enumerate(filtered):
                if len(final_all_match) >= 3:
                    status.write(f"✅ STOPPED - Found 3 ALL MATCHES - Fast!")
                    break

                status.write(f"🔍 {idx+1}/{len(filtered)}: {filename} | ALL MATCH found: {len(final_all_match)}/3")
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
                        pages, scanned = search_stop_at_3_all_match(pdf_bytes, search_query)
                        for p in pages:
                            # Add filename to tuple
                            final_all_match.append((filename, p[0], p[1], p[2], p[3]))
                            if len(final_all_match) >= 3:
                                break
                except Exception as e:
                    st.write(f"Error {filename}: {e}")
                progress.progress((idx+1)/len(filtered))

            progress.empty()
            status.empty()

            if len(final_all_match) >= 3:
                final_all_match = final_all_match[:3] # ONLY 3 PAGES
                st.success(f"✅ Found 3 pages with ALL {total_q} words - Showing ONLY 3 Pages - STOPPED EARLY - FAST!")

                for filename, page_no, match_count, matched_words, img_bytes in final_all_match:
                    with st.container(border=True):
                        st.write(f"### 📄 {filename} — Page {page_no} — 🟢 ALL {match_count} WORDS — Matched: {', '.join(matched_words)}")
                        st.image(img_bytes, caption=f"Page {page_no} - {filename} - ALL {match_count} WORDS MATCH", use_column_width=True)

            elif len(final_all_match) > 0:
                st.success(f"Found {len(final_all_match)} pages with ALL WORDS (less than 3)")
                for filename, page_no, match_count, matched_words, img_bytes in final_all_match:
                    with st.container(border=True):
                        st.write(f"### 📄 {filename} — Page {page_no} — 🟢 ALL {match_count} WORDS")
                        st.image(img_bytes, caption=f"Page {page_no}", use_column_width=True)

            else:
                # No ALL MATCH found - fallback to max matching
                st.warning(f"No page with ALL {total_q} words found - Showing max matching (2 words, 1 word) fallback...")
                fallback_results = []
                for filename in filtered:
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
                            pages = search_max_matching_fallback(pdf_bytes, search_query)
                            for p in pages:
                                fallback_results.append((filename, p[0], p[1], p[2], p[3]))
                    except: pass
                fallback_results.sort(key=lambda x: x[2], reverse=True)
                fallback_results = fallback_results[:3] # ONLY 3 PAGES even in fallback

                if not fallback_results:
                    st.error(f"No match for '{search_query}'")
                else:
                    st.info(f"Showing top {len(fallback_results)} max matching pages (ALL WORDS not found)")
                    for filename, page_no, match_count, matched_words, img_bytes in fallback_results:
                        with st.container(border=True):
                            badge = f"🟡 {match_count} WORDS" if match_count>=2 else f"🔵 {match_count} WORD"
                            st.write(f"### 📄 {filename} — Page {page_no} — {badge} — Matched: {', '.join(matched_words)}")
                            st.image(img_bytes, caption=f"Page {page_no}", use_column_width=True)

st.divider()
st.header("💰 All Pricelists - Download")
all_files = get_all_pdfs_any_name()
if not all_files: st.info("No Pricelists")
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
    st.header("👑 Admin Panel")

    with st.expander("👥 Customer Approvals - RESTORED ✅", expanded=True):
        customers_data, sha_c = get_json_file("data/customers.json", [])
        st.write(f"Total Customers: {len(customers_data)} | Pending: {len([c for c in customers_data if not c.get('approved')])}")
        if not customers_data:
            st.info("No customers yet")
        else:
            for i, c in enumerate(customers_data):
                status_txt = "✅ Approved" if c.get("approved") else "⏳ Pending"
                with st.container(border=True):
                    col1, col2, col3 = st.columns([3,1,1])
                    with col1:
                        st.write(f"**{c.get('name')}** | {c.get('mail')} | {c.get('contact')} | {c.get('city')} | {status_txt}")
                    with col2:
                        if not c.get("approved"):
                            if st.button("✅ Approve", key=f"app_cust_{i}", type="primary"):
                                customers_data[i]["approved"] = True
                                save_json_file("data/customers.json", customers_data, sha_c, f"Approve {c.get('mail')}")
                                st.rerun()
                    with col3:
                        if st.button("❌ Delete", key=f"del_cust_{i}"):
                            customers_data.pop(i)
                            save_json_file("data/customers.json", customers_data, sha_c, f"Delete {c.get('mail')}")
                            st.rerun()

    with st.expander("📤 Upload Pricelists - ANY NAME", expanded=False):
        up_brand = st.selectbox("Select Brand", brands_data, key="up_brand_final")
        up_files = st.file_uploader("Choose PDFs - ANY NAME", type=["pdf"], accept_multiple_files=True, key="up_final")
        if st.button("⬆️ Upload", type="primary"):
            for f in up_files:
                try:
                    safe_name = f.name.replace(" ", "_")
                    file_bytes = f.getvalue()
                    fname = safe_name
                    if len(file_bytes)/(1024*1024) > 90:
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
                    st.success(f"✅ Uploaded {fname}")
                except Exception as e:
                    st.error(f"Failed {f.name}: {e}")
