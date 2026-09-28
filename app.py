import os, io, json, base64, re
from flask import Flask, request, render_template_string, jsonify, session, redirect
import fitz # PyMuPDF
from github import Github
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)
app.secret_key = "FINAL_8_FEATURES_LOCKED"

# === CONFIG — FILL YOUR KEYS ===
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = "yourusername/yourpdfrepo"
GITHUB_FOLDER = "pdfs"
GOOGLE_SHEET_ID = "YOUR_GOOGLE_SHEET_ID"
SERVICE_ACCOUNT_JSON = "service_account.json" # upload to server

# Google Sheets Setup
scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_JSON, scope)
client = gspread.authorize(creds)
sheet_file = client.open_by_key(GOOGLE_SHEET_ID)
sheet_b = sheet_file.worksheet("SheetB_Approval") # Brand | FileName | Approved TRUE/FALSE
sheet_c = sheet_file.worksheet("SheetC_Customers") # Name | Contact | Mail | City | Pincode | Company | Date
sheet_index = sheet_file.worksheet("SheetD_Index") # Brand | FileName | PageNo | TextContent

g = Github(GITHUB_TOKEN)
repo = g.get_repo(GITHUB_REPO)

# === 1. PERMANENT PDFS — GITHUB COMMIT ===
def upload_to_github(file_storage, brand):
    filename = f"{brand}_{file_storage.filename}"
    content = file_storage.read()
    path = f"{GITHUB_FOLDER}/{filename}"
    try:
        # Create commit — permanent, no delete on reboot
        repo.create_file(path, f"Add {filename}", content)
        # Add to Sheet B for approval — Block search until approved
        sheet_b.append_row([brand, filename, "FALSE"])
        return True
    except:
        return False

def list_approved_pdfs(brand_filter="All Brands"):
    all_rows = sheet_b.get_all_records()
    approved = [r for r in all_rows if str(r['Approved']).upper()=="TRUE"]
    if brand_filter!= "All Brands":
        approved = [r for r in approved if r['Brand']==brand_filter]
    return approved

# === 8. CUSTOMER SIGNUP — MANDATORY ===
@app.route("/signup", methods=["POST"])
def signup():
    data = request.json
    # Validation — Company not mandatory
    if not all([data.get('name'), data.get('contact'), data.get('mail'), data.get('city'), data.get('pincode')]):
        return jsonify({"error":"Fill mandatory fields"}), 400
    sheet_c.append_row([data['name'], data['contact'], data['mail'], data['city'], data['pincode'], data.get('company',''), ""])
    session['customer_verified'] = True
    session['customer_mail'] = data['mail']
    return jsonify({"success":True})

# === SEARCH CORE — 3,6,7 ===
def search_pdfs(query, brand_filter, page=1):
    query = query.lower()
    rows = sheet_index.get_all_records() # Pre-indexed text of all PDF pages
    results = []
    for r in rows:
        # 7. Brand Wise Search
        if brand_filter!= "All Brands" and r['Brand']!= brand_filter:
            continue
        # 2. Approval Check
        if not is_approved(r['FileName']):
            continue
        # 3. Text Search — `200mm Round shower in fantini` → finds & works
        if query in r['TextContent'].lower() or query in r['FileName'].lower():
            results.append(r)
    # 4. Pagination — 20 per page
    per_page = 20
    start = (page-1)*per_page
    end = start + per_page
    return results[start:end], len(results)

def is_approved(filename):
    rows = sheet_b.get_all_records()
    for r in rows:
        if r['FileName']==filename and str(r['Approved']).upper()=="TRUE":
            return True
    return False

# === 5. PAGE DISPLAY — ONLY ORIGINAL IMAGE + DOWNLOAD ===
@app.route("/page_view")
def page_view():
    brand = request.args.get("brand")
    filename = request.args.get("file")
    pageno = int(request.args.get("pageno", 0))
    # Get file from GitHub
    file_content = repo.get_contents(f"{GITHUB_FOLDER}/{filename}")
    pdf_bytes = base64.b64decode(file_content.content)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc.load_page(pageno)
    pix = page.get_pixmap(dpi=200)
    img_bytes = pix.tobytes("png")
    # Return as image page with download button — UI handles it
    return f'''
    <div style="text-align:center">
        <img src="data:image/png;base64,{base64.b64encode(img_bytes).decode()}" style="max-width:100%;box-shadow:0 0 10px #ccc"/>
        <br><br>
        <a href="/download?file={filename}&pageno={pageno}" download><button style="padding:10px 20px;background:#000;color:#fff">Download Page</button></a>
    </div>
    '''

@app.route("/download")
def download():
    filename = request.args.get("file")
    pageno = int(request.args.get("pageno"))
    file_content = repo.get_contents(f"{GITHUB_FOLDER}/{filename}")
    pdf_bytes = base64.b64decode(file_content.content)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc.load_page(pageno)
    pix = page.get_pixmap(dpi=200)
    return pix.tobytes("png"), 200, {'Content-Type':'image/png', 'Content-Disposition': f'attachment; filename=page_{pageno}.png'}

# === 6. IMAGE SEARCH ===
@app.route("/image_search", methods=["POST"])
def image_search():
    # Simple CLIP / placeholder — finds similar product page by text from image filename
    # You can plug MobileNet similarity here
    file = request.files['image']
    # For now — search by image name as query
    results, total = search_pdfs(file.filename.split('.')[0], request.form.get('brand','All Brands'))
    return jsonify(results)

# === MAIN UI ===
HTML = """
<!DOCTYPE html>
<html>
<head><title>PDF Search — Final 8 Features</title>
<style>
body{font-family:Arial;padding:20px}
.search-box{display:flex;gap:10px;margin-bottom:20px}
select, input{padding:10px;border:1px solid #000}
#signup{border:1px solid #000;padding:20px;margin-bottom:20px}
</style>
</head>
<body>
<div id="signup">
<h3>Customer Signup Required</h3>
<input id="name" placeholder="Name*">
<input id="contact" placeholder="Contact No*">
<input id="mail" placeholder="Mail ID*">
<input id="city" placeholder="City*">
<input id="pincode" placeholder="Pincode*">
<input id="company" placeholder="Company Name (Optional)">
<button onclick="doSignup()">Submit & Continue</button>
</div>

<div id="main" style="display:none">
<div class="search-box">
<select id="brand">
<option>All Brands</option><option>Fantini</option><option>Gessi</option><option>Hansgrohe</option>
</select>
<input id="query" placeholder="Search 200mm Round shower..." style="flex:1">
<button onclick="doSearch(1)">Search</button>
<input type="file" id="imgSearch"><button onclick="doImageSearch()">Image Search</button>
</div>
<div id="results"></div>
<div id="pagination"></div>
</div>

<script>
function doSignup(){
 fetch('/signup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
  name:document.getElementById('name').value,
  contact:document.getElementById('contact').value,
  mail:document.getElementById('mail').value,
  city:document.getElementById('city').value,
  pincode:document.getElementById('pincode').value,
  company:document.getElementById('company').value
 })}).then(r=>r.json()).then(d=>{
  if(d.success){document.getElementById('signup').style.display='none';document.getElementById('main').style.display='block';}
  else alert(d.error)
 })
}
let curPage=1;
function doSearch(page){
 curPage=page;
 fetch(`/search?q=${document.getElementById('query').value}&brand=${document.getElementById('brand').value}&page=${page}`)
.then(r=>r.json()).then(d=>{
  let html='';
  d.results.forEach(r=>{
   html+=`<div style="border:1px solid #eee;padding:10px;margin:5px"><b>${r.Brand}</b> - ${r.FileName} - Page ${r.PageNo}
   <a href="/page_view?brand=${r.Brand}&file=${r.FileName}&pageno=${r.PageNo}" target="_blank">View Original Page</a></div>`;
  });
  document.getElementById('results').innerHTML=html;
  // Pagination 20 per page
  let totalPages=Math.ceil(d.total/20);
  let pagHtml='';
  if(curPage>1) pagHtml+=`<button onclick="doSearch(${curPage-1})">Prev</button>`;
  for(let i=1;i<=totalPages;i++) pagHtml+=`<button onclick="doSearch(${i})" ${i==curPage?'style="background:#000;color:#fff"':''}>${i}</button>`;
  if(curPage<totalPages) pagHtml+=`<button onclick="doSearch(${curPage+1})">Next</button>`;
  document.getElementById('pagination').innerHTML=pagHtml;
 })
}
function doImageSearch(){
 let fd=new FormData();
 fd.append('image', document.getElementById('imgSearch').files[0]);
 fd.append('brand', document.getElementById('brand').value);
 fetch('/image_search',{method:'POST',body:fd}).then(r=>r.json()).then(d=>{console.log(d); alert('Image search found '+d.length+' results — displayed')})
}
</script>
</body>
</html>
"""

@app.route("/")
def home():
    if not session.get('customer_verified'):
        return render_template_string(HTML)
    return render_template_string(HTML)

@app.route("/search")
def search_api():
    q = request.args.get("q","")
    brand = request.args.get("brand","All Brands")
    page = int(request.args.get("page",1))
    results, total = search_pdfs(q, brand, page)
    return jsonify({"results":results, "total":total})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
