import streamlit as st
import os, glob, hashlib, sqlite3, smtplib
from datetime import datetime
from email.mime.text import MIMEText
import fitz

# ============ CONFIG ============
st.set_page_config(page_title="Sagar Enterprise", layout="wide")
ADMIN_EMAIL = "Siddique.sagarenterprise7@gmail.com"
ADMIN_PASS_DEFAULT = "Sagar@2026"
PDF_FOLDER = "files"
DB_PATH = "users.db"
IMAGE_FOLDER = "extracted_images"
os.makedirs(PDF_FOLDER, exist_ok=True)
os.makedirs(IMAGE_FOLDER, exist_ok=True)

# ============ DB ============
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (email TEXT PRIMARY KEY, name TEXT, mobile TEXT, city TEXT, state TEXT, pincode TEXT, company TEXT, password TEXT, status TEXT, allowed_files TEXT, created_at TEXT)''')
    conn.commit()
    # Auto-create admin if not exists
    c.execute("SELECT * FROM users WHERE email=?", (ADMIN_EMAIL,))
    if not c.fetchone():
        c.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (ADMIN_EMAIL, "Siddique (Admin)", "9840830500", "Chennai", "Tamil Nadu", "600000", "Sagar Enterprise",
                   hashlib.sha256(ADMIN_PASS_DEFAULT.encode()).hexdigest(), "approved", "", datetime.now().isoformat()))
        conn.commit()
    conn.close()
init_db()

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()
def get_pdfs(): return sorted(glob.glob(os.path.join(PDF_FOLDER, "*.pdf")))

# ============ LOAD CATALOG (AI IMAGE+TEXT) ============
@st.cache_resource(show_spinner="🧠 AI reading all PDFs with images... first time 2-3 mins only")
def load_catalog():
    catalog = []
    for pdf_path in get_pdfs():
        fname = os.path.basename(pdf_path)
        try:
            doc = fitz.open(pdf_path)
            for pno in range(len(doc)):
                page = doc[pno]
                text = page.get_text("text")
                imgs = []
                for idx, img in enumerate(page.get_images(full=True)):
                    try:
                        xref = img[0]
                        pix = doc.extract_image(xref)
                        if len(pix["image"]) > 8000: # ignore small icons
                            iname = f"{fname}_{pno+1}_{idx}.{pix['ext']}"
                            ipath = os.path.join(IMAGE_FOLDER, iname)
                            if not os.path.exists(ipath):
                                open(ipath, "wb").write(pix["image"])
                            imgs.append(ipath)
                    except: pass
                if text.strip() or imgs:
                    catalog.append({"file": fname, "page": pno+1, "text": text, "images": imgs})
        except Exception as e:
            st.error(f"Error {fname}: {e}")
    return catalog

# ============ AUTH ============
def signup(name,mob,email,city,state,pin,comp,pw):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if c.execute("SELECT 1 FROM users WHERE email=?",(email,)).fetchone():
        conn.close(); return False,"Email already exists"
    c.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (email,name,mob,city,state,pin,comp,hash_pw(pw),"pending","",datetime.now().isoformat()))
    conn.commit(); conn.close()
    return True,"Signup success! Wait for Admin approval. Call 9840830500"

def login(email,pw):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email=? AND password=?",(email,hash_pw(pw)))
    r = c.fetchone(); conn.close()
    if not r: return None,"Wrong email/password"
    if r[8]=="pending": return None,"Pending approval. Contact owner 9840830500"
    if r[8]=="blocked": return None,"Blocked. Contact owner 9840830500"
    if r[8]=="rejected": return None,"Rejected"
    return {"email":r[0],"name":r[1],"mobile":r[2],"city":r[3],"state":r[4],"pincode":r[5],"company":r[6],"status":r[8],"allowed_files": r[9].split(",") if r[9] else [], "is_admin": r[0]==ADMIN_EMAIL}, "ok"

# ============ SESSION ============
if "user" not in st.session_state: st.session_state.user=None

# ============ LOGIN PAGE ============
if not st.session_state.user:
    st.title("🔐 Sagar Enterprise - Price Search")
    t1,t2 = st.tabs(["Login","Signup"])
    with t1:
        e = st.text_input("Email")
        p = st.text_input("Password",type="password")
        if st.button("Login",use_container_width=True):
            u,msg = login(e.strip().lower(),p)
            if u: st.session_state.user=u; st.rerun()
            else: st.error(msg)
        st.caption(f"Admin: {ADMIN_EMAIL} / {ADMIN_PASS_DEFAULT}")
    with t2:
        c1,c2 = st.columns(2)
        with c1:
            name=st.text_input("Name*"); mob=st.text_input("Mobile*"); email_s=st.text_input("Email*"); city=st.text_input("City*")
        with c2:
            state=st.text_input("State*"); pin=st.text_input("Pincode*"); comp=st.text_input("Company (Optional)"); pw_s=st.text_input("Password*",type="password")
        if st.button("Request Approval",use_container_width=True):
            if not all([name,mob,email_s,city,state,pin,pw_s]): st.error("Fill * fields")
            else:
                ok,msg=signup(name,mob,email_s.strip().lower(),city,state,pin,comp,pw_s)
                st.success(msg) if ok else st.error(msg)
else:
    u = st.session_state.user
    st.sidebar.write(f"👋 {u['name']}\n{u['email']}")
    if st.sidebar.button("Logout"): st.session_state.user=None; st.rerun()

    # ============ ADMIN PANEL ============
    if u["is_admin"]:
        st.title("👑 Admin Panel")

        # IN-APP UPLOAD
        st.subheader("📤 Upload Price List PDF (In-App)")
        up = st.file_uploader("Upload PDF",type=["pdf"])
        if up and st.button("Upload & Save"):
            path = os.path.join(PDF_FOLDER, up.name)
            open(path,"wb").write(up.getbuffer())
            st.success(f"Saved {up.name}"); st.cache_resource.clear(); st.rerun()

        # List & Delete Files
        all_pdfs = get_pdfs()
        st.write(f"**Total Files:** {len(all_pdfs)}")
        cols = st.columns(4)
        for i,fp in enumerate(all_pdfs):
            with cols[i%4]:
                st.text(os.path.basename(fp))
                if st.button(f"🗑️ Delete",key=f"del_file_{i}"):
                    os.remove(fp); st.cache_resource.clear(); st.rerun()

        st.divider()
        # Manage Users
        conn=sqlite3.connect(DB_PATH); users=conn.execute("SELECT * FROM users").fetchall(); conn.close()
        pending = [x for x in users if x[8]=="pending"]
        if pending: st.error(f"🔔 {len(pending)} Pending Approval")
        all_pdf_names = [os.path.basename(f) for f in all_pdfs]

        for row in users:
            if row[0]==ADMIN_EMAIL: continue
            email_u,name_u,mob_u,city_u,state_u,pin_u,comp_u,_,status_u,allowed_u,_ = row
            with st.expander(f"{name_u} | {email_u} | {mob_u} | {status_u}"):
                st.write(f"City: {city_u}, {state_u}-{pin_u} | Company: {comp_u} | Allowed: {allowed_u}")
                sel=[]
                c = st.columns(3)
                exist = allowed_u.split(",") if allowed_u else []
                for idx,pdfn in enumerate(all_pdf_names):
                    with c[idx%3]:
                        if st.checkbox(pdfn,value=pdfn in exist,key=f"{email_u}_{pdfn}"):
                            sel.append(pdfn)
                b1,b2,b3,b4,b5 = st.columns(5)
                if b1.button("✅ Approve",key=f"ap_{email_u}"):
                    conn=sqlite3.connect(DB_PATH); conn.execute("UPDATE users SET status='approved', allowed_files=? WHERE email=?",(",".join(sel),email_u)); conn.commit(); conn.close(); st.rerun()
                if b2.button("🚫 Block",key=f"bl_{email_u}"):
                    conn=sqlite3.connect(DB_PATH); conn.execute("UPDATE users SET status='blocked' WHERE email=?",(email_u,)); conn.commit(); conn.close(); st.rerun()
                if b3.button("✅ Unblock",key=f"ubl_{email_u}"):
                    conn=sqlite3.connect(DB_PATH); conn.execute("UPDATE users SET status='approved' WHERE email=?",(email_u,)); conn.commit(); conn.close(); st.rerun()
                if b4.button("❌ Reject",key=f"rj_{email_u}"):
                    conn=sqlite3.connect(DB_PATH); conn.execute("UPDATE users SET status='rejected' WHERE email=?",(email_u,)); conn.commit(); conn.close(); st.rerun()
                if b5.button("🗑️ Delete User",key=f"du_{email_u}"):
                    conn=sqlite3.connect(DB_PATH); conn.execute("DELETE FROM users WHERE email=?",(email_u,)); conn.commit(); conn.close(); st.rerun()
        st.divider()

    # ============ SEARCH (Both Admin & Customer) ============
    if not u["is_admin"]:
        st.title(f"Welcome {u['name']}")
        if not u["allowed_files"]: st.warning("No file access. Contact 9840830500"); st.stop()
        st.info(f"You can search in: {', '.join(u['allowed_files'])}")
        allowed = u["allowed_files"]
    else:
        st.subheader("🔍 Test Customer Search (AI Image+Text)")
        allowed = None

    catalog = load_catalog()
    q = st.text_input("🔍 Search (e.g. counter top basin, white round basin, parryware faucet)","")
    if q:
        ql = q.lower()
        # AI synonym expansion
        expanded = [ql]
        if "counter" in ql: expanded += ["counter top","table top","above counter","countertop"]

        res=[]
        for item in catalog:
            if allowed and item["file"] not in allowed: continue
            tl = item["text"].lower()
            score = sum(1 for term in expanded if term in tl) + sum(1 for w in ql.split() if len(w)>2 and w in tl)
            if score>0: res.append((score,item))
        res = sorted(res,key=lambda x:x[0],reverse=True)[:30]
        if not res: st.warning("No results. Try 'table top basin'")
        else:
            st.success(f"Found {len(res)} results (Image+Text AI matched)")
            for score,it in res:
                with st.container(border=True):
                    c1,c2 = st.columns([1,2])
                    with c1:
                        if it["images"]: st.image(it["images"][0],caption=f"{it['file']} P{it['page']}",use_container_width=True)
                        else: st.caption("No image")
                    with c2:
                        st.write(f"**{it['file']}** | Page {it['page']} | Match: {score}")
                        st.text(it["text"][:700])
