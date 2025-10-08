import streamlit as st
import pdfplumber
import pandas as pd
import io
import re
from collections import defaultdict

# Desteklenen para birimleri
CURRENCIES = ["EUR", "PLN", "GBP", "SEK"]

# PDF’ten metin çıkartma fonksiyonu
def extract_text_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

# PDF metninden para birimi ve miktar yakalama
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

# Streamlit başlık
st.set_page_config(page_title="PDF Para Birimi Tarayıcı", layout="wide")
st.title("💸 PDF Para Birimi Tarayıcı & Döviz Çevirici")

# Dosya yükleme
uploaded_files = st.file_uploader("📤 PDF dosyalarını yükleyin", type="pdf", accept_multiple_files=True)

# Ayarlar
convert = st.checkbox("💱 Tutarları EUR'a çevir", value=True)
show_negative = st.checkbox("➖ Negatif değerleri göster", value=False)

# Döviz kuru girişleri
eur_rates = {
    "PLN": st.number_input("PLN → EUR kuru", min_value=0.0, value=0.22),
    "GBP": st.number_input("GBP → EUR kuru", min_value=0.0, value=1.17),
    "SEK": st.number_input("SEK → EUR kuru", min_value=0.0, value=0.084)
}

# Veri toplama
final_data = []

if uploaded_files:
    for file in uploaded_files:
        text = extract_text_from_pdf(file)
        results = find_currency_amounts(text)

        # Aynı para biriminden gelen tutarları toplamak için
        sums = defaultdict(float)
        for currency, amount in results:
            if not show_negative and amount < 0:
                continue
            sums[currency] += amount

        # Sonuçları tabloya ekle
        for currency, total_amount in sums.items():
            if currency == "EUR":
                eur_value = total_amount
            else:
                eur_value = round(total_amount * eur_rates.get(currency, 0), 2)

            final_data.append({
                "Dosya": file.name,
                "Para Birimi": currency,
                "Toplam Tutar": round(total_amount, 2),
                "EUR Karşılığı": round(eur_value, 2)
            })

    # Sonuçları göster
    if final_data:
        df = pd.DataFrame(final_data)
        st.dataframe(df)

        # Genel EUR toplam
        total_eur = sum(row["EUR Karşılığı"] for row in final_data if isinstance(row["EUR Karşılığı"], float))
        st.success(f"💶 Genel EUR Toplamı: {round(total_eur, 2)} EUR")

        # Excel indir
        excel = io.BytesIO()
        df.to_excel(excel, index=False)
        st.download_button("📥 Excel olarak indir", data=excel.getvalue(), file_name="rapor.xlsx")

        # TXT indir
        txt = df.to_csv(sep="\t", index=False)
        st.download_button("📄 TXT olarak indir", data=txt, file_name="rapor.txt")

    else:
        st.warning("Geçerli para birimi bulunamadı.")
