    with st.expander("📤 Upload Pricelists", expanded=True):
        ups=st.file_uploader("Choose PDFs", type=["pdf"], accept_multiple_files=True, key="uploader")
        if st.button("⬆️ Upload", key="upload_btn"):
            for f in ups:
                try:
                    safe=f.name.replace(" ","_")
                    fb=f.getvalue()
                    if len(fb)/(1024*1024)>90:
                        rel=get_or_create_release()
                        for a in rel.get_assets():
                            if a.name==safe: a.delete_asset()
                        rel.upload_asset_from_memory(io.BytesIO(fb), len(fb), safe, "application/pdf")
                    else:
                        path=f"pdfs/{safe}"
                        try:
                            ex=repo.get_contents(path)
                            repo.update_file(path, f"Update {safe}", fb, ex.sha)
                        except: repo.create_file(path, f"Add {safe}", fb)
                    acc,sha_acc=get_json_file("data/file_access.json", {})
                    acc[safe]=["all"]
                    save_json_file("data/file_access.json", acc, sha_acc, "default")
                    st.success(f"Uploaded {safe}")
                except Exception as e: st.error(str(e))
