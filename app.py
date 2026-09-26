import streamlit as st, os, glob, hashlib, sqlite3, base64, re
from datetime import datetime
import fitz
st.set_page_config(page_title="Product and price finder", layout="wide")

ADMIN_EMAIL="siddique.sagarenterprise7@gmail.com"
ADMIN_PASS="SagarEnt@2026!Secure"
PDF_FOLDER="files"
DB_PATH="users.db"
os.makedirs(PDF_FOLDER, exist_ok=True)

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()
def get_pdfs(): return sorted(glob.glob(os.path.join(PDF_FOLDER, "*.pdf")))

def init_db():
    conn=sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS users
    (email TEXT PRIMARY KEY, name TEXT, mobile TEXT, company TEXT, address TEXT, city TEXT, pincode TEXT, password TEXT, status TEXT, created_at TEXT)''')
    try:
        cols=[r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        for c in ["company","address","city","pincode"]:
            if c not in cols: conn.execute(f"ALTER TABLE users ADD COLUMN {c} TEXT")
    except: pass
    conn.execute("INSERT OR REPLACE INTO users (email,name,mobile,company,address,city,pincode,password,status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                 (ADMIN_EMAIL.lower(),"Admin","9840830500","","","","",hash_pw(ADMIN_PASS),"approved",datetime.now().strftime("%Y-%m-%d")))
    conn.commit(); conn.close()

init_db()

if "user" not in st.session_state: st.session_state.user=None
if "view_file" not in st.session_state: st.session_state.view_file=None
if "page_num" not in st.session_state: st.session_state.page_num=0

if not st.session_state.user:
    st.title("🔍 Product and price finder - Sagar Enterprise")
    t1,t2=st.tabs(["🔐 Login","📝 Customer Sign-Up"])
    with t1:
        e=st.text_input("Email", placeholder="Enter your email", key="login_email_final")
        p=st.text_input("Password", type="password", placeholder="Enter password", key="login_pass_final")
        if st.button("Login", type="primary", use_container_width=True):
            if not e or not p: st.error("Enter email and password")
            else:
                conn=sqlite3.connect(DB_PATH)
                r=conn.execute("SELECT email,name,mobile,status FROM users WHERE email=? AND password=?",(e.lower().strip(),hash_pw(p))).fetchone()
                conn.close()
                if not r: st.error("Wrong email/password")
                elif r[3]!="approved" and r[0]!=ADMIN_EMAIL.lower(): st.warning("⏳ Pending Admin approval")
                else: st.session_state.user={"email":r[0],"name":r[1],"mobile":r[2],"is_admin":r[0]==ADMIN_EMAIL.lower()}; st.rerun()
    with t2:
        st.subheader("Customer Registration")
        c1,c2=st.columns(2)
        with c1:
            name=st.text_input("Full Name *")
            mobile=st.text_input("Mobile *")
            email=st.text_input("Email ID *")
            password=st.text_input("Create Password *", type="password")
        with c2:
            company=st.text_input("Company Name *")
            city=st.text_input("City *")
            pincode=st.text_input("Pincode *")
            address=st.text_area("Full Address *")
        if st.button("Sign Up", type="primary", use_container_width=True):
            if not all([name,mobile,email,password,company,city,pincode,address]): st.error("Fill all * fields")
            else:
                try:
                    conn=sqlite3.connect(DB_PATH)
                    conn.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?)",(email.lower(),name,mobile,company,address,city,pincode,hash_pw(password),"pending",datetime.now().strftime("%Y-%m-%d %H:%M")))
                    conn.commit(); conn.close()
                    st.success("✅ Registered! Wait for Admin approval")
                except: st.error("Email already exists")
    st.stop()

user=st.session_state.user
pdfs=get_pdfs()

# LEFT SIDE - NO DELETE FOR FILES
st.sidebar.title("📁 Sagar Enterprise")
st.sidebar.write(f"Hi, {user.get('name')}")
if user.get('is_admin'): st.sidebar.success("👑 Admin")
if st.sidebar.button("🚪 Logout"): st.session_state.user=None; st.rerun()

st.sidebar.divider()
st.sidebar.subheader(f"📚 Price Lists ({len(pdfs)} files) - No Delete")

# Show 10 files at a time to avoid max error
FILES_PER_PAGE = 10
total_pages = (len(pdfs) + FILES_PER_PAGE - 1) // FILES_PER_PAGE
start = st.session_state.page_num * FILES_PER_PAGE
end = start + FILES_PER_PAGE

for path in pdfs[start:end]:
    with st.sidebar.container(border=True):
        st.sidebar.write(f"📄 {os.path.basename(path)[:35]}")
        if st.sidebar.button("👁️ View", key=f"view_{path}", use_container_width=True):
            st.session_state.view_file=path; st.rerun()

col1,col2=st.sidebar.columns(2)
if col1.button("⬅️ Prev") and st.session_state.page_num>0:
    st.session_state.page_num-=1; st.rerun()
if col2.button("Next ➡️") and st.session_state.page_num < total_pages-1:
    st.session_state.page_num+=1; st.rerun()
st.sidebar.caption(f"Page {st.session_state.page_num+1} of {total_pages}")

if user.get('is_admin'):
    up=st.sidebar.file_uploader("📤 Add More PDF", type=["pdf"], accept_multiple_files=True)
    if up and st.sidebar.button("💾 Save"):
        for f in up: open(os.path.join(PDF_FOLDER,f.name),"wb").write(f.getbuffer())
        st.success("Saved"); st.rerun()

# CUSTOMER LIST - BELOW - WITH COMPANY DETAILS - NO DELETE FOR FILES, ONLY FOR CUSTOMERS IF YOU WANT
if user.get('is_admin'):
    st.sidebar.divider()
    st.sidebar.subheader("👥 Customers - Full Details")
    conn=sqlite3.connect(DB_PATH)
    rows=conn.execute("SELECT name,email,mobile,company,address,city,pincode,status FROM users WHERE email!=? ORDER BY created_at DESC",(ADMIN_EMAIL.lower(),)).fetchall()
    conn.close()
    st.sidebar.metric("Total", len(rows))
    for idx,(n,e,m,comp,addr,city,pin,stat) in enumerate(rows):
        with st.sidebar.container(border=True):
            st.sidebar.write(f"**{n}** - {comp}")
            st.sidebar.caption(f"{e}\n{m}\n🏢 {comp}\n📍 {addr}, {city}-{pin}\n{stat}")
            if stat=="pending":
                if st.sidebar.button("✅ Approve", key=f"ap_{e}_{idx}", use_container_width=True):
                    conn=sqlite3.connect(DB_PATH); conn.execute("UPDATE users SET status='approved' WHERE email=?",(e,)); conn.commit(); conn.close(); st.rerun()

# MAIN SEARCH - EXACT MATCH
st.title("🔍 Product and price finder")
if st.session_state.view_file:
    with open(st.session_state.view_file,"rb") as f: b64=base64.b64encode(f.read()).decode()
    st.markdown(f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="650"></iframe>', unsafe_allow_html=True)
    if st.button("❌ Close"): st.session_state.view_file=None; st.rerun()

st.subheader("🔍 Search")
q=st.text_input("Search ADDA", value="ADDA freestanding")
exact=st.checkbox("🎯 Exact match - all words on same page", value=True)
@st.cache_data
def build_idx():
    idx=[]
    for p in get_pdfs():
        try:
            doc=fitz.open(p)
            for i in range(len(doc)):
                t=doc[i].get_text("text") or ""
                if len(t)>10: idx.append({"file":os.path.basename(p),"page":i+1,"text":t,"low":t.lower(),"path":p,"pno":i})
            doc.close()
        except: pass
    return idx

if q:
    words=[w for w in re.findall(r'\w+', q.lower()) if len(w)>=3]
    index=build_idx()
    res=[x for x in index if all(w in x["low"] for w in words)] if exact else [x for x in index if any(w in x["low"] for w in words)]
    st.success(f"Found {len(res)} pages for '{q}'")
    for it in res[:10]:
        with st.container(border=True):
            st.write(f"**{it['file']} - Page {it['page']}**")
            st.code(it["text"][:1500])
