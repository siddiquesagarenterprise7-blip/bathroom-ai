if q:
    words=[w for w in re.findall(r'\b\w+\b', q.lower()) if len(w)>=2]
    if not words: st.stop()

    # FIRST 3 WORDS = PRIMARY - MUST HAVE
    primary_words = words[:3] # If you type 1 word, 1 primary. 2 words, 2 primary. 3+, first 3 primary.
    filter_words = words[3:] # 4th word onwards are filters

    # STEP 1: All primary words MUST be present
    primary_match=[]
    for x in index:
        search_text = (x["file"] + " " + x["low"]).lower()
        if all(p in search_text for p in primary_words):
            # Score by position of first primary word (early = better)
            pos = search_text.find(primary_words[0]) if primary_words else 0
            primary_match.append((pos, x))

    # Remove Index pages
    non_index=[(pos,x) for pos,x in primary_match if "SALES CONDITIONS" not in x["text"]]

    # STEP 2: Filter words scoring + price page first
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
                st.success(f"✅ Primary '{' + '.join(primary_words).upper()}' MUST - Found {len(perfect)} pages with ALL '{q}' - Price first")
            else:
                results_scored=scored
                st.success(f"✅ Primary '{' + '.join(primary_words).upper()}' MUST - Found {len(scored)} pages - Best has {scored[0][0]}/{len(filter_words)} filters '{', '.join(filter_words)}'")
        else:
            results_scored=scored
            st.success(f"✅ Primary '{' + '.join(primary_words).upper()}' MUST - Found {len(scored)} pages")

        for filter_count, has_price, neg_pos, it in results_scored[:15]:
            with st.container(border=True):
                if filter_words:
                    st.markdown(f"**{it['file']} - Page {it['page']}** {'💰 PRICE' if has_price else ''} - Primary {'+'.join(primary_words)} ✅ + Filters {filter_count}/{len(filter_words)}")
                else:
                    st.markdown(f"**{it['file']} - Page {it['page']}** {'💰 PRICE' if has_price else ''} - Primary {'+'.join(primary_words)} ✅")
                c1,c2=st.columns([2,3])
                with c1:
                    st.code(it["text"][:1800])
                    if st.button(f"👁️ View Page {it['page']}", key=f"p3_{it['file']}_{it['page']}_{filter_count}_{id(it)}", type="primary" if has_price else "secondary"):
                        st.session_state.view_file=it["path"]; st.session_state.view_page=it["page"]; st.rerun()
                with c2:
                    try: doc=fitz.open(it["path"]); pix=doc[it["pno"]].get_pixmap(dpi=180); p=f"/tmp/p3_{it['page']}_{id(it)}.png"; pix.save(p); st.image(p, use_container_width=True); doc.close()
                    except: pass
    else:
        # If no page has all 3 primary, try with first 2, then first 1
        fallback=[]
        for n in [2,1]:
            if len(primary_words) > n:
                try_primary = primary_words[:n]
                for x in index:
                    search_text = (x["file"] + " " + x["low"]).lower()
                    if all(p in search_text for p in try_primary) and "SALES CONDITIONS" not in x["text"]:
                        fallback.append(x)
                if fallback:
                    st.warning(f"No page has ALL 3 Primary '{' + '.join(primary_words)}' - Showing {len(fallback)} pages with First {n} Primary '{' + '.join(try_primary)}' - Try fewer words")
                    for it in fallback[:15]:
                        with st.container(border=True):
                            st.markdown(f"**{it['file']} - Page {it['page']}** - Fallback {n} words")
                            c1,c2=st.columns([2,3])
                            with c1:
                                st.code(it["text"][:1800])
                                if st.button(f"👁️ View", key=f"fb_{it['file']}_{it['page']}_{id(it)}"):
                                    st.session_state.view_file=it["path"]; st.session_state.view_page=it["page"]; st.rerun()
                            with c2:
                                try: doc=fitz.open(it["path"]); pix=doc[it["pno"]].get_pixmap(dpi=180); p=f"/tmp/fb_{it['page']}_{id(it)}.png"; pix.save(p); st.image(p, use_container_width=True); doc.close()
                                except: pass
                    break
        if not fallback:
            st.warning(f"No page found with Primary '{' + '.join(primary_words)}'")
