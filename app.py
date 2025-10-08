import streamlit as st
import pdfplumber
import pandas as pd
import io
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation

# ------------- Genel -------------
st.set_page_config(page_title="Aylık PDF & Satış Analizi", layout="wide")
st.title("📅 Aylık PDF & Satış Analizi (Ocak–Aralık)")

CURRENCIES = ["EUR", "PLN", "GBP", "SEK"]
MONTHS = [
    ("2025-01", "Ocak"), ("2025-02", "Şubat"), ("2025-03", "Mart"), ("2025-04", "Nisan"),
    ("2025-05", "Mayıs"), ("2025-06", "Haziran"), ("2025-07", "Temmuz"), ("2025-08", "Ağustos"),
    ("2025-09", "Eylül"), ("2025-10", "Ekim"), ("2025-11", "Kasım"), ("2025-12", "Aralık")
]

# ------------- Yardımcılar (PDF) -------------
def extract_text_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

def normalize_number_str(s: str) -> str:
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
    Etiketler: Total/Totale/Totaal, Summe, Gesamtbetrag, Bruttobetrag, Nettobetrag,
              Endbetrag, (OCR varyant) Nettobertrag
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
    if not cands:
        return None

    def has_decimal(v):
        s = f"{v}"
        return "." in s

    # ondalıklı varsa tam sayıları ele
    if any(has_decimal(x["val"]) for x in cands):
        cands = [x for x in cands if has_decimal(x["val"])]
        if not cands:
            return None

    if method == "max":
        return max(cands, key=lambda x: x["val"])
    if method == "min":
        return min(cands, key=lambda x: x["val"])

    def two_decimals(v):
        s = f"{v:.10f}".rstrip("0").rstrip(".")
        return "." in s and len(s.split(".")[1]) == 2

    def score(x):
        return (
            10 if x["labeled"] else 0,
            5 if has_decimal(x["val"]) else 0,
            3 if two_decimals(x["val"]) else 0,
            x["pos"]  # daha sonra gelen daha iyi
        )
    return sorted(cands, key=score)[-1]

# ------------- Yardımcılar (Satış Excel) -------------
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

# ------------- Aylık Sekme Bileşeni -------------
def render_month_tab(month_key: str, label: str):
    st.subheader(f"🗓️ {label} 2025")

    colA, colB, colC = st.columns([1,1,2])
    with colA:
        convert = st.checkbox("💱 Sadece PLN/GBP/SEK'i EUR'a çevir", value=True, key=f"conv_{month_key}")
    with colB:
        show_negative = st.checkbox("➖ Negatifleri göster", value=False, key=f"neg_{month_key}")
    with colC:
        totals_mode = st.checkbox("📌 Sadece 'Toplam' satırları (Total/Totale/Totaal/Brutto/Netto…)", value=True, key=f"totals_{month_key}")

    c1, c2 = st.columns(2)
    with c1:
        eur_rates = {
            "PLN": st.number_input("PLN → EUR kuru", min_value=0.0, value=0.22, key=f"pln_{month_key}"),
            "GBP": st.number_input("GBP → EUR kuru", min_value=0.0, value=1.17, key=f"gbp_{month_key}"),
            "SEK": st.number_input("SEK → EUR kuru", min_value=0.0, value=0.084, key=f"sek_{month_key}")
        }
    with c2:
        pick_method_label = st.selectbox("Toplam seçim yöntemi", ["Son görünen", "En büyük", "En küçük"], index=0, key=f"pick_{month_key}")
        method_map = {"Son görünen": "last", "En büyük": "max", "En küçük": "min"}

    # --- PDF Yükleme ---
    with st.expander(f"📄 {label} PDF Yükle (faturalar)", expanded=False):
        uploaded_pdfs = st.file_uploader("PDF yükle", type="pdf", accept_multiple_files=True, key=f"pdfs_{month_key}")

        pdf_rows = []
        if uploaded_pdfs:
            for file in uploaded_pdfs:
                text = extract_text_from_pdf(file)

                if totals_mode:
                    candidates = extract_totals_only(text)
                    if not candidates:
                        raw_pairs = find_currency_amounts(text)
                        candidates = [{"cur": c, "val": v, "pos": 0, "label": "", "labeled": False, "raw": f"{c} {v}"} for c, v in raw_pairs]
                else:
                    raw_pairs = find_currency_amounts(text)
                    candidates = [{"cur": c, "val": v, "pos": 0, "label": "", "labeled": False, "raw": f"{c} {v}"} for c, v in raw_pairs]

                selected_by_cur = {}
                for cur in CURRENCIES:
                    cur_cands = [c for c in candidates if c["cur"] == cur]
                    pick = pick_best_total(cur_cands, method=method_map[pick_method_label])
                    if pick:
                        selected_by_cur[cur] = pick["val"]

                for cur, total_amount in selected_by_cur.items():
                    if not show_negative and total_amount < 0:
                        continue
                    if cur == "EUR":
                        eur_value = total_amount
                    else:
                        eur_value = round(total_amount * eur_rates.get(cur, 0), 2) if convert else total_amount
                    pdf_rows.append({
                        "Ay": label,
                        "Dosya": file.name,
                        "Para Birimi": cur,
                        "Toplam Tutar": round(total_amount, 2),
                        "EUR Karşılığı": round(eur_value, 2)
                    })

            if pdf_rows:
                pdf_df = pd.DataFrame(pdf_rows)
                st.dataframe(pdf_df, use_container_width=True)
                total_eur = Decimal("0")
                for v in pd.to_numeric(pdf_df["EUR Karşılığı"], errors="coerce").fillna(0):
                    total_eur += to_decimal(v)
                st.success(f"💶 {label} PDF'lerden EUR Toplamı: {total_eur.quantize(Decimal('0.01'))} EUR")

                xbuf = io.BytesIO()
                pdf_df.to_excel(xbuf, index=False)
                st.download_button(f"📥 {label} PDF Sonuçları (Excel)", data=xbuf.getvalue(), file_name=f"{month_key}_pdf_rapor.xlsx")
            else:
                st.info(f"{label} için PDF sonucu yok.")
        else:
            pdf_df = pd.DataFrame()

    # --- Satış Excel Yükleme ---
    st.markdown("—")
    st.subheader(f"📊 {label} Satış Excel Analizi")

    colp1, colp2 = st.columns(2)
    with colp1:
        price_col = st.text_input("Item Price sütun adı", value="Item Price", key=f"price_{month_key}")
    with colp2:
        qty_col = st.text_input("Dispatched Quantity sütun adı (opsiyonel)", value="Dispatched Quantity", key=f"qty_{month_key}")

    with st.expander(f"📈 {label} Satış Excel/CSV Yükle", expanded=False):
        sales_files = st.file_uploader("Excel/CSV yükle", type=["xlsx","csv"], accept_multiple_files=True, key=f"sales_{month_key}")

        sales_rows = []
        merged_frames = []
        if sales_files:
            for f in sales_files:
                if f.name.lower().endswith(".csv"):
                    df = pd.read_csv(f)
                else:
                    df = pd.read_excel(f)

                lower_map = {c.lower(): c for c in df.columns}

                price_col_guess = None
                for key in [price_col, "Item Price", "item price", "price", "itemprice", "r1"]:
                    if key.lower() in lower_map:
                        price_col_guess = lower_map[key.lower()]
                        break

                qty_col_guess = None
                for key in [qty_col, "Dispatched Quantity", "dispatched quantity", "quantity", "qty", "p1"]:
                    if key.lower() in lower_map:
                        qty_col_guess = lower_map[key.lower()]
                        break

                if not price_col_guess:
                    st.warning(f"⚠️ {f.name} içinde '{price_col}' / 'Item Price' bulunamadı.")
                    continue

                df["_price_num"] = df[price_col_guess].apply(coerce_euro_number)
                price_sum = df["_price_num"].dropna().sum()
                sales_count_rows = int(df["_price_num"].dropna().shape[0])

                qty_sum = None
                if qty_col_guess:
                    df["_qty_num"] = pd.to_numeric(df[qty_col_guess], errors="coerce")
                    qty_sum = int(df["_qty_num"].dropna().sum())

                sales_rows.append({
                    "Ay": label,
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
                df_keep.insert(0, "Ay", label)
                merged_frames.append(df_keep)

            if sales_rows:
                sales_df = pd.DataFrame(sales_rows)
                st.dataframe(sales_df, use_container_width=True)

                tot_sales_eur = float(pd.to_numeric(sales_df["Toplam EUR (Item Price)"], errors="coerce").fillna(0).sum())
                tot_row_cnt = int(pd.to_numeric(sales_df["Satış Adedi (Satır sayımı)"], errors="coerce").fillna(0).sum())
                dq_col_series = pd.to_numeric(sales_df["Satış Adedi (Dispatched Quantity toplamı)"].replace("-", 0), errors="coerce").fillna(0)
                tot_dq = int(dq_col_series.sum())

                c1, c2, c3 = st.columns(3)
                with c1:
                    st.success(f"💶 {label} Satış Toplamı (EUR): **{round(tot_sales_eur, 2)}**")
                with c2:
                    st.info(f"🧾 {label} Satış Adedi (satır): **{tot_row_cnt}**")
                with c3:
                    st.info(f"📦 {label} Satış Adedi (Dispatched Qty): **{tot_dq}**")

                out = io.BytesIO()
                with pd.ExcelWriter(out, engine="openpyxl") as writer:
                    sales_df.to_excel(writer, index=False, sheet_name=f"{label}_Ozet")
                    if merged_frames:
                        pd.concat(merged_frames, ignore_index=True).to_excel(writer, index=False, sheet_name=f"{label}_Detay")
                st.download_button(f"📥 {label} Satış Özeti (Excel)", data=out.getvalue(), file_name=f"{month_key}_satis_ozet.xlsx")
            else:
                st.info(f"{label} için satış özeti yok.")
        else:
            sales_df = pd.DataFrame()

    return pdf_df, sales_df

# ------------- Sekmeler ve Yıllık Özet -------------
tabs = st.tabs([m[1] for m in MONTHS])

all_pdf_dfs = []
all_sales_dfs = []

for tab, (mkey, mlabel) in zip(tabs, MONTHS):
    with tab:
        pdf_df, sales_df = render_month_tab(mkey, mlabel)
        if not pdf_df.empty:
            all_pdf_dfs.append(pdf_df.assign(Ay=mlabel))
        if not sales_df.empty:
            all_sales_dfs.append(sales_df.assign(Ay=mlabel))

st.markdown("---")
st.header("📚 Yıllık Özet (Tüm Aylar)")

colA, colB = st.columns(2)
with colA:
    if all_pdf_dfs:
        pdf_all = pd.concat(all_pdf_dfs, ignore_index=True)
        st.subheader("📄 PDF Birleşik")
        st.dataframe(pdf_all, use_container_width=True)
        total_eur = Decimal("0")
        for v in pd.to_numeric(pdf_all["EUR Karşılığı"], errors="coerce").fillna(0):
            total_eur += to_decimal(v)
        st.success(f"💶 Yıl Boyu PDF EUR Toplamı: {total_eur.quantize(Decimal('0.01'))} EUR")
    else:
        st.info("Henüz PDF verisi yok.")

with colB:
    if all_sales_dfs:
        sales_all = pd.concat(all_sales_dfs, ignore_index=True)
        st.subheader("📈 Satış Birleşik")
        st.dataframe(sales_all, use_container_width=True)
        ge_tot_eur = float(pd.to_numeric(sales_all["Toplam EUR (Item Price)"], errors="coerce").fillna(0).sum())
        ge_rows = int(pd.to_numeric(sales_all["Satış Adedi (Satır sayımı)"], errors="coerce").fillna(0).sum())
        ge_dq = int(pd.to_numeric(sales_all["Satış Adedi (Dispatched Quantity toplamı)"].replace("-", 0), errors="coerce").fillna(0).sum())
        st.success(f"💶 Yıl Boyu Satış Toplamı (EUR): {round(ge_tot_eur, 2)} | 🧾 Satış Adedi: {ge_rows} | 📦 Dispatched Qty: {ge_dq}")
    else:
        st.info("Henüz satış verisi yok.")

# Tek Excel indir: tüm aylar
if all_pdf_dfs or all_sales_dfs:
    out_all = io.BytesIO()
    with pd.ExcelWriter(out_all, engine="openpyxl") as writer:
        if all_pdf_dfs:
            pdf_all.to_excel(writer, index=False, sheet_name="PDF_Birlesik")
        if all_sales_dfs:
            sales_all.to_excel(writer, index=False, sheet_name="Satis_Birlesik")
    st.download_button("📥 Yıllık Birleşik Excel (PDF+Satış)", data=out_all.getvalue(), file_name="yillik_birlesik_ozet.xlsx")
