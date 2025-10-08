import streamlit as st
import pdfplumber
import pandas as pd
import io
import re
from collections import defaultdict

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

def find_currency_amounts(text):
    results = []
    for currency in CURRENCIES:
        pattern = rf"{currency}\s?[\d,]+\.\d+"
        matches = re.findall(pattern, text)
        for match in matches:
            try:
                amount = float(match.replace(currency, "").replace(",", "").strip())
                results.append((currency, amount))
            except:
                continue
    return results

with st.expander("📄 PDF Analizi (EUR/PLN/GBP/SEK tespiti ve EUR'a çeviri)", expanded=True):
    uploaded_pdfs = st.file_uploader(
        "PDF dosyalarını yükleyin", type="pdf", accept_multiple_files=True, key="pdfs"
    )

    convert = st.checkbox("💱 Yalnızca PLN / GBP / SEK değerlerini EUR'a çevir", value=True, key="pdf_convert")
    show_negative = st.checkbox("➖ Negatif değerleri göster", value=False, key="pdf_neg")

    eur_rates = {
        "PLN": st.number_input("PLN → EUR kuru", min_value=0.0, value=0.22, key="pln_rate"),
        "GBP": st.number_input("GBP → EUR kuru", min_value=0.0, value=1.17, key="gbp_rate"),
        "SEK": st.number_input("SEK → EUR kuru", min_value=0.0, value=0.084, key="sek_rate")
    }

    pdf_rows = []

    if uploaded_pdfs:
        for file in uploaded_pdfs:
            text = extract_text_from_pdf(file)
            raw_results = find_currency_amounts(text)

            # Aynı (para birimi, tutar) tekrarlarını kaldır
            unique_results = set(raw_results)

            # Para birimi bazında toplam
            sums = defaultdict(float)
            for currency, amount in unique_results:
                if not show_negative and amount < 0:
                    continue
                sums[currency] += amount

            # Sonuç satırları
            for currency, total_amount in sums.items():
                if currency == "EUR":
                    eur_value = total_amount  # EUR'u çevirmeyiz
                else:
                    eur_value = round(total_amount * eur_rates.get(currency, 0), 2) if convert else total_amount

                pdf_rows.append({
                    "Dosya": file.name,
                    "Para Birimi": currency,
                    "Toplam Tutar": round(total_amount, 2),
                    "EUR Karşılığı": round(eur_value, 2)
                })

        if pdf_rows:
            pdf_df = pd.DataFrame(pdf_rows)
            st.dataframe(pdf_df, use_container_width=True)

            total_eur = sum(
                row["EUR Karşılığı"] for row in pdf_rows if isinstance(row["EUR Karşılığı"], (int, float, float))
            )
            st.success(f"💶 PDF'lerden Genel EUR Toplamı: {round(total_eur, 2)} EUR")

            # Excel indir
            excel_buff = io.BytesIO()
            pdf_df.to_excel(excel_buff, index=False)
            st.download_button("📥 PDF Sonuçlarını Excel olarak indir", data=excel_buff.getvalue(), file_name="pdf_rapor.xlsx")

            # TXT indir
            txt = pdf_df.to_csv(sep="\t", index=False)
            st.download_button("📄 PDF Sonuçlarını TXT olarak indir", data=txt, file_name="pdf_rapor.txt")
        else:
            st.info("PDF'lerde geçerli para birimi bulunamadı.")

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

# Kullanıcıya esneklik: Otomatik bulamazsa seçsin
col1, col2 = st.columns(2)
with col1:
    custom_price_col = st.text_input("Item Price sütun adı (otomatik: Item Price)", value="Item Price")
with col2:
    custom_qty_col = st.text_input("Dispatched Quantity sütun adı (otomatik: Dispatched Quantity)", value="Dispatched Quantity")

def coerce_euro_number(x):
    """
    'EUR 12,34' / '12.34' / '12,34' gibi değerleri floats'a çevirir.
    Varsayılan olarak virgülü ondalık ayırıcı kabul eder.
    """
    if pd.isna(x):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    # Para birimi yazılarını temizle
    s = re.sub(r"[€EUReur£GBPgbpPLNplnSEKsek\s]", "", s)
    # Binlik/ondalık düzeltme: önce nokta ve virgülü normalize edelim
    # Örn: "1.234,56" -> "1234,56" -> "1234.56"
    if s.count(",") == 1 and s.count(".") >= 1:
        s = s.replace(".", "")
        s = s.replace(",", ".")
    elif s.count(",") == 1 and s.count(".") == 0:
        s = s.replace(",", ".")
    # Kalan harfleri ayıkla
    s = re.sub(r"[^0-9.\-]", "", s)
    try:
        return float(s)
    except:
        return None

sales_rows = []
summary_cards = {}

if sales_files:
    all_frames = []
    for f in sales_files:
        # Dosya tipi
        if f.name.lower().endswith(".csv"):
            df = pd.read_csv(f)
        else:
            df = pd.read_excel(f)

        # Sütun isimlerini case-insensitive normalleştir
        df_cols_map = {c: c for c in df.columns}
        lower_map = {c.lower(): c for c in df.columns}

        # Item Price sütununu tespit et
        price_col_guess = None
        for key in [custom_price_col, "Item Price", "item price", "price", "itemprice", "r1"]:
            if key.lower() in lower_map:
                price_col_guess = lower_map[key.lower()]
                break

        # Dispatched Quantity sütununu tespit et (opsiyonel)
        qty_col_guess = None
        for key in [custom_qty_col, "Dispatched Quantity", "dispatched quantity", "quantity", "qty", "p1"]:
            if key.lower() in lower_map:
                qty_col_guess = lower_map[key.lower()]
                break

        # Fiyat kolonunu zorunlu sayalım (yoksa uyarı ver)
        if not price_col_guess:
            st.warning(f"⚠️ {f.name} içinde '{custom_price_col}' / 'Item Price' sütunu bulunamadı. Lütfen sütun adını doğru girin.")
            continue

        df["_price_num"] = df[price_col_guess].apply(coerce_euro_number)
        price_sum = df["_price_num"].dropna().sum()

        # Satış adedi (satır sayımı): fiyatı sayılabilen satır sayısı
        sales_count_rows = int(df["_price_num"].dropna().shape[0])

        # Dispatched Quantity varsa onu da topla
        qty_sum = None
        if qty_col_guess:
            df["_qty_num"] = pd.to_numeric(df[qty_col_guess], errors="coerce")
            qty_sum = int(df["_qty_num"].dropna().sum())

        # Bu dosyanın özeti
        sales_rows.append({
            "Dosya": f.name,
            "Toplam EUR (Item Price)": round(float(price_sum), 2) if pd.notna(price_sum) else 0.0,
            "Satış Adedi (Satır sayımı)": sales_count_rows,
            "Satış Adedi (Dispatched Quantity toplamı)": qty_sum if qty_sum is not None else "-"
        })

        # Birleştirme için sakla
        keep_cols = [price_col_guess]
        if qty_col_guess:
            keep_cols.append(qty_col_guess)
        df_keep = df[keep_cols].copy()
        df_keep.insert(0, "Kaynak Dosya", f.name)
        all_frames.append(df_keep)

    # Sonuç tablosu (dosya bazlı özet)
    if sales_rows:
        sales_df = pd.DataFrame(sales_rows)
        st.subheader("📦 Dosya Bazlı Satış Özeti")
        st.dataframe(sales_df, use_container_width=True)

        # Genel toplamlar
        total_sales_eur = float(sales_df["Toplam EUR (Item Price)"].sum())
        total_sales_count_rows = int(sales_df["Satış Adedi (Satır sayımı)"].replace("-", 0).sum())

        # Dispatched Quantity toplamını ayrıca hesapla
        if "Satış Adedi (Dispatched Quantity toplamı)" in sales_df.columns:
            dq_col = sales_df["Satış Adedi (Dispatched Quantity toplamı)"]
            total_dq = int(pd.to_numeric(dq_col.replace("-", 0)).sum())
        else:
            total_dq = 0

        c1, c2, c3 = st.columns(3)
        with c1:
            st.success(f"💶 Genel Toplam Satış (EUR): **{round(total_sales_eur, 2)}**")
        with c2:
            st.info(f"🧾 Satış Adedi (satır sayımı): **{total_sales_count_rows}**")
        with c3:
            st.info(f"📦 Satış Adedi (Dispatched Quantity): **{total_dq}**")

        # Detay dökümleri indir
        if all_frames:
            merged = pd.concat(all_frames, ignore_index=True)

            # Excel indir (özet + detay)
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine="openpyxl") as writer:
                sales_df.to_excel(writer, index=False, sheet_name="Ozet")
                merged.to_excel(writer, index=False, sheet_name="Detay")
            st.download_button("📥 Satış Özeti + Detayı (Excel)", data=out.getvalue(), file_name="satis_ozet_detay.xlsx")

            # TXT indir (özet)
            txt2 = sales_df.to_csv(sep="\t", index=False)
            st.download_button("📄 Satış Özeti (TXT)", data=txt2, file_name="satis_ozet.txt")
    else:
        if sales_files:
            st.warning("Yüklenen Excel/CSV dosyalarında uygun sütunlar bulunamadı veya tüm satırlar boş/uyumsuz görünüyor.")
        else:
            st.info("Henüz satış dosyası yüklemediniz.")
