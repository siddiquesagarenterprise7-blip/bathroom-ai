import streamlit as st, os, glob, hashlib, sqlite3, base64
import fitz

st.set_page_config(page_title="Product and price finder", layout="wide")
ADMIN_EMAIL = "siddique.sagarenterprise7@gmail.com"
ADMIN_PASS = "Sagar@2026"
PDF_FOLDER = "files"
DB_PATH = "users.db"
os.makedirs(PDF_FOLDER, exist_ok=True)

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()
def get_pdfs(): return sorted(glob.glob(os.path.join(PDF_FOLDER, "*.pdf")))

# === FIXED - AUTO DELETE OLD DB IF SCHEMA MISMATCH ===
if os.path.exists(DB_PATH):
    try:
        conn=sqlite3.connect(DB_PATH)
        conn.execute("SELECT email, name, password FROM users LIMIT 1")
        conn.close()
    except:
        os.remove(DB_PATH) # old schema, delete it

conn=sqlite3.connect(DB_PATH)
conn.execute('CREATE TABLE IF NOT EXISTS users (email TEXT PRIMARY KEY, name TEXT, password TEXT)')
conn.execute("INSERT OR REPLACE INTO users VALUES (?,?,?)",(ADMIN_EMAIL.lower(),"Admin",hash_pw(ADMIN_PASS)))
conn.commit()
conn.close()

if "user" not in st.session_state: st.session_state.user=None
if "view_file" not in st.session_state: st.session_state.view_file=None

if not st.session_state.user:
    st.title("🔍 Product and price finder")
    e=st.text_input("Email", value="siddique.sagarenterprise7@gmail.com")
    p=st.text_input("Password", type="password", value="Sagar@2026")
    if st.button("Login",type="primary", use_container_width=True):
        c=sqlite3.connect(DB_PATH)
        r=c.execute("SELECT * FROM users WHERE email=? AND password=?",(e.lower(),hash_pw(p))).fetchone()
        c.close()
        if r: st.session_state.user={"email":r[0]}; st.rerun()
        else: st.error("Wrong email/password")
else:
    if st.sidebar.button("Logout"): st.session_state.user=None; st.rerun()
    if st.sidebar.button("🔄 Refresh"): st.rerun()
    if st.sidebar.button("🗑️ Clear Cache"): st.cache_data.clear(); st.rerun()

    st.title("📁 Product and price finder")

    up=st.file_uploader("Upload PDF",type=["pdf"])
    if up and st.button("Save PDF"):
        open(os.path.join(PDF_FOLDER,up.name),"wb").write(up.getbuffer())
        st.success(f"Saved {up.name}"); st.rerun()

    pdfs=get_pdfs()
    st.subheader(f"📁 Saved Price Lists ({len(pdfs)}) - Lined Up & Viewable")
    for path in pdfs:
        fname=os.path.basename(path)
        c1,c2,c3=st.columns([4,1,1])
        c1.write(f"📄 {fname}")
        if c2.button("👁️ View",key=f"v_{fname}"): st.session_state.view_file=path
        with open(path,"rb") as f:
            c3.download_button("⬇️",f,fname,key=f"d_{fname}")

    if st.session_state.view_file and os.path.exists(st.session_state.view_file):
        st.divider()
        st.subheader(f"Viewing: {os.path.basename(st.session_state.view_file)}")
        if st.button("❌ Close Viewer"): st.session_state.view_file=None; st.rerun()
        with open(st.session_state.view_file,"rb") as f:
            b64=base64.b64encode(f.read()).decode()
        st.markdown(f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="700"></iframe>',unsafe_allow_html=True)

    st.divider()
    st.subheader("🔍 Search")
    q=st.text_input("Search e.g. adda")
    if q:
        for path in pdfs:
            doc=fitz.open(path)
            for i in range(len(doc)):
                txt=doc[i].get_text().lower()
                if q.lower() in txt:
                    st.success(f"Found in {os.path.basename(path)} Page {i+1}")
                    st.text(doc[i].get_text()[:800])
