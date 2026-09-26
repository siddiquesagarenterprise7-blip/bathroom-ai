import streamlit as st, os, glob, hashlib, sqlite3, base64, re
from datetime import datetime
import fitz
st.set_page_config(page_title="Product and price finder", layout="wide")

ADMIN_EMAIL = st.secrets.get("ADMIN_EMAIL", "siddique.sagarenterprise7@gmail.com")
ADMIN_PASS = st.secrets.get("ADMIN_PASS", "SagarEnt@2026!Secure")
PDF_FOLDER="files"; DB_PATH="users.db"
os.makedirs(PDF_FOLDER, exist_ok=True)

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()
def get_pdfs(): return sorted(glob.glob(os.path.join(PDF_FOLDER, "*.pdf")))
def init_db():
    conn=sqlite3.connect(DB_PATH)
    conn.execute('CREATE TABLE IF NOT EXISTS users (email TEXT PRIMARY KEY, name TEXT, mobile TEXT, company TEXT, address TEXT, city TEXT, pincode TEXT, password TEXT, status TEXT, created_at TEXT)')
    try:
        cols=[r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        for c in ["company","address","city","pincode"]:
            if c not in cols: conn.execute(f"ALTER TABLE users ADD COLUMN {c} TEXT")
    except: pass
    conn.execute("INSERT OR REPLACE INTO users VALUES (?,?,?,?,?,?,?,?,?,?)",(ADMIN_EMAIL.lower(),"Admin","9840830500","","","","",hash_pw(ADMIN_PASS),"approved",datetime.now().strftime("%Y-%m-%d")))
    conn.commit(); conn.close()
init_db()

if "user" not in st.session_state: st.session_state.user=None
if "view_file" not in st.session_state: st.session_state.view_file=None
if "view_page" not in st.session_state: st.session_state.view_page=None
if "page_num" not in st.session_state: st.session_state.page_num=0

if not st.session_state.user:
    st.title("🔍 Product and price finder - Sagar Enterprise")
    t1,t2=st.tabs(["🔐 Login","📝 Sign-Up"])
    with t1:
        e=st.text_input("Email", key="e1"); p=st.text_input("Password", type="password", key="p1")
        if st.button("Login", type="primary", use_container_width=True):
            conn=sqlite3.connect(DB_PATH); r=conn.execute("SELECT email,name,mobile,status FROM users WHERE email=? AND password=?",(e.lower().strip(),hash_pw(p))).fetchone(); conn.close()
            if not r: st.error("Wrong")
            elif r[3]!="approved" and r[0]!=ADMIN_EMAIL.lower(): st.warning("Pending approval")
            else: st.session_state.user={"email":r[0],"name":r[1],"mobile":r[2],"is_admin":r[0]==ADMIN_EMAIL.lower()}; st.rerun()
    with t2:
        c1,c2=st.columns(2)
        with c1: name=st.text_input("Full Name *"); mobile=st.text_input("Mobile *"); email=st.text_input("Email *"); password=st.text_input("Password *", type="password")
        with c2: company=st.text_input("Company *"); city=st.text_input("City *"); pincode=st.text_input("Pincode *"); address=st.text_area("Address *")
        if st.button("Sign Up", type="primary", use_container_width=True):
            if not all([name,mobile,email,password,company,city,pincode,address]): st.error("Fill all *")
            else:
                try: conn=sqlite3.connect(DB_PATH); conn.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?)",(email.lower(),name,mobile,company,address,city,pincode,hash_pw(password),"pending",datetime.now().strftime("%Y-%m-%d %H:%M"))); conn.commit(); conn.close(); st.success("Registered!")
                except: st.error("Email exists")
    st.stop()

user=st.session_state.user; pdfs=get_pdfs()
st.sidebar.title("📁 Sagar Enterprise"); st.sidebar.write(f"Hi, {user.get('name')}")
if user.get('is_admin'): st.sidebar.success("👑 Admin")
if st.sidebar.button("🚪 Logout"): st.session_state.user=None; st.rerun()
st.sidebar.divider(); st.sidebar.subheader(f"📚 Price Lists ({len(pdfs)})")
FILES_PER_PAGE=10; total_pages=(len(pdfs)+FILES_PER_PAGE-1)//FILES_PER_PAGE if pdfs else 1
start=st.session_state.page_num*FILES_PER_PAGE; end=start+FILES_PER_PAGE
for path in pdfs[start:end]:
    fname=os.path.basename(path)
    with st.sidebar.container(border=True):
        st.sidebar.write(f"📄 {fname[:35]}")
        c1,c2=st.sidebar.columns(2)
        if c1.button("👁️ View", key=f"v_{path}", use_container_width=True): st.session_state.view_file=path; st.session_state.view_page=None; st.rerun()
        with open(path,"rb") as f: c2.download_button("⬇️", f, file_name=fname, mime="application/pdf", key=f"d_{path}", use_container_width=True)
c1,c2=st.sidebar.columns(2)
if c1.button("⬅️ Prev") and st.session_state.page_num>0: st.session_state.page_num-=1; st.rerun()
if c2.button("Next ➡️") and st.session_state.page_num < total_pages-1: st.session_state.page_num+=1; st.rerun()
if user.get('is_admin'):
    up=st.sidebar.file_uploader("📤 Add PDF", type=["pdf"], accept_multiple_files=True)
    if up and st.sidebar.button("💾 Save"):
        for f in up: open(os.path.join(PDF_FOLDER,f.name),"wb").write(f.getbuffer())
        st.rerun()

st.title("🔍 Product and price finder")
if st.session_state.view_file and os.path.exists(st.session_state.view_file):
    st.info(f"Viewing: {os.path.basename(st.session_state.view_file)}" + (f" - Page {st.session_state.view_page}" if st.session_state.view_page else ""))
    if st.button("❌ Close"): st.session_state.view_file=None; st.session_state.view_page=None; st.rerun()
    try:
        doc=fitz.open(st.session_state.view_file)
        if st.session_state.view_page:
            pno=st.session_state.view_page-1
            if 0 <= pno < len(doc): pix=doc[pno].get_pixmap(dpi=250); img=f"/tmp/{pno}.png"; pix.save(img); st.image(img, caption=f"Price Page {st.session_state.view_page}", use_container_width=True)
        with open(st.session_state.view_file,"rb") as f: b64=base64.b64encode(f.read()).decode()
        st.markdown(f'<iframe src="data:application/pdf;base64,{b64}#page={st.session_state.view_page or 1}" width="100%" height="700"></iframe>', unsafe_allow_html=True)
        doc.close()
    except: pass

st.subheader("🔍 Search - First 3 Words Primary (Brand Wise)")
q=st.text_input("Search", value="antoniolupi freestanding basins", placeholder="e.g. catalano zero nero satin wc")

@st.cache_data
def build_idx():
    idx=[]
    for p in get_pdfs():
        try:
            doc=fitz.open(p)
            for i in range(len(doc)):
                t=doc[i].get_text("text") or ""
                if len(t.strip())>10: idx.append({"file":os.path.basename(p),"page":i+1,"text":t,"low":t.lower(),"path":p,"pno":i})
            doc.close()
        except: pass
    return idx

index=build_idx()

# ===== 3 WORDS PRIMARY SEARCH =====
if q:
    words=[w for w in re.findall(r'\b\w+\b', q.lower()) if len(w)>=2]
    if words:
        primary_words = words[:3]
        filter_words = words[3:]

        primary_match=[]
        for x in index:
            search_text = (x["file"] + " " + x["low"]).lower()
            if all(p in search_text for p in primary_words):
                pos = search_text.find(primary_words[0]) if primary_words else 0
                primary_match.append((pos, x))

        non_index=[(pos,x) for pos,x in primary_match if "SALES CONDITIONS" not in x["text"]]

        scored=[]
        for pos,x in non_index:
            search_text = (x["file"] + " " + x["low"]).lower()
            filter_count = sum(1 for w in filter_words if w in search_text) if filter_words else 0
            has_price = 1 if "₹" in x["text"] else 0
            scored.append((filter_count, has_price, -pos, x))

        scored.sort(reverse=True)

        if scored:
            if filter_words:
                perfect=[s for s in scored if s[0]==len(filter_words)]
                if perfect:
                    results_scored=perfect + [s for s in scored if s not in perfect]
                    st.success(f"✅ Primary '{' '.join(primary_words).upper()}' MUST - Found {len(perfect)} with ALL '{q}'")
                else:
                    results_scored=scored
                    st.success(f"✅ Primary '{' '.join(primary_words).upper()}' MUST - Found {len(scored)} - Best has {scored[0][0]}/{len(filter_words)} filters")
            else:
                results_scored=scored
                st.success(f"✅ Primary '{' '.join(primary_words).upper()}' MUST - Found {len(scored)} pages")

            for filter_count, has_price, neg_pos, it in results_scored[:15]:
                with st.container(border=True):
                    st.markdown(f"**{it['file']} - Page {it['page']}** {'💰 PRICE' if has_price else ''} - Primary {'+'.join(primary_words)}")
                    c1,c2=st.columns([2,3])
                    with c1:
                        st.code(it["text"][:1800])
                        if st.button(f"👁️ View Page {it['page']}", key=f"p3_{it['file']}_{it['page']}_{filter_count}_{id(it)}", type="primary" if has_price else "secondary"):
                            st.session_state.view_file=it["path"]; st.session_state.view_page=it["page"]; st.rerun()
                    with c2:
                        try: doc=fitz.open(it["path"]); pix=doc[it["pno"]].get_pixmap(dpi=180); p=f"/tmp/p3_{it['page']}_{id(it)}.png"; pix.save(p); st.image(p, use_container_width=True); doc.close()
                        except: pass
        else:
            st.warning(f"No page with Primary '{' '.join(primary_words)}' - Try: antonioluoi, catalano, freestanding")
