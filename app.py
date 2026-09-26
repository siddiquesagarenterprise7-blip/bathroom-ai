import streamlit as st, os, glob, hashlib, sqlite3, base64
import fitz

st.set_page_config(page_title="Product and price finder", layout="wide", page_icon="🔍")
ADMIN_EMAIL = "siddique.sagarenterprise7@gmail.com"
ADMIN_PASS = "Sagar@2026"
PDF_FOLDER = "files"
DB_PATH = "users.db"
os.makedirs(PDF_FOLDER, exist_ok=True)

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()
def get_pdfs(): return sorted(glob.glob(os.path.join(PDF_FOLDER, "*.pdf")))

# ===== FIXED DB - No more OperationalError =====
def init_db():
    conn=sqlite3.connect(DB_PATH)
    c=conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (email TEXT PRIMARY KEY, name TEXT, mobile TEXT, password TEXT, status TEXT, allowed_files TEXT)''')
    conn.commit()
    # Now safely insert admin - Use INSERT OR REPLACE
    c.execute("INSERT OR REPLACE INTO users VALUES (?,?,?,?,?,?)",
              (ADMIN_EMAIL.lower(), "Siddique Admin", "9840830500", hash_pw(ADMIN_PASS), "approved", ""))
    conn.commit()
    conn.close()

init_db()

if "user" not in st.session_state: st.session_state.user=None
if "view_file" not in st.session_state: st.session_state.view_file=None

def login(e,p):
    conn=sqlite3.connect(DB_PATH)
    r=conn.execute("SELECT * FROM users WHERE email=? AND password=?",(e.lower(),hash_pw(p))).fetchone()
    conn.close()
    if not r: return None
    return {"email":r[0],"name":r[1],"is_admin":r[0]==ADMIN_EMAIL.lower()}

if not st.session_state.user:
    st.title("🔍 Product and price finder")
    e=st.text_input("Email", value=ADMIN_EMAIL)
    p=st.text_input("Password", type="password", value=ADMIN_PASS)
    if st.button("Login", type="primary", use_container_width=True):
        u=login(e,p)
        if u: st.session_state.user=u; st.rerun()
        else: st.error("Wrong Email/Password")
else:
    u=st.session_state.user
    st.sidebar.title("🔍 Product and price finder")
    st.sidebar.write(f"👋 {u['name']}")
    st.sidebar.divider()
    if st.sidebar.button("🔄 Refresh", use_container_width=True): st.rerun()
    if st.sidebar.button("🗑️ Clear Cache", use_container_width=True):
        st.cache_data.clear(); st.cache_resource.clear(); st.rerun()
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state.user=None; st.session_state.view_file=None; st.rerun()

    st.title("👑 Product and price finder")
    st.divider()

    st.subheader("📤 Upload PDF")
    up=st.file_uploader("Upload", type=["pdf"])
    if up and st.button("💾 Save PDF", type="primary"):
        open(os.path.join(PDF_FOLDER, up.name),"wb").write(up.getbuffer())
        st.success(f"Saved {up.name}"); st.rerun()

    st.divider()
    st.subheader("📁 Saved Price Lists - Lined Up & Viewable")
    pdfs=get_pdfs()
    if not pdfs: st.warning("No files - Upload above")
    else:
        h1,h2,h3,h4=st.columns([4,1,1,1])
        h1.markdown("**File**"); h2.markdown("**Size**"); h3.markdown("**View**"); h4.markdown("**Action**")
        for path in pdfs:
            fname=os.path.basename(path)
            size=os.path.getsize(path)/1024/1024
            c1,c2,c3,c4=st.columns([4,1,1,1])
            c1.write(f"📄 {fname}")
            c2.write(f"{size:.2f} MB")
            if c3.button("👁️ View", key=f"view_{fname}", use_container_width=True):
                st.session_state.view_file=path
            with open(path,"rb") as f:
                c4.download_button("⬇️", f, file_name=fname, key=f"dl_{fname}", use_container_width=True)

    if st.session_state.view_file and os.path.exists(st.session_state.view_file):
        st.divider()
        st.subheader(f"Viewing: {os.path.basename(st.session_state.view_file)}")
        if st.button("❌ Close Viewer"): st.session_state.view_file=None; st.rerun()
        with open(st.session_state.view_file,"rb") as f:
            b64=base64.b64encode(f.read()).decode()
        st.markdown(f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="800"></iframe>', unsafe_allow_html=True)

    st.divider()
    st.subheader("🔍 Search - Text PDF")
    q=st.text_input("Search e.g. adda, basin, tap")
    if q:
        q_lower=q.lower()
        words=q_lower.split()
        results=[]
        for path in pdfs:
            doc=fitz.open(path)
            for pno in range(len(doc)):
                tl=doc[pno].get_text().lower()
                if all(w in tl for w in words):
                    txt=doc[pno].get_text()
                    idx=tl.find(words[0])
                    snip=txt[max(0,idx-80):idx+400]
                    results.append((os.path.basename(path),pno+1,snip))
        if results:
            st.success(f"Found {len(results)} matches")
            for fn,pg,snip in results[:20]:
                with st.container(border=True):
                    st.write(f"**{fn}** - Page {pg}")
                    st.text(snip)
        else:
            st.error(f"No results for '{q}' - try single word 'adda'")
