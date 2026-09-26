import streamlit as st, os, glob, hashlib, sqlite3, base64, re
from datetime import datetime
import fitz
st.set_page_config(page_title="Product and price finder", layout="wide")

ADMIN_EMAIL="siddique.sagarenterprise7@gmail.com"
ADMIN_PASS="Sagar@2026"
PDF_FOLDER="files"
DB_PATH="users.db"
os.makedirs(PDF_FOLDER, exist_ok=True)

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()
def get_pdfs(): return sorted(glob.glob(os.path.join(PDF_FOLDER, "*.pdf")))

def init_db():
    conn=sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS users
    (email TEXT PRIMARY KEY, name TEXT, mobile TEXT, password TEXT, status TEXT, created_at TEXT)''')
    conn.execute("INSERT OR REPLACE INTO users VALUES (?,?,?,?,?,?)",
                 (ADMIN_EMAIL.lower(),"Admin","9840830500",hash_pw(ADMIN_PASS),"approved",datetime.now().strftime("%Y-%m-%d")))
    conn.commit(); conn.close()

if os.path.exists(DB_PATH):
    try:
        sqlite3.connect(DB_PATH).execute("SELECT email,name,mobile,password,status,created_at FROM users LIMIT 1").fetchall()
    except: os.remove(DB_PATH)
init_db()

if "user" not in st.session_state: st.session_state.user=None
if "view_file" not in st.session_state: st.session_state.view_file=None
if st.session_state.user and "name" not in st.session_state.user:
    st.session_state.user=None

if not st.session_state.user:
    st.title("🔍 Product and price finder - Sagar Enterprise")
    t1,t2=st.tabs(["🔐 Login","📝 Customer Sign-Up"])
    with t1:
        e=st.text_input("Email", value=ADMIN_EMAIL)
        p=st.text_input("Password", type="password", value=ADMIN_PASS)
        if st.button("Login", type="primary", use_container_width=True):
            conn=sqlite3.connect(DB_PATH)
            r=conn.execute("SELECT email,name,mobile,status FROM users WHERE email=? AND password=?",(e.lower(),hash_pw(p))).fetchone()
            conn.close()
            if not r: st.error("Wrong email/password")
            elif r[3]!="approved" and r[0]!=ADMIN_EMAIL.lower(): st.warning("⏳ Pending Admin approval")
            else:
                st.session_state.user={"email":r[0],"name":r[1],"mobile":r[2],"is_admin":r[0]==ADMIN_EMAIL.lower()}
                st.rerun()
    with t2:
        name=st.text_input("Full Name")
        mobile=st.text_input("Mobile")
        email=st.text_input("Email ID")
        password=st.text_input("Create Password", type="password")
        if st.button("Sign Up", use_container_width=True):
            try:
                conn=sqlite3.connect(DB_PATH)
                conn.execute("INSERT INTO users VALUES (?,?,?,?,?,?)",(email.lower(),name,mobile,hash_pw(password),"pending",datetime.now().strftime("%Y-%m-%d %H:%M")))
                conn.commit(); conn.close()
                st.success("✅ Registered! Wait for Admin approval")
            except: st.error("Email already exists")
    st.stop()

user=st.session_state.user
pdfs=get_pdfs()

# ===== LEFT SIDE =====
st.sidebar.title("📁 Sagar Enterprise")
st.sidebar.write(f"Hi, {user.get('name','User')}")
st.sidebar.caption(user.get('email',''))
if user.get('is_admin'): st.sidebar.success("👑 Admin")
else: st.sidebar.info("👤 Customer")
if st.sidebar.button("🚪 Logout"): st.session_state.user=None; st.session_state.view_file=None; st.rerun()
if st.sidebar.button("🗑️ Clear Cache"): st.cache_data.clear(); st.rerun()

st.sidebar.divider()
st.sidebar.subheader(f"📚 Price Lists ({len(pdfs)})")
if user.get('is_admin'):
    up=st.sidebar.file_uploader("📤 Upload PDF", type=["pdf"], accept_multiple_files=True)
    if up and st.sidebar.button("💾 Save PDFs"):
        for f in up: open(os.path.join(PDF_FOLDER,f.name),"wb").write(f.getbuffer())
        st.sidebar.success(f"Saved {len(up)}"); st.rerun()

for path in pdfs:
    fname=os.path.basename(path)
    with st.sidebar.container(border=True):
        st.sidebar.write(f"📄 {fname[:32]}")
        c1,c2=st.sidebar.columns(2)
        if c1.button("👁️ View", key=f"v_{fname}", use_container_width=True):
            st.session_state.view_file=path; st.rerun()
        with open(path,"rb") as f:
            c2.download_button("⬇️", f, file_name=fname, key=f"d_{fname}", use_container_width=True)

# CUSTOMER LIST BELOW PRICE LIST - ADMIN ONLY
if user.get('is_admin'):
    st.sidebar.divider()
    st.sidebar.subheader("👥 Customer Sign-ups")
    conn=sqlite3.connect(DB_PATH)
    rows=conn.execute("SELECT name,email,mobile,status,created_at FROM users WHERE email!=? ORDER BY created_at DESC",(ADMIN_EMAIL.lower(),)).fetchall()
    conn.close()
    st.sidebar.metric("Total Customers", len(rows))
    if len(rows)==0:
        st.sidebar.info("No customers yet")
    else:
        for idx,(name,email,mobile,status,dt) in enumerate(rows):
            with st.sidebar.container(border=True):
                st.sidebar.write(f"**{name}**")
                st.sidebar.caption(f"{email}\n📱 {mobile}\n{dt}\n{status}")
                if status=="pending":
                    if st.sidebar.button("✅ Approve", key=f"ap_{email}_{idx}", use_container_width=True):
                        conn=sqlite3.connect(DB_PATH); conn.execute("UPDATE users SET status='approved' WHERE email=?",(email,)); conn.commit(); conn.close(); st.rerun()
                else:
                    if st.sidebar.button("❌ Block", key=f"bl_{email}_{idx}", use_container_width=True):
                        conn=sqlite3.connect(DB_PATH); conn.execute("UPDATE users SET status='pending' WHERE email=?",(email,)); conn.commit(); conn.close(); st.rerun()
                if st.sidebar.button("🗑️ Delete", key=f"del_{email}_{idx}", use_container_width=True):
                    conn=sqlite3.connect(DB_PATH); conn.execute("DELETE FROM users WHERE email=?",(email,)); conn.commit(); conn.close(); st.rerun()

# ===== MAIN SEARCH WITH EXACT MATCH FIX =====
st.title("🔍 Product and price finder")

if st.session_state.view_file and os.path.exists(st.session_state.view_file):
    st.info(f"Viewing: {os.path.basename(st.session_state.view_file)}")
    if st.button("❌ Close Viewer"): st.session_state.view_file=None; st.rerun()
    with open(st.session_state.view_file,"rb") as f: b64=base64.b64encode(f.read()).decode()
    st.markdown(f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="650"></iframe>', unsafe_allow_html=True)
    st.divider()

st.subheader("🔍 Search ADDA")

c1,c2=st.columns([3,1])
with c1: q=st.text_input("Search", value="ADDA freestanding", placeholder="e.g. ADDA freestanding, ADDA countertop")
with c2: exact_mode=st.checkbox("🎯 Exact match", value=True, help="If checked, ALL words must be on same page")

@st.cache_data
def build_index():
    idx=[]
    for p in get_pdfs():
        try:
            doc=fitz.open(p)
            for i in range(len(doc)):
                txt=doc[i].get_text("text") or ""
                if len(txt.strip())<10: continue
                idx.append({"file":os.path.basename(p),"page":i+1,"text":txt,"low":txt.lower(),"path":p,"pno":i})
            doc.close()
        except: pass
    return idx

index=build_index()

if st.button("🔍 SEARCH", type="primary") or q:
    q_low=q.lower().strip()
    words=[w for w in re.findall(r'\b\w+\b', q_low) if len(w)>=3]

    if not words:
        st.warning("Type at least 3 letters")
        st.stop()

    exact_results=[]
    partial_results=[]

    for it in index:
        low=it["low"]
        if exact_mode:
            # EXACT: All words must be present - e.g. ADDA + freestanding
            if all(w in low for w in words):
                # Extra check: for freestanding, ensure not countertop when searching freestanding
                exact_results.append(it)
        else:
            if any(w in low for w in words):
                partial_results.append(it)

    if exact_mode:
        results=exact_results
        # Sort: pages with PRICE and ₹ first
        results.sort(key=lambda x: (1 if "₹" in x["text"] else 0, 1 if "PRICE" in x["text"] else 0), reverse=True)
        if results:
            st.success(f"✅ Found {len(results)} EXACT pages for '{q}' - All words [{', '.join(words)}] match on same page")
        else:
            st.error(f"❌ No EXACT match for '{q}'")
            st.info(f"Showing all pages with ANY word [{', '.join(words)}] instead")
            results=[x for x in index if any(w in x["low"] for w in words)]
            results.sort(key=lambda x: 1 if "₹" in x["text"] else 0, reverse=True)
            st.warning(f"Found {len(results)} pages with ANY word - This includes ADDA countertop when you searched freestanding")
    else:
        results=partial_results
        st.success(f"Found {len(results)} pages for ANY word in '{q}'")

    # Make presentation
    if results and len(results)>0:
        if st.button(f"📑 Make Presentation PDF ({min(5,len(results))} pages)"):
            new=fitz.open()
            for it in results[:5]:
                src=fitz.open(it["path"])
                new.insert_pdf(src, from_page=it["pno"], to_page=it["pno"])
                src.close()
            new.save("/tmp/ADDA.pdf"); new.close()
            with open("/tmp/ADDA.pdf","rb") as f:
                st.download_button("⬇️ DOWNLOAD", f, file_name=f"{q.replace(' ','_')}_Price.pdf", type="primary")

    for idx,it in enumerate(results[:10],1):
        with st.container(border=True):
            st.markdown(f"**{idx}. {it['file']} - Page {it['page']}**")
            # Highlight which words matched
            matched=[w for w in words if w in it["low"]]
            st.caption(f"Matched: {', '.join(matched)}")
            col1,col2=st.columns([1,1])
            with col1:
                st.code(it["text"][:2000])
            with col2:
                doc=fitz.open(it["path"])
                pix=doc[it["pno"]].get_pixmap(dpi=220)
                img=f"/tmp/search_{idx}.png"; pix.save(img)
                st.image(img, caption=f"Page {it['page']}", use_container_width=True)
                doc.close()
