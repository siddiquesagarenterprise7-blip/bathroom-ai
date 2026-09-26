import streamlit as st, os, glob, hashlib, sqlite3
from datetime import datetime
import fitz

st.set_page_config(page_title="Sagar Enterprise", layout="wide")
ADMIN_EMAIL = "siddique.sagarenterprise7@gmail.com"
ADMIN_PASS = "Sagar@2026"
PDF_FOLDER = "files"
DB_PATH = "users.db"
IMAGE_FOLDER = "extracted_images"
os.makedirs(PDF_FOLDER, exist_ok=True)
os.makedirs(IMAGE_FOLDER, exist_ok=True)

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()
def get_pdfs(): return sorted(glob.glob(os.path.join(PDF_FOLDER, "*.pdf")))

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (email TEXT PRIMARY KEY, name TEXT, mobile TEXT, city TEXT, state TEXT, pincode TEXT, company TEXT, password TEXT, status TEXT, allowed_files TEXT, created_at TEXT)''')
    c.execute("DELETE FROM users WHERE email=?", (ADMIN_EMAIL,))
    c.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?)",(ADMIN_EMAIL,"Siddique Admin","9840830500","Chennai","TN","600000","Sagar Enterprise",hash_pw(ADMIN_PASS),"approved","",datetime.now().isoformat()))
    conn.commit(); conn.close()
init_db()

def login(email,pw):
    email=email.strip().lower()
    conn=sqlite3.connect(DB_PATH)
    c=conn.cursor()
    c.execute("SELECT * FROM users WHERE email=? AND password=?",(email,hash_pw(pw)))
    r=c.fetchone(); conn.close()
    if not r: return None,"Wrong email/password"
    if r[8]=="pending": return None,"Pending approval. Call 9840830500"
    if r[8]=="blocked": return None,"Blocked. Call owner"
    return {"email":r[0],"name":r[1],"is_admin":r[0]==ADMIN_EMAIL,"allowed_files":r[9].split(",") if r[9] else []},"ok"

if "user" not in st.session_state: st.session_state.user=None

if not st.session_state.user:
    st.title("🔐 Sagar Enterprise - Login")
    t1,t2=st.tabs(["Login","Signup"])
    with t1:
        e=st.text_input("Email")
        p=st.text_input("Password",type="password")
        if st.button("Login",use_container_width=True):
            u,msg=login(e,p)
            if u: st.session_state.user=u; st.rerun()
            else: st.error(msg)
    with t2:
        st.info("Customer signup - needs admin approval")
        name=st.text_input("Name"); mob=st.text_input("Mobile"); email_s=st.text_input("New Email"); city=st.text_input("City"); pw_s=st.text_input("Set Password",type="password")
        if st.button("Request Approval"):
            conn=sqlite3.connect(DB_PATH)
            try:
                conn.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?)",(email_s.lower(),name,mob,city,"TN","600000","","",hash_pw(pw_s),"pending","",datetime.now().isoformat()))
                conn.commit(); st.success("Sent for approval. Call 9840830500")
            except: st.error("Email exists")
            conn.close()
else:
    u=st.session_state.user
    st.sidebar.write(f"👋 {u['name']}")
    if st.sidebar.button("Logout"): st.session_state.user=None; st.rerun()
    if u["is_admin"]:
        st.title("👑 Admin Panel - Sagar Enterprise")
        st.subheader("📤 Upload PDF")
        up=st.file_uploader("Upload Price List",type=["pdf"])
        if up and st.button("Save PDF"):
            open(os.path.join(PDF_FOLDER,up.name),"wb").write(up.getbuffer())
            st.success(f"Saved {up.name}"); st.rerun()
        pdfs=[os.path.basename(f) for f in get_pdfs()]
        st.write(f"Files: {pdfs}")
        conn=sqlite3.connect(DB_PATH); users=conn.execute("SELECT * FROM users WHERE email!=?",(ADMIN_EMAIL,)).fetchall(); conn.close()
        for row in users:
            email_u,name_u,mob_u,status_u=row[0],row[1],row[2],row[8]
            with st.expander(f"{name_u} | {email_u} | {status_u}"):
                sel=[]
                for pdfn in pdfs:
                    if st.checkbox(pdfn,value=pdfn in row[9],key=f"{email_u}_{pdfn}"): sel.append(pdfn)
                c1,c2,c3=st.columns(3)
                if c1.button("✅ Approve",key=f"ap_{email_u}"):
                    conn=sqlite3.connect(DB_PATH); conn.execute("UPDATE users SET status='approved', allowed_files=? WHERE email=?",(",".join(sel),email_u)); conn.commit(); conn.close(); st.rerun()
                if c2.button("🚫 Block",key=f"bl_{email_u}"):
                    conn=sqlite3.connect(DB_PATH); conn.execute("UPDATE users SET status='blocked' WHERE email=?",(email_u,)); conn.commit(); conn.close(); st.rerun()
                if c3.button("🗑️ Delete",key=f"del_{email_u}"):
                    conn=sqlite3.connect(DB_PATH); conn.execute("DELETE FROM users WHERE email=?",(email_u,)); conn.commit(); conn.close(); st.rerun()
    st.divider()
    st.subheader("🔍 AI Search (Image+Text)")
    q=st.text_input("Search e.g. counter top basin")
    if q:
        st.info("Search ready - Upload PDFs first, then I will enable full Image+Text extraction")
