import streamlit as st
import fitz, base64, io
from github import Github
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from PIL import Image

st.set_page_config(page_title="Bathroom AI - Final 8", layout="wide")

# === CONFIG — FILL IN SECRETS ===
# Go to Streamlit Cloud -> Manage App -> Secrets -> Paste this:
# GITHUB_TOKEN = "ghp_xxxx"
# GITHUB_REPO = "yourusername/bathroom-ai"
# GOOGLE_SHEET_ID = "your_sheet_id"
# GOOGLE_SERVICE_ACCOUNT = {...json content... }

GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
GITHUB_REPO_NAME = st.secrets["GITHUB_REPO"]
GOOGLE_SHEET_ID = st.secrets["GOOGLE_SHEET_ID"]

# GitHub init
g = Github(GITHUB_TOKEN)
repo = g.get_repo(GITHUB_REPO_NAME)

# Google Sheets init
scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
creds_dict = dict(st.secrets["GOOGLE_SERVICE_ACCOUNT"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet_file = client.open_by_key(GOOGLE_SHEET_ID)
sheet_b = sheet_file.worksheet("SheetB_Approval")
sheet_c = sheet_file.worksheet("SheetC_Customers")
sheet_d = sheet_file.worksheet("SheetD_Index")

# === SESSION FOR SIGNUP ===
if "customer_verified" not in st.session_state:
    st.session_state.customer_verified = False

# === 8. CUSTOMER SIGNUP ===
if not st.session_state.customer_verified:
    st.title("Customer Signup Required")
    with st.form("signup"):
        name = st.text_input("Name*")
        contact = st.text_input("Contact No*")
        mail = st.text_input("Mail ID*")
        city = st.text_input("City*")
        pincode = st.text_input("Pincode*")
        company = st.text_input("Company Name (Optional)")
        submit = st.form_submit_button("Submit & Continue")
        if submit:
            if not all([name, contact, mail, city, pincode]):
                st.error("Fill all mandatory fields")
            else:
                sheet_c.append_row([name, contact, mail, city, pincode, company])
                st.session_state.customer_verified = True
                st.session_state.customer_mail = mail
                st.rerun()
    st.stop()

# === MAIN APP AFTER SIGNUP ===
st.title("Bathroom Product Search - 8 Features Locked")

# 7. Brand Wise Search
col1, col2, col3 = st.columns([1,3,1])
with col1:
    brand = st.selectbox("Brand", ["All Brands", "Fantini", "Gessi", "Hansgrohe"])
with col2:
    query = st.text_input("Search", placeholder="200mm Round shower")
with col3:
    st.write(" ")
    search_btn = st.button("Search")

# 6. Image Search
uploaded_image = st.file_uploader("Image Search - Upload shower image", type=["jpg","png"])

# === SEARCH LOGIC ===
def is_approved(filename):
    rows = sheet_b.get_all_records()
    for r in rows:
        if r['FileName']==filename and str(r['Approved']).upper()=="TRUE":
            return True
    return False

def search_pdfs(q, brand_filter):
    rows = sheet_d.get_all_records()
    results=[]
    for r in rows:
        if brand_filter!="All Brands" and r['Brand']!=brand_filter:
            continue
        if not is_approved(r['FileName']):
            continue
        if q.lower() in str(r['TextContent']).lower() or q.lower() in str(r['FileName']).lower():
            results.append(r)
    return results

if search_btn or uploaded_image:
    if uploaded_image:
        # Simple image search - use filename as query for now
        q = uploaded_image.name.split('.')[0]
        st.info(f"Image search for: {q}")
    else:
        q = query

    results = search_pdfs(q, brand)

    # 4. Pagination - 20 per page
    if "page_num" not in st.session_state:
        st.session_state.page_num = 0

    total = len(results)
    per_page = 20
    pages = total // per_page + (1 if total % per_page else 0)

    start = st.session_state.page_num * per_page
    end = start + per_page
    page_results = results[start:end]

    st.write(f"Found {total} results")

    for r in page_results:
        with st.container(border=True):
            st.write(f"**{r['Brand']}** - {r['FileName']} - Page {r['PageNo']}")
            # 5. Page Display - ONLY original image + Download
            try:
                file_content = repo.get_contents(f"pdfs/{r['FileName']}")
                pdf_bytes = base64.b64decode(file_content.content)
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                page = doc.load_page(int(r['PageNo']))
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")
                st.image(img_bytes, use_column_width=True)
                st.download_button("Download Original Page", data=img_bytes, file_name=f"page_{r['PageNo']}.png", mime="image/png", key=f"{r['FileName']}_{r['PageNo']}")
            except Exception as e:
                st.error(f"Could not load page: {e}")

    col_prev, col_next = st.columns(2)
    with col_prev:
        if st.button("Prev") and st.session_state.page_num>0:
            st.session_state.page_num-=1
            st.rerun()
    with col_next:
        if st.button("Next") and st.session_state.page_num < pages-1:
            st.session_state.page_num+=1
            st.rerun()

# === ADMIN: UPLOAD TO GITHUB — PERMANENT ===
with st.expander("Admin - Upload PDFs to GitHub (Permanent)"):
    up_brand = st.selectbox("Brand for upload", ["Fantini", "Gessi", "Hansgrohe"], key="up_brand")
    up_files = st.file_uploader("Upload PDFs", type=["pdf"], accept_multiple_files=True)
    if st.button("Upload to GitHub - Permanent Commit"):
        for f in up_files:
            try:
                content = f.read()
                path = f"pdfs/{up_brand}_{f.name}"
                repo.create_file(path, f"Add {f.name}", content)
                sheet_b.append_row([up_brand, f"{up_brand}_{f.name}", "FALSE"])
                st.success(f"Uploaded {f.name} - Waiting for approval in SheetB")
            except Exception as e:
                st.error(f"{f.name} failed: {e}")
