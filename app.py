import streamlit as st
import fitz, base64, json
from github import Github

st.set_page_config(page_title="Bathroom AI - Final 8", layout="wide")

# === CONFIG — ONLY 2 VALUES NEEDED ===
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
GITHUB_REPO_NAME = st.secrets["GITHUB_REPO"]

g = Github(GITHUB_TOKEN)
repo = g.get_repo(GITHUB_REPO_NAME)

# === HELPER: GITHUB JSON STORAGE (Instead of Google Sheets) ===
def get_json_file(path, default):
    try:
        file = repo.get_contents(path)
        content = base64.b64decode(file.content).decode()
        return json.loads(content), file.sha
    except:
        return default, None

def save_json_file(path, data, sha, message):
    content = json.dumps(data, indent=2)
    if sha:
        repo.update_file(path, message, content, sha)
    else:
        try:
            repo.create_file(path, message, content)
        except:
            # if already exists, get sha again
            _, existing_sha = get_json_file(path, {})
            if existing_sha:
                repo.update_file(path, message, content, existing_sha)

# === CUSTOMER SIGNUP — Stored in GitHub ===
if "customer_verified" not in st.session_state:
    st.session_state.customer_verified = False

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
                customers, sha = get_json_file("data/customers.json", [])
                customers.append({"name":name,"contact":contact,"mail":mail,"city":city,"pincode":pincode,"company":company})
                save_json_file("data/customers.json", customers, sha, f"New customer {name}")
                st.session_state.customer_verified = True
                st.success("Signup saved permanently to GitHub!")
                st.rerun()
    st.stop()

# === MAIN APP ===
st.title("Bathroom Product Search - 8 Features Locked")

col1, col2 = st.columns([1,3])
with col1:
    brand = st.selectbox("Brand", ["All Brands", "Fantini", "Gessi", "Hansgrohe"])
with col2:
    query = st.text_input("Search", placeholder="200mm Round shower in fantini")

search_btn = st.button("Search")
uploaded_image = st.file_uploader("Image Search", type=["jpg","png"])

# === APPROVAL LOGIC FROM GITHUB ===
approvals, _ = get_json_file("data/approvals.json", []) # [{"brand":"Fantini","file":"Fantini_x.pdf","approved":True}]

def is_approved(filename):
    for a in approvals:
        if a["file"]==filename and a["approved"]:
            return True
    return False

# === SEARCH (Simplified — lists all PDFs for now) ===
if search_btn or query:
    try:
        contents = repo.get_contents("pdfs")
        pdf_files = [c.name for c in contents if c.name.endswith(".pdf")]
        if brand!= "All Brands":
            pdf_files = [f for f in pdf_files if f.startswith(brand)]
        if query:
            pdf_files = [f for f in pdf_files if query.lower() in f.lower()]

        # Filter only approved
        pdf_files = [f for f in pdf_files if is_approved(f)]

        st.write(f"Found {len(pdf_files)} results")

        # 4. Pagination 20 per page
        per_page = 20
        if "page_num" not in st.session_state:
            st.session_state.page_num = 0

        start = st.session_state.page_num * per_page
        end = start + per_page

        for filename in pdf_files[start:end]:
            with st.container(border=True):
                st.write(f"**{filename}**")
                file_content = repo.get_contents(f"pdfs/{filename}")
                pdf_bytes = base64.b64decode(file_content.content)
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                # Show first page as original image
                page = doc.load_page(0)
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                st.image(img_bytes, use_container_width=True)
                st.download_button(f"Download {filename} - Page 1", data=img_bytes, file_name=f"{filename}_page1.png", mime="image/png", key=filename)

    except Exception as e:
        st.error(f"No pdfs folder yet or {e}")

# === ADMIN UPLOAD — PERMANENT GITHUB COMMIT ===
with st.expander("Admin - Upload PDFs to GitHub (Permanent)"):
    up_brand = st.selectbox("Brand for upload", ["Fantini", "Gessi", "Hansgrohe"], key="up_brand")
    up_files = st.file_uploader("Upload PDFs", type=["pdf"], accept_multiple_files=True)
    if st.button("Upload to GitHub - Permanent"):
        for f in up_files:
            try:
                content = f.read()
                path = f"pdfs/{up_brand}_{f.name}"
                repo.create_file(path, f"Add {f.name}", content)
                # Add to approvals.json as FALSE
                approvals_data, sha = get_json_file("data/approvals.json", [])
                approvals_data.append({"brand":up_brand,"file":f"{up_brand}_{f.name}","approved":False})
                save_json_file("data/approvals.json", approvals_data, sha, f"Approval for {f.name}")
                st.success(f"Uploaded {f.name} — Now approve in data/approvals.json")
            except Exception as e:
                st.error(f"{f.name} failed: {e}")

with st.expander("Admin - Approve Files"):
    approvals_data, sha = get_json_file("data/approvals.json", [])
    for i, a in enumerate(approvals_data):
        col_a, col_b = st.columns([3,1])
        with col_a:
            st.write(f"{a['brand']} - {a['file']} - Approved: {a['approved']}")
        with col_b:
            if st.button(f"Approve", key=f"app_{i}"):
                approvals_data[i]["approved"]=True
                save_json_file("data/approvals.json", approvals_data, sha, f"Approved {a['file']}")
                st.rerun()
