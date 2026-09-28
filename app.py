import streamlit as st
import base64, json, io
import fitz
from PIL import Image
from github import Github

st.set_page_config(page_title="Bathroom AI - SHEET FIXED", layout="wide")

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

def search_stop_at_3_all_match(pdf_bytes, query):
    query_words = [w.lower() for w in query.strip().split() if w.strip()][:4]
    total_q = len(query_words)
    all_match_pages = []
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page_idx in range(len(doc)):
            if len(all_match_pages) >= 3: break
            page = doc.load_page(page_idx)
            text_lower = page.get_text("text").lower()
            matched = [q for q in query_words if q in text_lower]
            if len(matched) == total_q and total_q>0:
                # FIXED: Use 120 DPI + PIL Image - ALWAYS SHOWS
                pix = page.get_pixmap(dpi=120)
                img_bytes = pix.tobytes("png")
                pil_img = Image.open(io.BytesIO(img_bytes))
                all_match_pages.append((page_idx+1, len(matched), matched, pil_img))
        doc.close()
    except Exception as e:
        st.write(f"Error: {e}")
    return all_match_pages

def search_fallback(pdf_bytes, query):
    query_words = [w.lower() for w in query.strip().split() if w.strip()][:4]
    results = []
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page_idx in range(len(doc)):
            page = doc.load_page(page_idx)
            text_lower = page.get_text("text").lower()
            matched = [q for q in query_words if q in text_lower]
            if matched:
                pix = page.get_pixmap(dpi=120)
                img_bytes = pix.tobytes("png")
                pil_img = Image.open(io.BytesIO(img_bytes))
                results.append((page_idx+1, len(matched), matched, pil_img))
        doc.close()
    except: pass
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:10]

if "customer_verified" not in st.session_state:
    st.session_state.customer_verified = False
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False
if "customer_email" not in st.session_state:
    st.session_state.customer_email = ""

if not st.session_state.customer_verified and not st.session_state.is_admin:
    st.title("🛁 Login")
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
    st.stop()

st.title("🛁 Pricelist Search - SHEET IMAGE FIXED")
if st.session_state.is_admin:
    st.success("✅ ONLY 3 Pages + SHEET IMAGE FIXED - PIL Image")
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

search_btn = st.button("🔍 SEARCH - Show ONLY 3 Sheets", use_container_width=True, type="primary")

if search_btn:
    if not search_query.strip():
        st.warning("Type word")
    else:
        all_files = get_all_pdfs_any_name()
        filtered = all_files
        if brand_filter!="All Brands":
            tmp = [f for f in all_files if brand_filter.lower() in f.lower()]
            if tmp: filtered = tmp

        query_words = search_query.strip().split()
        total_q = len(query_words)
        st.info(f"Searching {query_words} — STOP at 3 ALL MATCH — Show ONLY 3 SHEETS")

        final_all_match = []
        for idx, filename in enumerate(filtered):
            if len(final_all_match) >= 3: break
            st.write(f"🔍 Searching {filename}...")
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
                    pages = search_stop_at_3_all_match(pdf_bytes, search_query)
                    for p in pages:
                        final_all_match.append((filename, p[0], p[1], p[2], p[3]))
                        if len(final_all_match) >= 3: break
            except: pass

        if len(final_all_match) >= 3:
            final_all_match = final_all_match[:3]
            st.success(f"✅ Found 3 pages with ALL {total_q} words - Showing EXACT SHEETS!")

            for filename, page_no, match_count, matched_words, pil_img in final_all_match:
                with st.container(border=True):
                    st.write(f"### 📄 {filename} — Page {page_no} — 🟢 ALL {match_count} WORDS — Matched: {', '.join(matched_words)}")
                    # THIS WILL NOW SHOW EXACT SHEET
                    st.image(pil_img, caption=f"EXACT SHEET - Page {page_no} - {filename}", use_container_width=True)

        elif len(final_all_match) > 0:
            st.success(f"Found {len(final_all_match)} pages")
            for filename, page_no, match_count, matched_words, pil_img in final_all_match:
                with st.container(border=True):
                    st.write(f"### 📄 {filename} — Page {page_no}")
                    st.image(pil_img, caption=f"Page {page_no}", use_container_width=True)

        else:
            st.warning("No ALL match - Showing fallback max 3")
            fallback = []
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
                        pages = search_fallback(pdf_bytes, search_query)
                        for p in pages:
                            fallback.append((filename, p[0], p[1], p[2], p[3]))
                except: pass
            fallback.sort(key=lambda x: x[2], reverse=True)
            fallback = fallback[:3]
            for filename, page_no, match_count, matched_words, pil_img in fallback:
                with st.container(border=True):
                    st.write(f"Page {page_no} - {', '.join(matched_words)}")
                    st.image(pil_img, caption=f"Page {page_no}", use_container_width=True)

if st.session_state.is_admin:
    st.divider()
    with st.expander("👥 Customer Approvals", expanded=True):
        customers_data, sha_c = get_json_file("data/customers.json", [])
        st.write(f"Total: {len(customers_data)}")
        for i, c in enumerate(customers_data):
            status_txt = "✅" if c.get("approved") else "⏳"
            with st.container(border=True):
                col1, col2 = st.columns([3,1])
                with col1: st.write(f"{c.get('name')} | {c.get('mail')} | {status_txt}")
                with col2:
                    if not c.get("approved"):
                        if st.button("Approve", key=f"app_{i}"):
                            customers_data[i]["approved"] = True
                            save_json_file("data/customers.json", customers_data, sha_c, f"Approve {c.get('mail')}")
                            st.rerun()
