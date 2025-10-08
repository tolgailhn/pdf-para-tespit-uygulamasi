import streamlit as st
import pdfplumber
import pandas as pd
import io
import re
from decimal import Decimal, InvalidOperation
from collections import defaultdict

st.set_page_config(page_title="Yıllık Otomatik PDF & Satış Analizi", layout="wide")
st.title("📅 Otomatik Aylık PDF + Satış Analizi (Ocak–Aralık 2025)")

# ---------- Ay tanıma haritaları ----------
MONTH_MAP = {
    "01": "Ocak", "1": "Ocak", "ocak": "Ocak",
    "02": "Şubat", "2": "Şubat", "subat": "Şubat", "şubat": "Şubat",
    "03": "Mart", "3": "Mart",
    "04": "Nisan", "4": "Nisan",
    "05": "Mayıs", "5": "Mayıs", "mayis": "Mayıs",
    "06": "Haziran", "6": "Haziran",
    "07": "Temmuz", "7": "Temmuz",
    "08": "Ağustos", "8": "Ağustos", "agustos": "Ağustos",
    "09": "Eylül", "9": "Eylül", "eylul": "Eylül",
    "10": "Ekim",
    "11": "Kasım",
    "12": "Aralık", "aralik": "Aralık"
}

def detect_month_from_name(filename):
    fn = filename.lower()
    for k, v in MONTH_MAP.items():
        if k in fn:
            return v
    return "Bilinmiyor"

# ---------- Ortak yardımcılar ----------
def normalize_number_str(s: str) -> str:
    s = s.strip()
    s = re.sub(r"[^\d,.\-]", "", s)
    if s.count(",") == 1 and s.count(".") >= 1:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(",") == 1 and s.count(".") == 0:
        s = s.replace(",", ".")
    return re.sub(r"[^0-9.\-]", "", s)

def to_decimal(val) -> Decimal:
    if val is None: return Decimal("0")
    try: return Decimal(str(val))
    except InvalidOperation:
        try: return Decimal(normalize_number_str(str(val)))
        except: return Decimal("0")

def extract_text_from_pdf(file):
    txt = ""
    with pdfplumber.open(file) as pdf:
        for p in pdf.pages:
            t = p.extract_text()
            if t: txt += t + "\n"
    return txt

def extract_totals_only(text):
    labels = r"(Total|Totale|Totaal|Summe|Gesamtbetrag|Bruttobetrag|Nettobetrag|Endbetrag|Nettobertrag)"
    currs = r"(EUR|GBP|PLN|SEK)"
    cands = []
    for m in re.finditer(rf"{labels}.*?\b{currs}\s+([0-9\.,]+)", text, flags=re.I|re.S):
        lbl, cur, amt = m.group(1), m.group(2), m.group(3)
        val = float(normalize_number_str(amt))
        cands.append((cur, val, lbl, m.start()))
    return cands

def pick_best_total(cands):
    if not cands: return None
    def has_dec(v): return "." in str(v)
    if any(has_dec(v[1]) for v in cands):
        cands = [x for x in cands if has_dec(x[1])]
    # en son + etiketli tercih
    return sorted(cands, key=lambda x:(x[3], "brutto" in x[2].lower(), "netto" in x[2].lower()))[-1]

# ---------- PDF Yükleme ----------
st.header("📄 PDF Faturalar (tüm ayları birlikte yükle)")
pdf_files = st.file_uploader("PDF dosyaları (Ocak–Aralık hepsi)", type="pdf", accept_multiple_files=True)

convert = st.checkbox("💱 Sadece PLN/GBP/SEK'i EUR'a çevir", value=True)
eur_rates = {
    "PLN": st.number_input("PLN → EUR kuru", value=0.22, min_value=0.0),
    "GBP": st.number_input("GBP → EUR kuru", value=1.17, min_value=0.0),
    "SEK": st.number_input("SEK → EUR kuru", value=0.084, min_value=0.0)
}

pdf_rows = []
if pdf_files:
    for f in pdf_files:
        ay = detect_month_from_name(f.name)
        text = extract_text_from_pdf(f)
        cands = extract_totals_only(text)
        by_cur = defaultdict(list)
        for cur, val, lbl, pos in cands:
            by_cur[cur].append((cur, val, lbl, pos))
        for cur, lst in by_cur.items():
            pick = pick_best_total(lst)
            if not pick: continue
            _, val, _, _ = pick
            eur_val = val if cur=="EUR" else round(val * eur_rates.get(cur,0),2) if convert else val
            pdf_rows.append({"Ay":ay,"Dosya":f.name,"Para Birimi":cur,"Toplam Tutar":round(val,2),"EUR Karşılığı":round(eur_val,2)})

    pdf_df = pd.DataFrame(pdf_rows)
    st.dataframe(pdf_df, use_container_width=True)
    tot_eur = sum(pd.to_numeric(pdf_df["EUR Karşılığı"], errors="coerce").fillna(0))
    st.success(f"💶 PDF'lerden Genel EUR Toplamı: {round(tot_eur,2)} EUR")
else:
    pdf_df = pd.DataFrame()

# ---------- Satış Excel ----------
st.header("📊 Satış Excel Dosyaları (tüm ayları birlikte yükle)")
sales_files = st.file_uploader("Satış dosyaları", type=["xlsx","csv"], accept_multiple_files=True)

sales_rows=[]
if sales_files:
    for f in sales_files:
        ay = detect_month_from_name(f.name)
        df = pd.read_excel(f) if f.name.endswith("xlsx") else pd.read_csv(f)
        cols = [c.lower() for c in df.columns]
        price_col = next((c for c in df.columns if "item" in c.lower() and "price" in c.lower()), None)
        qty_col = next((c for c in df.columns if "dispatched" in c.lower() or "quantity" in c.lower()), None)
        if not price_col:
            st.warning(f"{f.name} içinde Item Price sütunu yok.")
            continue
        df["_price"] = pd.to_numeric(df[price_col].astype(str).str.replace(",","."), errors="coerce")
        tot = df["_price"].sum()
        satir = df["_price"].count()
        qty_tot = int(pd.to_numeric(df[qty_col], errors="coerce").sum()) if qty_col else "-"
        sales_rows.append({"Ay":ay,"Dosya":f.name,"Toplam EUR (Item Price)":round(tot,2),"Satış Adedi (Satır)":satir,"Satış Adedi (Qty)":qty_tot})
    sales_df = pd.DataFrame(sales_rows)
    st.dataframe(sales_df, use_container_width=True)
    total_sales = sum(pd.to_numeric(sales_df["Toplam EUR (Item Price)"], errors="coerce").fillna(0))
    total_rows = sum(pd.to_numeric(sales_df["Satış Adedi (Satır)"], errors="coerce").fillna(0))
    st.success(f"💶 Toplam Satış (EUR): {round(total_sales,2)} | 🧾 Adet: {total_rows}")
else:
    sales_df=pd.DataFrame()

# ---------- Aylık & Yıllık özet ----------
if not pdf_df.empty or not sales_df.empty:
    st.header("📚 Aylık + Yıllık Özet")
    aylik = (pdf_df.groupby("Ay")["EUR Karşılığı"].sum().reset_index(name="PDF EUR Toplamı")
             if not pdf_df.empty else pd.DataFrame(columns=["Ay","PDF EUR Toplamı"]))
    satis = (sales_df.groupby("Ay")["Toplam EUR (Item Price)"].sum().reset_index(name="Satış EUR Toplamı")
             if not sales_df.empty else pd.DataFrame(columns=["Ay","Satış EUR Toplamı"]))
    merged = pd.merge(aylik, satis, on="Ay", how="outer").fillna(0)
    merged["Toplam EUR"] = merged["PDF EUR Toplamı"] + merged["Satış EUR Toplamı"]
    st.dataframe(merged, use_container_width=True)
    st.success(f"💶 Yıllık Genel Toplam: {round(merged['Toplam EUR'].sum(),2)} EUR")

    # Excel indir
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        merged.to_excel(writer, index=False, sheet_name="Aylik_Ozet")
        if not pdf_df.empty:
            pdf_df.to_excel(writer, index=False, sheet_name="PDF_Detay")
        if not sales_df.empty:
            sales_df.to_excel(writer, index=False, sheet_name="Satis_Detay")
    st.download_button("📥 Yıllık Birleşik Excel (Aylık+Detay)", data=out.getvalue(), file_name="yillik_otomatik_ozet.xlsx")
