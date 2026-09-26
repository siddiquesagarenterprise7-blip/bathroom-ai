import streamlit as st, os, glob, hashlib, sqlite3, shutil
from datetime import datetime

# ========== CONFIG ==========
st.set_page_config(page_title="Product and price finder", layout="wide", page_icon="🔍")
ADMIN_EMAIL = "siddique.sagarenterprise7@gmail.com"
ADMIN_PASS = "Sagar@2026"
PDF_FOLDER = "files"
DB_PATH = "users.db"
IMAGE_FOLDER = "extracted_images"

os.makedirs(PDF_FOLDER, exist_ok=True)
os.makedirs(IMAGE_FOLDER, exist_ok=True)

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def get_pdfs():
    return sorted(glob.glob(os.path.join(PDF_FOLDER, "*.pdf")))

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (email TEXT PRIMARY KEY, name TEXT, mobile TEXT, city TEXT, state TEXT, pincode TEXT, company TEXT, password TEXT, status TEXT, allowed_files TEXT, created_at TEXT)''')
    # Force reset admin to Sagar@2026 every time
    c.execute("DELETE FROM users WHERE lower(email)=?", (ADMIN_EMAIL.lower(),))
    c.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (ADMIN_EMAIL.lower(), "Siddique Admin", "9840830500", "Chennai", "TN", "600000", "Sagar Enterprise",
               hash_pw(ADMIN_PASS), "approved", "", datetime.now().isoformat()))
    conn.commit()
    conn.close()

init_db()

def login_user(email, pw):
    email = email.strip().lower()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email=? AND password=?", (email, hash_pw(pw)))
    r = c.fetchone()
    conn.close()
    if not r:
        return None, "Wrong email/password"
    if r[8] == "pending":
        return None, "Pending approval. Call 9840830500"
    if r[8] == "blocked":
        return None, "Blocked. Call owner"
    return {"email": r[0], "name": r[1], "is_admin": r[0] == ADMIN_EMAIL.lower(), "allowed_files": r[9].split(",") if r[9] else []}, "ok"

if "user" not in st.session_state:
    st.session_state.user = None

# ========== LOGIN PAGE ==========
if not st.session_state.user:
    st.title("🔍 Product and price finder")
    st.caption("Sagar Enterprise - Chennai")
    t1, t2 = st.tabs(["🔐 Login", "📝 Customer Signup"])
    with t1:
        e = st.text_input("Email")
        p = st.text_input("Password", type="password")
        if st.button("Login", use_container_width=True, type="primary"):
            u, msg = login_user(e, p)
            if u:
                st.session_state.user = u
                st.rerun()
            else:
                st.error(msg)
    with t2:
        st.info("Customer signup - needs admin approval")
        name = st.text_input("Full Name")
        mob = st.text_input("Mobile")
        email_s = st.text_input("New Email")
        city = st.text_input("City")
        pw_s = st.text_input("Set Password", type="password")
        if st.button("Request Approval", use_container_width=True):
            if not email_s or not pw_s:
                st.error("Email & Password required")
            else:
                conn = sqlite3.connect(DB_PATH)
                try:
                    conn.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                 (email_s.lower(), name, mob, city, "TN", "600000", "", hash_pw(pw_s), "pending", "", datetime.now().isoformat()))
                    conn.commit()
                    st.success("Sent for approval. Call 9840830500")
                except:
                    st.error("Email already exists")
                conn.close()

# ========== MAIN APP ==========
else:
    u = st.session_state.user
    st.sidebar.title("🔍 Product and price finder")
    st.sidebar.write(f"👋 {u['name']}")
    st.sidebar.write(f"📧 {u['email']}")

    st.sidebar.divider()
    st.sidebar.subheader("🧹 Maintenance")
    c_a, c_b = st.sidebar.columns(2)
    with c_a:
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()
    with c_b:
        if st.button("🗑️ Clear Cache", use_container_width=True):
            st.cache_data.clear()
            st.cache_resource.clear()
            if os.path.exists(IMAGE_FOLDER):
                shutil.rmtree(IMAGE_FOLDER)
                os.makedirs(IMAGE_FOLDER, exist_ok=True)
            st.toast("Cache Cleared!", icon="✅")
            st.rerun()

    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state.user = None
        st.rerun()

    # --- ADMIN PANEL ---
    if u["is_admin"]:
        st.title("👑 Product and price finder - Admin Panel")

        col1, col2, col3 = st.columns(3)
        col1.metric("📄 PDF Files", len(get_pdfs()))
        col2.metric("🖼️ Cached Images", len(glob.glob(f"{IMAGE_FOLDER}/*")) if os.path.exists(IMAGE_FOLDER) else 0)
        with col3:
            if st.button("🔄 Refresh Data Now", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

        st.divider()
        st.subheader("📤 Upload PDF (Price List / Catalogue)")
        up = st.file_uploader("Choose PDF", type=["pdf"])
        if up and st.button("Save PDF", type="primary"):
            path = os.path.join(PDF_FOLDER, up.name)
            open(path, "wb").write(up.getbuffer())
            st.success(f"✅ Saved {up.name}")
            st.rerun()

        pdfs = [os.path.basename(f) for f in get_pdfs()]
        if pdfs:
            st.write(f"**Available Files:** {pdfs}")
        else:
            st.warning("No PDFs uploaded yet")

        st.divider()
        st.subheader("👥 Customer Management")
        conn = sqlite3.connect(DB_PATH)
        users = conn.execute("SELECT * FROM users WHERE email!=?", (ADMIN_EMAIL.lower(),)).fetchall()
        conn.close()

        if not users:
            st.info("No customer requests yet")
        else:
            for row in users:
                email_u, name_u, mob_u, city_u, status_u, allowed = row[0], row[1], row[2], row[3], row[8], row[9]
                with st.expander(f"{'🟢' if status_u=='approved' else '🟡' if status_u=='pending' else '🔴'} {name_u} | {email_u} | {mob_u} | {status_u.upper()}"):
                    st.write(f"City: {city_u} | Mobile: {mob_u}")
                    sel = []
                    st.write("**Allow access to files:**")
                    for pdfn in pdfs:
                        checked = pdfn in (allowed.split(",") if allowed else [])
                        if st.checkbox(pdfn, value=checked, key=f"{email_u}_{pdfn}"):
                            sel.append(pdfn)
                    c1, c2, c3 = st.columns(3)
                    if c1.button("✅ Approve", key=f"ap_{email_u}", use_container_width=True):
                        conn = sqlite3.connect(DB_PATH)
                        conn.execute("UPDATE users SET status='approved', allowed_files=? WHERE email=?", (",".join(sel), email_u))
                        conn.commit(); conn.close()
                        st.success("Approved"); st.rerun()
                    if c2.button("🚫 Block", key=f"bl_{email_u}", use_container_width=True):
                        conn = sqlite3.connect(DB_PATH)
                        conn.execute("UPDATE users SET status='blocked' WHERE email=?", (email_u,))
                        conn.commit(); conn.close()
                        st.rerun()
                    if c3.button("🗑️ Delete", key=f"del_{email_u}", use_container_width=True):
                        conn = sqlite3.connect(DB_PATH)
                        conn.execute("DELETE FROM users WHERE email=?", (email_u,))
                        conn.commit(); conn.close()
                        st.rerun()

    # --- CUSTOMER SEARCH ---
    st.divider()
    st.subheader("🔍 Product and price finder - AI Search")
    q = st.text_input("Search product e.g. 'counter top basin', 'SS 202 tap', 'water closet'")

    pdfs_all = get_pdfs()
    if u["is_admin"]:
        allowed_pdfs = pdfs_all
    else:
        allowed_pdfs = [os.path.join(PDF_FOLDER, f) for f in u["allowed_files"] if os.path.exists(os.path.join(PDF_FOLDER, f))]

    if q:
        if not allowed_pdfs:
            st.warning("No files allowed for you. Contact Admin 9840830500")
        else:
            st.info(f"Searching '{q}' in {len(allowed_pdfs)} file(s)... (Full Image+Text AI coming next - upload your PDFs now)")
            # Simple text search demo - will upgrade to image search
            import fitz
            found = []
            for pdf_path in allowed_pdfs:
                try:
                    doc = fitz.open(pdf_path)
                    for page in doc:
                        text = page.get_text()
                        if q.lower() in text.lower():
                            found.append(f"{os.path.basename(pdf_path)} - Page {page.number+1}")
                except:
                    pass
            if found:
                st.success(f"Found in: {found[:10]}")
            else:
                st.warning("No text match - but image search will be added next")

    st.sidebar.divider()
    st.sidebar.caption("© Sagar Enterprise | Chennai\nProduct and price finder v1.0")
