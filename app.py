import streamlit as st
import base64, json, io
import fitz
from github import Github

st.set_page_config(page_title="Bathroom AI - ONLY PRICELISTS", layout="wide")

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

def search_inside_pdf(pdf_bytes, query):
    query_words = [w.lower() for w in query.strip().split() if w.strip()][:4]
    if not query_words: return []
    results = []
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page_idx in range(len(doc)):
            page = doc.load_page(page_idx)
            text_lower = page.get_text("text").lower()
            matched = [q for q in query_words if q in text_lower]
            if matched:
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                results.append((page_idx+1, len(matched), matched, img_bytes))
        doc.close()
    except: pass
    results.sort(key=lambda x: x[1], reverse=True)
    return results

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

st.title("🛁 Pricelist Search - ONLY PRICE LISTS")
if st.session_state.is_admin:
    st.success("✅ ONLY PRICELISTS MODE - Any Name - Search Inside PDF - Max Matching")
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
with col2: search_query = st.text_input("Search Pricelist", placeholder="e.g. Mint shower 1234")

search_btn = st.button("🔍 SEARCH INSIDE PRICELISTS - All3>All2>All1", use_container_width=True, type="primary")

if search_btn:
    if not search_query.strip():
        st.warning("Type word to search")
    else:
        all_files = get_all_pdfs_any_name()
        st.write(f"📄 Pricelist files in system: {all_files}")

        if not all_files:
            st.error("No Pricelist PDFs! Upload below")
        else:
            filtered = all_files
            if brand_filter!="All Brands":
                filtered = [f for f in all_files if brand_filter.lower() in f.lower()]
                if not filtered: filtered = all_files

            query_words = search_query.strip().split()
            st.info(f"Searching **{query_words}** inside {len(filtered)} pricelist(s) — Max Matching: **ALL {len(query_words)} > {len(query_words)-1} > 1**")

            final_results = []
            progress = st.progress(0)
            status = st.empty()

            for idx, filename in enumerate(filtered):
                status.write(f"🔍 Searching {idx+1}/{len(filtered)}: {filename} - 20-30 sec for 100MB")
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
                        pages = search_inside_pdf(pdf_bytes, search_query)
                        for page_no, match_count, matched_words, img_bytes in pages:
                            final_results.append((filename, page_no, match_count, matched_words, img_bytes, pdf_bytes))
                except Exception as e:
                    st.write(f"Error {filename}: {e}")
                progress.progress((idx+1)/len(filtered))

            progress.empty()
            status.empty()
            final_results.sort(key=lambda x: x[2], reverse=True)

            if not final_results:
                st.error(f"No match for '{search_query}' - Try single word like 'mint' or code like '1234'")
            else:
                st.success(f"✅ Found {len(final_results)} pages in Pricelists")
                files_dict = {}
                for filename, page_no, match_count, matched_words, img_bytes, pdf_bytes in final_results:
                    if filename not in files_dict: files_dict[filename]=[]
                    files_dict[filename].append((page_no, match_count, matched_words, img_bytes))

                for filename, pages in files_dict.items():
                    pages.sort(key=lambda x: x[1], reverse=True)
                    with st.container(border=True):
                        st.write(f"### 📄 {filename} — {len(pages)} pages found")
                        for page_no, match_count, matched_words, img_bytes in pages[:15]:
                            if match_count == len(query_words): badge = f"🟢 ALL {match_count} WORDS"
                            elif match_count>=2: badge = f"🟡 {match_count} WORDS"
                            else: badge = f"🔵 {match_count} WORD"
                            st.write(f"**Page {page_no}** — {badge} — Matched: {', '.join(matched_words)}")
                            st.image(img_bytes, caption=f"Page {page_no} - {filename}", use_container_width=True)
                            st.divider()

# Download section
st.divider()
st.header("💰 All Pricelists - Download")
all_files = get_all_pdfs_any_name()
if not all_files: st.info("No Pricelists yet - Upload below")
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

    with st.expander("📊 Status - Pricelists Only", expanded=True):
        all_files = get_all_pdfs_any_name()
        st.write(f"**Pricelist PDFs (ANY NAME):** {all_files}")
        st.write(f"**Count:** {len(all_files)} pricelist(s)")
        if len(all_files)==0:
            st.error("No files! Upload your Fantini_Pricelist_2026.pdf below")
        else:
            st.success(f"You have {len(all_files)} pricelist(s) - ALL searchable!")

    with st.expander("📤 Upload Pricelists - ANY NAME - SEARCHABLE", expanded=True):
        st.info("✅ Upload ANY NAME - Will be searchable inside PDF!")
        up_brand = st.selectbox("Select Brand", brands_data, key="up_brand")
        up_files = st.file_uploader("Choose PRICELIST PDFs - ANY NAME - Searchable", type=["pdf"], accept_multiple_files=True, key="up_any")
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
                        st.success(f"✅ Uploaded {fname} to Releases (100MB+) - SEARCHABLE!")
                    else:
                        path = f"pdfs/{fname}"
                        try:
                            ex = repo.get_contents(path)
                            repo.update_file(path, f"Update {fname}", file_bytes, ex.sha)
                        except:
                            repo.create_file(path, f"Add {fname}", file_bytes)
                        st.success(f"✅ Uploaded {fname} - SEARCHABLE!")

                except Exception as e:
                    st.error(f"Failed {f.name}: {e}")
