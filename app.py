import streamlit as st
import pdfplumber
import pandas as pd
import io
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation

# ---- Genel Ayar ----
st.set_page_config(page_title="PDF & Satış Analiz Aracı", layout="wide")
st.title("💸 PDF Para Birimi Tarayıcı & Satış Excel Analiz")

# =========================================
# ============  PDF ANALİZİ  ==============
# =========================================

CURRENCIES = ["EUR", "PLN", "GBP", "SEK"]

def extract_text_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

def normalize_number_str(s: str) -> str:
    """
    2,572.13 -> 2572.13
    2.572,13 -> 2572.13
    490.77   -> 490.77
    490,77   -> 490.77
    """
    s = s.strip()
    s = re.sub(r"[^\d,.\-]", "", s)
    if s.count(",") == 1 and s.count(".") >= 1:
        s = s.replace(".", "")
        s = s.replace(",", ".")
    elif s.count(",") == 1 and s.count(".") == 0:
        s = s.replace(",", ".")
    s = re.sub(r"[^0-9.\-]", "", s)
    return s

def to_decimal(val) -> Decimal:
    if val is None:
        return Decimal("0")
    try:
        return Decimal(str(val))
    except InvalidOperation:
        try:
            return Decimal(normalize_number_str(str(val)))
        except Exception:
            return Decimal("0")

def find_currency_amounts(text):
    """
    Genel tarama: 'CUR 123,45/123.45' eşleşmelerini yakalar.
    Fallback olarak kullanılır.
    """
    out = []
    for cur in CURRENCIES:
        for m in re.findall(rf"{cur}\s+([0-9\.,]+)", text):
            num = normalize_number_str(m)
            try:
                out.append((cur, float(num)))
            except:
                pass
    return out

def extract_totals_only(text):
    """
    Etiketli 'toplam' satırlarını yakalar:
    Total/Totale/Totaal, Summe, Gesamtbetrag, Bruttobetrag, Nettobetrag,
    Endbetrag, (OCR varyant) Nettobertrag.
    Çıktı: [{cur, val(float), pos(int), label(str), labeled(bool), raw(str)}]
    """
    candidates = []

    def push(cur, amt_str, label, pos):
        num = normalize_number_str(amt_str)
        try:
            val = float(num)
            candidates.append({
                "cur": cur,
                "val": val,
                "pos": pos,
                "label": label or "",
                "labeled": bool(label),
                "raw": f"{label or ''} {cur} {amt_str}".strip()
            })
        except:
            pass

    labels = r"(Total|Totale|Totaal|Summe|Gesamtbetrag|Bruttobetrag|Nettobetrag|Nettobertrag|Endbetrag)"
    currs  = r"(EUR|GBP|PLN|SEK)"

    # LABEL ... CUR AMT
    for m in re.finditer(rf"{labels}.*?\b{currs}\s+([0-9\.,]+)", text, flags=re.IGNORECASE|re.DOTALL):
        lbl, cur, amt = m.group(1), m.group(2), m.group(3)
        push(cur, amt, lbl, m.start())

    # CUR AMT ... LABEL
    for m in re.finditer(rf"\b{currs}\s+([0-9\.,]+).*?{labels}", text, flags=re.IGNORECASE|re.DOTALL):
        cur, amt, lbl = m.group(1), m.group(2), m.group(3)
        push(cur, amt, lbl, m.start())

    # klasik: LABEL CUR AMT
    for m in re.finditer(rf"(?:^|\s){labels}\s+{currs}\s+([0-9\.,]+)", text, flags=re.IGNORECASE):
        lbl, cur, amt = m.group(1), m.group(2), m.group(3)
        push(cur, amt, lbl, m.start())

    return candidates

def pick_best_total(cands, method="last"):
    """
    Eğer ondalıklı aday varsa (6.30/6,30), tam sayıları (303) tamamen eler.
    Skor: labeled>unlabeled, ondalık>tam sayı, 2 ondalık>diğer ve pos (last modu).
    method: "last" | "max" | "min"
    """
    if not cands:
        return None

    def has_decimal(v):
        s = f"{v}"
        return "." in s

    # Ondalıklı aday varsa tam sayıları ele
    if any(has_decimal(x["val"]) for x in cands):
        cands = [x for x in cands if has_decimal(x["val"])]
        if not cands:
            return None

    if method == "max":
        return max(cands, key=lambda x: x["val"])
    if method == "min":
        return min(cands, key=lambda x: x["val"])

    # default: 'last' + kalite skoru
    def two_decimals(v):
        s = f"{v:.10f}".rstrip("0").rstrip(".")
        return "." in s and len(s.split(".")[1]) == 2

    def score(x):
        return (
            10 if x["labeled"] else 0,       # etiketli olması
            5 if has_decimal(x["val"]) else 0,
            3 if two_decimals(x["val"]) else 0,
            x["pos"]                          # metinde daha sonra gelen (daha büyük pos) tercih
        )

    return sorted(cands, key=score)[-1]

with st.expander("📄 PDF Analizi (EUR/PLN/GBP/SEK tespiti ve EUR'a çeviri)", expanded=True):
    uploaded_pdfs = st.file_uploader(
        "PDF dosyalarını yükleyin", type="pdf", accept_multiple_files=True, key="pdfs"
    )

    colA, colB, colC = st.columns([1,1,2])
    with colA:
        convert = st.checkbox("💱 Sadece PLN/GBP/SEK'i EUR'a çevir", value=True)
    with colB:
        show_negative = st.checkbox("➖ Negatifleri göster", value=False)
    with colC:
        totals_mode = st.checkbox("📌 Sadece 'Toplam' satırları (Total/Totale/Totaal/Brutto/Netto…)", value=True)

    # Toplam seçim yöntemi
    sel_col1, sel_col2 = st.columns([2,2])
    with sel_col1:
        total_pick_method = st.selectbox("Toplam seçim yöntemi", ["Son görünen", "En büyük", "En küçük"], index=0)
    method_map = {"Son görünen": "last", "En büyük": "max", "En küçük": "min"}

    # Döviz kurları
    eur_rates = {
        "PLN": st.number_input("PLN → EUR kuru", min_value=0.0, value=0.22),
        "GBP": st.number_input("GBP → EUR kuru", min_value=0.0, value=1.17),
        "SEK": st.number_input("SEK → EUR kuru", min_value=0.0, value=0.084)
    }

    pdf_rows = []

    if uploaded_pdfs:
        for file in uploaded_pdfs:
            text = extract_text_from_pdf(file)

            if totals_mode:
                candidates = extract_totals_only(text)
                # Hiç etiketli aday yoksa genel taramaya düş
                if not candidates:
                    raw_pairs = find_currency_amounts(text)
                    # raw_pairs -> dict listesine çevir (etiketsiz)
                    candidates = [{"cur": c, "val": v, "pos": 0, "label": "", "labeled": False, "raw": f"{c} {v}"} for c, v in raw_pairs]
            else:
                raw_pairs = find_currency_amounts(text)
                candidates = [{"cur": c, "val": v, "pos": 0, "label": "", "labeled": False, "raw": f"{c} {v}"} for c, v in raw_pairs]

            # Para birimi bazında en iyi toplamı seç
            selected_by_cur = {}
            for cur in CURRENCIES:
                cur_cands = [c for c in candidates if c["cur"] == cur]
                pick = pick_best_total(cur_cands, method=method_map[total_pick_method])
                if pick:
                    selected_by_cur[cur] = pick["val"]

            # Sonuç satırları
            for cur, total_amount in selected_by_cur.items():
                if not show_negative and total_amount < 0:
                    continue
                if cur == "EUR":
                    eur_value = total_amount  # EUR'u çevirmeyiz
                else:
                    eur_value = round(total_amount * eur_rates.get(cur, 0), 2) if convert else total_amount

                pdf_rows.append({
                    "Dosya": file.name,
                    "Para Birimi": cur,
                    "Toplam Tutar": round(total_amount, 2),
                    "EUR Karşılığı": round(eur_value, 2)
                })

        if pdf_rows:
            pdf_df = pd.DataFrame(pdf_rows)
            st.dataframe(pdf_df, use_container_width=True)

            # Genel toplam (Decimal güvenli toplama)
            eur_series = pd.to_numeric(pdf_df["EUR Karşılığı"], errors="coerce").fillna(0)
            total_eur = Decimal("0")
            for v in eur_series:
                total_eur += to_decimal(v)
            st.success(f"💶 PDF'lerden Genel EUR Toplamı: {total_eur.quantize(Decimal('0.01'))} EUR")

            # Excel indir
            xbuf = io.BytesIO()
            pdf_df.to_excel(xbuf, index=False)
            st.download_button("📥 PDF Sonuçlarını Excel olarak indir", data=xbuf.getvalue(), file_name="pdf_rapor.xlsx")

            # TXT indir
            txt = pdf_df.to_csv(sep="\t", index=False)
            st.download_button("📄 PDF Sonuçlarını TXT olarak indir", data=txt, file_name="pdf_rapor.txt")
        else:
            st.info("PDF'lerde geçerli 'Toplam' satırı veya para birimi bulunamadı.")

# =========================================
# =========  SATIŞ EXCEL ANALİZİ  =========
# =========================================

st.markdown("---")
st.header("📊 Satış Excel Analizi (Aylık)")

st.caption("""
Bir veya birden fazla Excel yükleyebilirsin. Uygulama:
- **Item Price** (r1) sütunundaki EUR tutarlarını toplar,
- Kaç satır toplandıysa onu **satış adedi (satır sayımı)** olarak verir,
- (Varsa) **Dispatched Quantity** (p1) sütununu toplayarak adet toplamını ayrıca gösterir.
""")

sales_files = st.file_uploader(
    "Satış Excel dosyalarını yükleyin (XLSX/CSV)", type=["xlsx", "csv"], accept_multiple_files=True, key="sales"
)

col1, col2 = st.columns(2)
with col1:
    custom_price_col = st.text_input("Item Price sütun adı (otomatik: Item Price)", value="Item Price")
with col2:
    custom_qty_col = st.text_input("Dispatched Quantity sütun adı (otomatik: Dispatched Quantity)", value="Dispatched Quantity")

def coerce_euro_number(x):
    if pd.isna(x):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    s = re.sub(r"[€EUReur£GBPgbpPLNplnSEKsek\s]", "", s)
    if s.count(",") == 1 and s.count(".") >= 1:
        s = s.replace(".", "")
        s = s.replace(",", ".")
    elif s.count(",") == 1 and s.count(".") == 0:
        s = s.replace(",", ".")
    s = re.sub(r"[^0-9.\-]", "", s)
    try:
        return float(s)
    except:
        return None

sales_rows = []
if sales_files:
    all_frames = []
    for f in sales_files:
        if f.name.lower().endswith(".csv"):
            df = pd.read_csv(f)
        else:
            df = pd.read_excel(f)

        lower_map = {c.lower(): c for c in df.columns}

        price_col_guess = None
        for key in [custom_price_col, "Item Price", "item price", "price", "itemprice", "r1"]:
            if key.lower() in lower_map:
                price_col_guess = lower_map[key.lower()]
                break

        qty_col_guess = None
        for key in [custom_qty_col, "Dispatched Quantity", "dispatched quantity", "quantity", "qty", "p1"]:
            if key.lower() in lower_map:
                qty_col_guess = lower_map[key.lower()]
                break

        if not price_col_guess:
            st.warning(f"⚠️ {f.name} içinde '{custom_price_col}' / 'Item Price' sütunu bulunamadı.")
            continue

        df["_price_num"] = df[price_col_guess].apply(coerce_ero_number) if False else df[price_col_guess].apply(coerce_euro_number)
        price_sum = df["_price_num"].dropna().sum()
        sales_count_rows = int(df["_price_num"].dropna().shape[0])

        qty_sum = None
        if qty_col_guess:
            df["_qty_num"] = pd.to_numeric(df[qty_col_guess], errors="coerce")
            qty_sum = int(df["_qty_num"].dropna().sum())

        sales_rows.append({
            "Dosya": f.name,
            "Toplam EUR (Item Price)": round(float(price_sum), 2) if pd.notna(price_sum) else 0.0,
            "Satış Adedi (Satır sayımı)": sales_count_rows,
            "Satış Adedi (Dispatched Quantity toplamı)": qty_sum if qty_sum is not None else "-"
        })

        keep_cols = [price_col_guess]
        if qty_col_guess:
            keep_cols.append(qty_col_guess)
        df_keep = df[keep_cols].copy()
        df_keep.insert(0, "Kaynak Dosya", f.name)
        all_frames.append(df_keep)

    if sales_rows:
        sales_df = pd.DataFrame(sales_rows)
        st.subheader("📦 Dosya Bazlı Satış Özeti")
        st.dataframe(sales_df, use_container_width=True)

        total_sales_eur = float(pd.to_numeric(sales_df["Toplam EUR (Item Price)"], errors="coerce").fillna(0).sum())
        total_sales_count_rows = int(pd.to_numeric(sales_df["Satış Adedi (Satır sayımı)"], errors="coerce").fillna(0).sum())
        dq_col = pd.to_numeric(sales_df.get("Satış Adedi (Dispatched Quantity toplamı)"), errors="coerce").fillna(0)
        total_dq = int(dq_col.sum())

        c1, c2, c3 = st.columns(3)
        with c1:
            st.success(f"💶 Genel Toplam Satış (EUR): **{round(total_sales_eur, 2)}**")
        with c2:
            st.info(f"🧾 Satış Adedi (satır sayımı): **{total_sales_count_rows}**")
        with c3:
            st.info(f"📦 Satış Adedi (Dispatched Quantity): **{total_dq}**")

        if all_frames:
            merged = pd.concat(all_frames, ignore_index=True)
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine="openpyxl") as writer:
                sales_df.to_excel(writer, index=False, sheet_name="Ozet")
                merged.to_excel(writer, index=False, sheet_name="Detay")
            st.download_button("📥 Satış Özeti + Detayı (Excel)", data=out.getvalue(), file_name="satis_ozet_detay.xlsx")

            txt2 = sales_df.to_csv(sep="\t", index=False)
            st.download_button("📄 Satış Özeti (TXT)", data=txt2, file_name="satis_ozet.txt")
    else:
        if sales_files:
            st.warning("Yüklenen Excel/CSV dosyalarında uygun sütunlar bulunamadı veya tüm satırlar boş.")
        else:
            st.info("Henüz satış dosyası yüklemediniz.")
