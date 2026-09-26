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

# DB
conn=sqlite3.connect(DB_PATH)
conn.execute('CREATE TABLE IF NOT EXISTS users (email TEXT PRIMARY KEY, name TEXT, mobile TEXT, password TEXT, status TEXT, allowed_files TEXT)')
conn.execute("DELETE FROM users WHERE email=?", (ADMIN_EMAIL.lower(),))
conn.execute("INSERT INTO users VALUES (?,?,?,?,?,?)",(ADMIN_EMAIL.lower(),"Siddique Admin","9840830500",hash_pw(ADMIN_PASS),"approved",""))
conn.commit(); conn.close()

if "user" not in st.session_state: st.session_state.user=None
if "view_file" not in st.session_state: st.session_state.view_file=None

def login(e,p):
    c=sqlite3.connect(DB_PATH)
    r=c.execute("SELECT * FROM users WHERE email=? AND password=?",(e.lower(),hash_pw(p))).fetchone()
    c.close()
    if not r: return None
    return {"email":r[0],"name":r[1],"is_admin":r[0]==ADMIN_EMAIL.lower()}

if not st.session_state.user:
    st.title("🔍 Product and price finder")
    st.caption("Sagar Enterprise - Login: siddique.sagarenterprise7@gmail.com / Sagar@2026")
    e=st.text_input("Email", value="siddique.sagarenterprise7@gmail.com")
    p=st.text_input("Password", type="password", value="Sagar@2026")
    if st.button("Login", type="primary", use_container_width=True):
        u=login(e,p)
        if u: st.session_state.user=u; st.rerun()
        else: st.error("Wrong password")
else:
    u=st.session_state.user
    # SIDEBAR
    st.sidebar.title("🔍 Product and price finder")
    st.sidebar.write(f"👋 {u['name']}")
    st.sidebar.write(f"{ADMIN_EMAIL}")
    st.sidebar.divider()
    if st.sidebar.button("🔄 Refresh", use_container_width=True): st.rerun()
    if st.sidebar.button("🗑️ Clear Cache", use_container_width=True):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.sidebar.success("Cleared!")
        st.rerun()
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state.user=None
        st.session_state.view_file=None
        st.rerun()

    st.title("👑 Product and price finder - Admin")
    st.divider()

    # UPLOAD
    st.subheader("📤 Upload PDF")
    up=st.file_uploader("Choose Price List PDF", type=["pdf"])
    if up:
        if st.button("💾 Save PDF", type="primary"):
            path=os.path.join(PDF_FOLDER, up.name)
            with open(path,"wb") as f: f.write(up.getbuffer())
            st.success(f"Saved {up.name}")
            st.rerun()

    # ===== THIS IS WHAT YOU SAID "Earlier it was shown" - NOW FIXED =====
    st.divider()
    st.subheader("📁 Saved Price Lists - Lined Up")
    pdfs=get_pdfs()
    if not pdfs:
        st.warning("No files in 'files' folder. Upload above.")
    else:
        st.success(f"Found {len(pdfs)} files")
        # Header row
        h1,h2,h3,h4=st.columns([4,1.5,1.5,1.5])
        h1.markdown("**File Name**")
        h2.markdown("**Size**")
        h3.markdown("**View**")
        h4.markdown("**Download/Delete**")

        for path in pdfs:
            fname=os.path.basename(path)
            size=os.path.getsize(path)/1024/1024
            c1,c2,c3,c4=st.columns([4,1.5,1.5,1.5])
            c1.write(f"📄 {fname}")
            c2.write(f"{size:.2f} MB")
            if c3.button("👁️ View", key=f"view_{fname}", use_container_width=True):
                st.session_state.view_file=path
            colA,colB=c4.columns(2)
            with open(path,"rb") as f:
                colA.download_button("⬇️", f, file_name=fname, key=f"dl_{fname}", use_container_width=True)
            if colB.button("🗑️", key=f"del_{fname}", use_container_width=True):
                os.remove(path)
                if st.session_state.view_file==path: st.session_state.view_file=None
                st.rerun()

    # VIEWER - Shows below table like earlier
    if st.session_state.view_file and os.path.exists(st.session_state.view_file):
        st.divider()
        st.subheader(f"👁️ Viewing: {os.path.basename(st.session_state.view_file)}")
        if st.button("❌ Close Viewer"):
            st.session_state.view_file=None
            st.rerun()
        try:
            with open(st.session_state.view_file,"rb") as f:
                b64=base64.b64encode(f.read()).decode()
            pdf_html=f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="800" type="application/pdf"></iframe>'
            st.markdown(pdf_html, unsafe_allow_html=True)
        except Exception as e:
            st.error(str(e))

    # ===== SEARCH - FIXED FOR TEXT PDF =====
    st.divider()
    st.subheader("🔍 Product and price finder - AI Search")
    st.caption("Search e.g. 'counter top basin', 'SS 202 tap', 'adda basins'")

    q=st.text_input("Type to search", placeholder="adda basins")
    if q:
        q_lower=q.lower().strip()
        words=q_lower.split()
        results=[]
        for path in pdfs:
            try:
                doc=fitz.open(path)
                for pno in range(len(doc)):
                    text=doc[pno].get_text() or ""
                    tl=text.lower()
                    # Match if ALL words appear anywhere on page (not exact phrase)
                    if all(w in tl for w in words):
                        # Find snippet
                        first=words[0]
                        idx=tl.find(first)
                        snippet=text[max(0,idx-100):idx+400]
                        results.append({"file":os.path.basename(path),"page":pno+1,"snippet":snippet,"path":path,"pno":pno})
            except Exception as e:
                st.error(f"{path}: {e}")

        if results:
            st.success(f"✅ Found {len(results)} matches for '{q}'")
            for r in results[:25]:
                with st.container(border=True):
                    st.markdown(f"**📄 {r['file']}** | Page **{r['page']}**")
                    st.text(r['snippet'])
                    c1,c2=st.columns([1,1])
                    with open(r['path'],"rb") as f:
                        c1.download_button(f"⬇️ Open {r['file']}", f, file_name=r['file'], key=f"res_{r['file']}_{r['page']}_{q}_{r['pno']}")
                    if c2.button(f"👁️ View Page {r['page']}", key=f"pv_{r['file']}_{r['page']}_{q}_{r['pno']}"):
                        st.session_state.view_file=r['path']
                        st.rerun()
        else:
            st.error(f"❌ No match for '{q}'")
            st.info("Tip: Try single word. Your file has 'ADDA' - search 'adda' not 'adda basins'")
            if pdfs:
                st.write("Debug - Sample from first file Page 1:")
                try:
                    doc=fitz.open(pdfs[0])
                    st.code(doc[0].get_text()[:1000])
                except: pass
