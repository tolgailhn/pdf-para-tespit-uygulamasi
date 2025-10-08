 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/app.py b/app.py
index e16f00b0a4b439375775a374d12b56a6a92e089d..2832dfd458095e0a3740921e97c262b22fb1649e 100644
--- a/app.py
+++ b/app.py
@@ -1,310 +1,323 @@
-import streamlit as st
-import pdfplumber
-import pandas as pd
-import io
-import re
-from collections import defaultdict
-from decimal import Decimal, InvalidOperation
-
-# ---- Genel Ayar ----
-st.set_page_config(page_title="PDF & Satış Analiz Aracı", layout="wide")
-st.title("💸 PDF Para Birimi Tarayıcı & Satış Excel Analiz")
-
-# =========================================
-# ============  PDF ANALİZİ  ==============
-# =========================================
-
-CURRENCIES = ["EUR", "PLN", "GBP", "SEK"]
-
-def extract_text_from_pdf(file):
-    text = ""
-    with pdfplumber.open(file) as pdf:
-        for page in pdf.pages:
-            page_text = page.extract_text()
-            if page_text:
-                text += page_text + "\n"
-    return text
-
-def normalize_number_str(s: str) -> str:
-    """
-    '2,572.13' -> '2572.13'
-    '2.572,13' -> '2572.13'
-    '490.77'   -> '490.77'
-    '490,77'   -> '490.77'
-    """
-    s = s.strip()
-    # önce boşluk ve para birimi yazılarını ayıkla
-    s = re.sub(r"[^\d,.\-]", "", s)
-    if s.count(",") == 1 and s.count(".") >= 1:
-        # binlik . ve ondalık , varsay → noktaları sil, virgülü noktaya çevir
-        s = s.replace(".", "")
-        s = s.replace(",", ".")
-    elif s.count(",") == 1 and s.count(".") == 0:
-        # sadece virgül varsa → ondalık ayırıcıdır
-        s = s.replace(",", ".")
-    # şimdi sadece rakam . - kalsın
-    s = re.sub(r"[^0-9.\-]", "", s)
-    return s
-
-def to_decimal(val) -> Decimal:
-    if val is None:
-        return Decimal("0")
-    try:
-        return Decimal(str(val))
-    except InvalidOperation:
-        try:
-            return Decimal(normalize_number_str(str(val)))
-        except Exception:
-            return Decimal("0")
-
-def find_currency_amounts(text):
-    """
-    Genel tarama: 'EUR 490.77' gibi tüm eşleşmeleri yakalar.
-    """
-    results = []
-    for currency in CURRENCIES:
-        pattern = rf"{currency}\s?([0-9\.,]+)"
-        for m in re.findall(pattern, text):
-            num = normalize_number_str(m)
-            try:
-                amount = float(num)
-                results.append((currency, amount))
-            except:
-                continue
-    return results
-
-def extract_totals_only(text):
-    """
-    Sadece 'Total / Totale / Totaal' satırlarını hedefler ve (para birimi, tutar) döndürür.
-    Diller: EN (Total), IT (Totale), NL (Totaal), FR (Total), ES (Total).
-    """
-    totals = []
-    # başlık varyasyonları
-    total_words = r"(Total|TOTAL|Totale|TOTALE|Totaal|TOTAL|Total[e]?)"
-    pattern = rf"{total_words}\s+(EUR|GBP|PLN|SEK)\s+([0-9\.,]+)"
-    for word, cur, amt in re.findall(pattern, text):
-        num = normalize_number_str(amt)
-        try:
-            amount = float(num)
-            totals.append((cur, amount))
-        except:
-            continue
-
-    # Bazı belgelerde para birimi sağda olabilir: "EUR 490.77" aynı satırda Total ile
-    # yedek desen: 'Totale ... EUR 490.77'
-    pattern2 = rf"{total_words}.*?(EUR|GBP|PLN|SEK)\s+([0-9\.,]+)"
-    for word, cur, amt in re.findall(pattern2, text, flags=re.IGNORECASE):
-        num = normalize_number_str(amt)
-        try:
-            amount = float(num)
-            totals.append((cur, amount))
-        except:
-            continue
-
-    # Tekilleştir (aynı satır iki desenle yakalanırsa)
-    return list(set(totals))
-
-with st.expander("📄 PDF Analizi (EUR/PLN/GBP/SEK tespiti ve EUR'a çeviri)", expanded=True):
-    uploaded_pdfs = st.file_uploader(
-        "PDF dosyalarını yükleyin", type="pdf", accept_multiple_files=True, key="pdfs"
-    )
-
-    colA, colB, colC, colD = st.columns([1,1,2,2])
-    with colA:
-        convert = st.checkbox("💱 Sadece PLN/GBP/SEK'i EUR'a çevir", value=True, key="pdf_convert")
-    with colB:
-        show_negative = st.checkbox("➖ Negatifleri göster", value=False, key="pdf_neg")
-    with colC:
-        dedupe_in_file = st.checkbox("🔁 Aynı (para,tutar) tekrarlarını aynı dosyada tek say", value=True)
-    with colD:
-        totals_mode = st.checkbox("📌 Sadece 'Total/Totale/Totaal' satırını kullan (önerilir)", value=True)
-
-    eur_rates = {
-        "PLN": st.number_input("PLN → EUR kuru", min_value=0.0, value=0.22, key="pln_rate"),
-        "GBP": st.number_input("GBP → EUR kuru", min_value=0.0, value=1.17, key="gbp_rate"),
-        "SEK": st.number_input("SEK → EUR kuru", min_value=0.0, value=0.084, key="sek_rate")
-    }
-
-    pdf_rows = []
-
-    if uploaded_pdfs:
-        for file in uploaded_pdfs:
-            text = extract_text_from_pdf(file)
-
-            if totals_mode:
-                raw_results = extract_totals_only(text)
-                # eğer hiçbir 'Total' bulunamazsa genel taramaya fallback
-                if not raw_results:
-                    raw_results = find_currency_amounts(text)
-            else:
-                raw_results = find_currency_amounts(text)
-
-            # Aynı dosyada aynı (para,tutar) tekrarlarını tekilleştir (isteğe bağlı)
-            iterable = set(raw_results) if dedupe_in_file else raw_results
-
-            # Para birimi bazında toplam
-            sums = defaultdict(float)
-            for currency, amount in iterable:
-                if not show_negative and amount < 0:
-                    continue
-                sums[currency] += amount
-
-            # Sonuç satırları
-            for currency, total_amount in sums.items():
-                if currency == "EUR":
-                    eur_value = total_amount  # EUR'u çevirmeyiz
-                else:
-                    eur_value = round(total_amount * eur_rates.get(currency, 0), 2) if convert else total_amount
-
-                pdf_rows.append({
-                    "Dosya": file.name,
-                    "Para Birimi": currency,
-                    "Toplam Tutar": round(total_amount, 2),
-                    "EUR Karşılığı": round(eur_value, 2)
-                })
-
-        if pdf_rows:
-            pdf_df = pd.DataFrame(pdf_rows)
-            st.dataframe(pdf_df, use_container_width=True)
-
-            # 🔢 GENEL TOPLAM = "EUR Karşılığı" sütununun Decimal ile güvenli toplamı
-            eur_series = pdf_df["EUR Karşılığı"].apply(lambda x: to_decimal(x))
-            total_eur = sum(eur_series, Decimal("0"))
-            st.success(f"💶 PDF'lerden Genel EUR Toplamı: {total_eur.quantize(Decimal('0.01'))} EUR")
-
-            # Excel indir
-            excel_buff = io.BytesIO()
-            pdf_df.to_excel(excel_buff, index=False)
-            st.download_button("📥 PDF Sonuçlarını Excel olarak indir", data=excel_buff.getvalue(), file_name="pdf_rapor.xlsx")
-
-            # TXT indir
-            txt = pdf_df.to_csv(sep="\t", index=False)
-            st.download_button("📄 PDF Sonuçlarını TXT olarak indir", data=txt, file_name="pdf_rapor.txt")
-        else:
-            st.info("PDF'lerde geçerli 'Total/Totale/Totaal' veya para birimi bulunamadı.")
-
-# =========================================
-# =========  SATIŞ EXCEL ANALİZİ  =========
-# =========================================
-
-st.markdown("---")
-st.header("📊 Satış Excel Analizi (Aylık)")
-
-st.caption("""
-Bir veya birden fazla Excel yükleyebilirsin. Uygulama:
-- **Item Price** (r1) sütunundaki EUR tutarlarını toplar,
-- Kaç satır toplandıysa onu **satış adedi (satır sayımı)** olarak verir,
-- (Varsa) **Dispatched Quantity** (p1) sütununu toplayarak adet toplamını ayrıca gösterir.
-""")
-
-sales_files = st.file_uploader(
-    "Satış Excel dosyalarını yükleyin (XLSX/CSV)", type=["xlsx", "csv"], accept_multiple_files=True, key="sales"
-)
-
-col1, col2 = st.columns(2)
-with col1:
-    custom_price_col = st.text_input("Item Price sütun adı (otomatik: Item Price)", value="Item Price")
-with col2:
-    custom_qty_col = st.text_input("Dispatched Quantity sütun adı (otomatik: Dispatched Quantity)", value="Dispatched Quantity")
-
-def coerce_euro_number(x):
-    if pd.isna(x):
-        return None
-    if isinstance(x, (int, float)):
-        return float(x)
-    s = str(x).strip()
-    s = re.sub(r"[€EUReur£GBPgbpPLNplnSEKsek\s]", "", s)
-    if s.count(",") == 1 and s.count(".") >= 1:
-        s = s.replace(".", "")
-        s = s.replace(",", ".")
-    elif s.count(",") == 1 and s.count(".") == 0:
-        s = s.replace(",", ".")
-    s = re.sub(r"[^0-9.\-]", "", s)
-    try:
-        return float(s)
-    except:
-        return None
-
-sales_rows = []
-if sales_files:
-    all_frames = []
-    for f in sales_files:
-        if f.name.lower().endswith(".csv"):
-            df = pd.read_csv(f)
-        else:
-            df = pd.read_excel(f)
-
-        lower_map = {c.lower(): c for c in df.columns}
-
-        price_col_guess = None
-        for key in [custom_price_col, "Item Price", "item price", "price", "itemprice", "r1"]:
-            if key.lower() in lower_map:
-                price_col_guess = lower_map[key.lower()]
-                break
-
-        qty_col_guess = None
-        for key in [custom_qty_col, "Dispatched Quantity", "dispatched quantity", "quantity", "qty", "p1"]:
-            if key.lower() in lower_map:
-                qty_col_guess = lower_map[key.lower()]
-                break
-
-        if not price_col_guess:
-            st.warning(f"⚠️ {f.name} içinde '{custom_price_col}' / 'Item Price' sütunu bulunamadı.")
-            continue
-
-        df["_price_num"] = df[price_col_guess].apply(coerce_euro_number)
-        price_sum = df["_price_num"].dropna().sum()
-        sales_count_rows = int(df["_price_num"].dropna().shape[0])
-
-        qty_sum = None
-        if qty_col_guess:
-            df["_qty_num"] = pd.to_numeric(df[qty_col_guess], errors="coerce")
-            qty_sum = int(df["_qty_num"].dropna().sum())
-
-        sales_rows.append({
-            "Dosya": f.name,
-            "Toplam EUR (Item Price)": round(float(price_sum), 2) if pd.notna(price_sum) else 0.0,
-            "Satış Adedi (Satır sayımı)": sales_count_rows,
-            "Satış Adedi (Dispatched Quantity toplamı)": qty_sum if qty_sum is not None else "-"
-        })
-
-        keep_cols = [price_col_guess]
-        if qty_col_guess:
-            keep_cols.append(qty_col_guess)
-        df_keep = df[keep_cols].copy()
-        df_keep.insert(0, "Kaynak Dosya", f.name)
-        all_frames.append(df_keep)
-
-    if sales_rows:
-        sales_df = pd.DataFrame(sales_rows)
-        st.subheader("📦 Dosya Bazlı Satış Özeti")
-        st.dataframe(sales_df, use_container_width=True)
-
-        total_sales_eur = float(pd.to_numeric(sales_df["Toplam EUR (Item Price)"], errors="coerce").fillna(0).sum())
-        total_sales_count_rows = int(pd.to_numeric(sales_df["Satış Adedi (Satır sayımı)"], errors="coerce").fillna(0).sum())
-        dq_col = pd.to_numeric(sales_df.get("Satış Adedi (Dispatched Quantity toplamı)"), errors="coerce").fillna(0)
-        total_dq = int(dq_col.sum())
-
-        c1, c2, c3 = st.columns(3)
-        with c1:
-            st.success(f"💶 Genel Toplam Satış (EUR): **{round(total_sales_eur, 2)}**")
-        with c2:
-            st.info(f"🧾 Satış Adedi (satır sayımı): **{total_sales_count_rows}**")
-        with c3:
-            st.info(f"📦 Satış Adedi (Dispatched Quantity): **{total_dq}**")
-
-        if all_frames:
-            merged = pd.concat(all_frames, ignore_index=True)
-            out = io.BytesIO()
-            with pd.ExcelWriter(out, engine="openpyxl") as writer:
-                sales_df.to_excel(writer, index=False, sheet_name="Ozet")
-                merged.to_excel(writer, index=False, sheet_name="Detay")
-            st.download_button("📥 Satış Özeti + Detayı (Excel)", data=out.getvalue(), file_name="satis_ozet_detay.xlsx")
-
-            txt2 = sales_df.to_csv(sep="\t", index=False)
-            st.download_button("📄 Satış Özeti (TXT)", data=txt2, file_name="satis_ozet.txt")
-    else:
-        if sales_files:
-            st.warning("Yüklenen Excel/CSV dosyalarında uygun sütunlar bulunamadı veya tüm satırlar boş.")
-        else:
-            st.info("Henüz satış dosyası yüklemediniz.")
+import streamlit as st
+import pdfplumber
+import pandas as pd
+import io
+import re
+from collections import defaultdict
+from decimal import Decimal, InvalidOperation
+
+# ---- Genel Ayar ----
+st.set_page_config(page_title="PDF & Satış Analiz Aracı", layout="wide")
+st.title("💸 PDF Para Birimi Tarayıcı & Satış Excel Analiz")
+
+# =========================================
+# ============  PDF ANALİZİ  ==============
+# =========================================
+
+CURRENCIES = ["EUR", "PLN", "GBP", "SEK"]
+
+def extract_text_from_pdf(file):
+    text = ""
+    with pdfplumber.open(file) as pdf:
+        for page in pdf.pages:
+            page_text = page.extract_text()
+            if page_text:
+                text += page_text + "\n"
+    return text
+
+def normalize_number_str(s: str) -> str:
+    """
+    2,572.13 -> 2572.13
+    2.572,13 -> 2572.13
+    490.77   -> 490.77
+    490,77   -> 490.77
+    """
+    s = s.strip()
+    s = re.sub(r"[^\d,.\-]", "", s)
+    if s.count(",") == 1 and s.count(".") >= 1:
+        s = s.replace(".", "")
+        s = s.replace(",", ".")
+    elif s.count(",") == 1 and s.count(".") == 0:
+        s = s.replace(",", ".")
+    s = re.sub(r"[^0-9.\-]", "", s)
+    return s
+
+def to_decimal(val) -> Decimal:
+    if val is None:
+        return Decimal("0")
+    try:
+        return Decimal(str(val))
+    except InvalidOperation:
+        try:
+            return Decimal(normalize_number_str(str(val)))
+        except Exception:
+            return Decimal("0")
+
+def find_currency_amounts(text):
+    "Genel tarama: tüm 'CUR 123,45/123.45' eşleşmelerini yakalar."
+    out = []
+    for cur in CURRENCIES:
+        for m in re.findall(rf"{cur}\s+([0-9\.,]+)", text):
+            num = normalize_number_str(m)
+            try:
+                out.append((cur, float(num)))
+            except:
+                pass
+    return out
+
+def extract_totals_only(text):
+    """
+    Sadece 'toplam' satırlarını hedefler. Diller/anahtarlar:
+    - EN/FR/ES/NL/IT: Total, Totale, Totaal
+    - DE: Bruttobetrag, Nettobetrag, Gesamtbetrag, Summe
+    Çıktı: [(CUR, amount, label_priority)]
+    label_priority: Brutto=1, Netto=2, Diğer=9 (küçük daha öncelikli)
+    """
+    totals = []
+
+    # 1) “LABEL CUR AMT” (örn: Bruttobetrag EUR 6.30)
+    label_re = r"(Total|Totale|Totaal|Summe|Gesamtbetrag|Bruttobetrag|Nettobetrag)"
+    patt1 = rf"{label_re}.*?\b(EUR|GBP|PLN|SEK)\s+([0-9\.,]+)"
+    for lbl, cur, amt in re.findall(patt1, text, flags=re.IGNORECASE|re.DOTALL):
+        num = normalize_number_str(amt)
+        try:
+            val = float(num)
+            lbl_low = lbl.lower()
+            pr = 9
+            if "brutto" in lbl_low: pr = 1
+            elif "netto" in lbl_low: pr = 2
+            totals.append((cur, val, pr))
+        except:
+            pass
+
+    # 2) “CUR AMT ... LABEL” (yedek) (örn: EUR 6.30 ... Bruttobetrag)
+    patt2 = rf"\b(EUR|GBP|PLN|SEK)\s+([0-9\.,]+).*?{label_re}"
+    for cur, amt, lbl in re.findall(patt2, text, flags=re.IGNORECASE|re.DOTALL):
+        num = normalize_number_str(amt)
+        try:
+            val = float(num)
+            lbl_low = lbl.lower()
+            pr = 9
+            if "brutto" in lbl_low: pr = 1
+            elif "netto" in lbl_low: pr = 2
+            totals.append((cur, val, pr))
+        except:
+            pass
+
+    # 3) Klasik “Total EUR 123.45”
+    patt3 = rf"(?:^|\s)(Total|Totale|Totaal)\s+(EUR|GBP|PLN|SEK)\s+([0-9\.,]+)"
+    for lbl, cur, amt in re.findall(patt3, text, flags=re.IGNORECASE):
+        num = normalize_number_str(amt)
+        try:
+            val = float(num)
+            totals.append((cur, val, 9))
+        except:
+            pass
+
+    # Aynı satır farklı desenle yakalanırsa tekilleştir
+    uniq = {}
+    for cur, val, pr in totals:
+        key = cur
+        # Aynı para birimi için öncelik: Brutto (1) > Netto (2) > diğer (9); eşitse büyük tutarı seç
+        if key not in uniq:
+            uniq[key] = (val, pr)
+        else:
+            old_val, old_pr = uniq[key]
+            if pr < old_pr or (pr == old_pr and val > old_val):
+                uniq[key] = (val, pr)
+
+    # Listeye çevir
+    return [(k, v[0]) for k, v in uniq.items()]
+
+with st.expander("📄 PDF Analizi (EUR/PLN/GBP/SEK tespiti ve EUR'a çeviri)", expanded=True):
+    uploaded_pdfs = st.file_uploader("PDF dosyalarını yükleyin", type="pdf", accept_multiple_files=True, key="pdfs")
+
+    colA, colB, colC, colD = st.columns([1,1,2,2])
+    with colA:
+        convert = st.checkbox("💱 Sadece PLN/GBP/SEK'i EUR'a çevir", value=True)
+    with colB:
+        show_negative = st.checkbox("➖ Negatifleri göster", value=False)
+    with colC:
+        dedupe_in_file = st.checkbox("🔁 Aynı (para,tutar) tekrarlarını aynı dosyada tek say", value=True)
+    with colD:
+        totals_mode = st.checkbox("📌 Sadece 'Toplam' satırları (Total/Totale/Totaal/Brutto/Netto…)", value=True)
+
+    eur_rates = {
+        "PLN": st.number_input("PLN → EUR kuru", min_value=0.0, value=0.22),
+        "GBP": st.number_input("GBP → EUR kuru", min_value=0.0, value=1.17),
+        "SEK": st.number_input("SEK → EUR kuru", min_value=0.0, value=0.084)
+    }
+
+    pdf_rows = []
+
+    if uploaded_pdfs:
+        for file in uploaded_pdfs:
+            text = extract_text_from_pdf(file)
+
+            if totals_mode:
+                raw = extract_totals_only(text)
+                if not raw:
+                    raw = find_currency_amounts(text)  # fallback
+            else:
+                raw = find_currency_amounts(text)
+
+            iterable = set(raw) if dedupe_in_file else raw
+
+            sums = defaultdict(float)
+            for cur, amt in iterable:
+                if not show_negative and amt < 0:
+                    continue
+                sums[cur] += amt
+
+            for cur, total_amount in sums.items():
+                if cur == "EUR":
+                    eur_value = total_amount
+                else:
+                    eur_value = round(total_amount * eur_rates.get(cur, 0), 2) if convert else total_amount
+
+                pdf_rows.append({
+                    "Dosya": file.name,
+                    "Para Birimi": cur,
+                    "Toplam Tutar": round(total_amount, 2),
+                    "EUR Karşılığı": round(eur_value, 2)
+                })
+
+        if pdf_rows:
+            pdf_df = pd.DataFrame(pdf_rows)
+            st.dataframe(pdf_df, use_container_width=True)
+
+            eur_series = pdf_df["EUR Karşılığı"].apply(to_decimal)
+            total_eur = sum(eur_series, Decimal("0"))
+            st.success(f"💶 PDF'lerden Genel EUR Toplamı: {total_eur.quantize(Decimal('0.01'))} EUR")
+
+            xbuf = io.BytesIO()
+            pdf_df.to_excel(xbuf, index=False)
+            st.download_button("📥 PDF Sonuçlarını Excel olarak indir", data=xbuf.getvalue(), file_name="pdf_rapor.xlsx")
+
+            txt = pdf_df.to_csv(sep="\t", index=False)
+            st.download_button("📄 PDF Sonuçlarını TXT olarak indir", data=txt, file_name="pdf_rapor.txt")
+        else:
+            st.info("PDF'lerde geçerli 'Toplam' satırı veya para birimi bulunamadı.")
+
+# =========================================
+# =========  SATIŞ EXCEL ANALİZİ  =========
+# =========================================
+
+st.markdown("---")
+st.header("📊 Satış Excel Analizi (Aylık)")
+
+st.caption("""
+Bir veya birden fazla Excel yükleyebilirsin. Uygulama:
+- **Item Price** (r1) sütunundaki EUR tutarlarını toplar,
+- Kaç satır toplandıysa onu **satış adedi (satır sayımı)** olarak verir,
+- (Varsa) **Dispatched Quantity** (p1) sütununu toplayarak adet toplamını ayrıca gösterir.
+""")
+
+sales_files = st.file_uploader("Satış Excel dosyalarını yükleyin (XLSX/CSV)", type=["xlsx", "csv"], accept_multiple_files=True, key="sales")
+
+col1, col2 = st.columns(2)
+with col1:
+    custom_price_col = st.text_input("Item Price sütun adı (otomatik: Item Price)", value="Item Price")
+with col2:
+    custom_qty_col = st.text_input("Dispatched Quantity sütun adı (otomatik: Dispatched Quantity)", value="Dispatched Quantity")
+
+def coerce_euro_number(x):
+    if pd.isna(x):
+        return None
+    if isinstance(x, (int, float)):
+        return float(x)
+    s = str(x).strip()
+    s = re.sub(r"[€EUReur£GBPgbpPLNplnSEKsek\s]", "", s)
+    if s.count(",") == 1 and s.count(".") >= 1:
+        s = s.replace(".", "")
+        s = s.replace(",", ".")
+    elif s.count(",") == 1 and s.count(".") == 0:
+        s = s.replace(",", ".")
+    s = re.sub(r"[^0-9.\-]", "", s)
+    try:
+        return float(s)
+    except:
+        return None
+
+sales_rows = []
+if sales_files:
+    all_frames = []
+    for f in sales_files:
+        if f.name.lower().endswith(".csv"):
+            df = pd.read_csv(f)
+        else:
+            df = pd.read_excel(f)
+
+        lower_map = {c.lower(): c for c in df.columns}
+
+        price_col_guess = None
+        for key in [custom_price_col, "Item Price", "item price", "price", "itemprice", "r1"]:
+            if key.lower() in lower_map:
+                price_col_guess = lower_map[key.lower()]
+                break
+
+        qty_col_guess = None
+        for key in [custom_qty_col, "Dispatched Quantity", "dispatched quantity", "quantity", "qty", "p1"]:
+            if key.lower() in lower_map:
+                qty_col_guess = lower_map[key.lower()]
+                break
+
+        if not price_col_guess:
+            st.warning(f"⚠️ {f.name} içinde '{custom_price_col}' / 'Item Price' sütunu bulunamadı.")
+            continue
+
+        df["_price_num"] = df[price_col_guess].apply(coerce_euro_number)
+        price_sum = df["_price_num"].dropna().sum()
+        sales_count_rows = int(df["_price_num"].dropna().shape[0])
+
+        qty_sum = None
+        if qty_col_guess:
+            df["_qty_num"] = pd.to_numeric(df[qty_col_guess], errors="coerce")
+            qty_sum = int(df["_qty_num"].dropna().sum())
+
+        sales_rows.append({
+            "Dosya": f.name,
+            "Toplam EUR (Item Price)": round(float(price_sum), 2) if pd.notna(price_sum) else 0.0,
+            "Satış Adedi (Satır sayımı)": sales_count_rows,
+            "Satış Adedi (Dispatched Quantity toplamı)": qty_sum if qty_sum is not None else "-"
+        })
+
+        keep_cols = [price_col_guess]
+        if qty_col_guess:
+            keep_cols.append(qty_col_guess)
+        df_keep = df[keep_cols].copy()
+        df_keep.insert(0, "Kaynak Dosya", f.name)
+        all_frames.append(df_keep)
+
+    if sales_rows:
+        sales_df = pd.DataFrame(sales_rows)
+        st.subheader("📦 Dosya Bazlı Satış Özeti")
+        st.dataframe(sales_df, use_container_width=True)
+
+        total_sales_eur = float(pd.to_numeric(sales_df["Toplam EUR (Item Price)"], errors="coerce").fillna(0).sum())
+        total_sales_count_rows = int(pd.to_numeric(sales_df["Satış Adedi (Satır sayımı)"], errors="coerce").fillna(0).sum())
+        dq_col = pd.to_numeric(sales_df.get("Satış Adedi (Dispatched Quantity toplamı)"), errors="coerce").fillna(0)
+        total_dq = int(dq_col.sum())
+
+        c1, c2, c3 = st.columns(3)
+        with c1:
+            st.success(f"💶 Genel Toplam Satış (EUR): **{round(total_sales_eur, 2)}**")
+        with c2:
+            st.info(f"🧾 Satış Adedi (satır sayımı): **{total_sales_count_rows}**")
+        with c3:
+            st.info(f"📦 Satış Adedi (Dispatched Quantity): **{total_dq}**")
+
+        if all_frames:
+            merged = pd.concat(all_frames, ignore_index=True)
+            out = io.BytesIO()
+            with pd.ExcelWriter(out, engine="openpyxl") as writer:
+                sales_df.to_excel(writer, index=False, sheet_name="Ozet")
+                merged.to_excel(writer, index=False, sheet_name="Detay")
+            st.download_button("📥 Satış Özeti + Detayı (Excel)", data=out.getvalue(), file_name="satis_ozet_detay.xlsx")
+
+            txt2 = sales_df.to_csv(sep="\t", index=False)
+            st.download_button("📄 Satış Özeti (TXT)", data=txt2, file_name="satis_ozet.txt")
+    else:
+        st.warning("Yüklenen Excel/CSV dosyalarında uygun sütunlar bulunamadı veya tüm satırlar boş.")
+else:
+    st.info("Henüz satış dosyası yüklemediniz.")
 
EOF
)
