import streamlit as st
import pdfplumber
import pandas as pd
import io
import re
from collections import defaultdict

# Desteklenen para birimleri
CURRENCIES = ["EUR", "PLN", "GBP", "SEK"]

# PDF metni çıkartma
def extract_text_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

# Para birimi ve miktar bulma
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

# Arayüz ayarları
st.set_page_config(page_title="PDF Para Birimi Tarayıcı", layout="wide")
st.title("💸 PDF Para Birimi Tarayıcı & Döviz Çevirici")

uploaded_files = st.file_uploader("📤 PDF dosyalarını yükleyin", type="pdf", accept_multiple_files=True)
convert = st.checkbox("💱 Yalnızca PLN / GBP / SEK değerlerini EUR'a çevir", value=True)
show_negative = st.checkbox("➖ Negatif değerleri göster", value=False)

# Döviz kurları kullanıcı girişi
eur_rates = {
    "PLN": st.number_input("PLN → EUR kuru", min_value=0.0, value=0.22),
    "GBP": st.number_input("GBP → EUR kuru", min_value=0.0, value=1.17),
    "SEK": st.number_input("SEK → EUR kuru", min_value=0.0, value=0.084)
}

final_data = []

if uploaded_files:
    for file in uploaded_files:
        text = extract_text_from_pdf(file)
        results = find_currency_amounts(text)

        # Aynı para birimindeki değerleri topla
        sums = defaultdict(float)
        for currency, amount in results:
            if not show_negative and amount < 0:
                continue
            sums[currency] += amount

        # Dosya bazlı sonuç ekle
        for currency, total_amount in sums.items():
            if currency == "EUR":  # EUR değerini asla çevirme
                eur_value = total_amount
            else:
                eur_value = round(total_amount * eur_rates.get(currency, 0), 2) if convert else total_amount

            final_data.append({
                "Dosya": file.name,
                "Para Birimi": currency,
                "Toplam Tutar": round(total_amount, 2),
                "EUR Karşılığı": round(eur_value, 2)
            })

    # Sonuç tablosu
    if final_data:
        df = pd.DataFrame(final_data)
        st.dataframe(df, use_container_width=True)

        # Genel toplam (sadece EUR karşılıkları toplanır)
        total_eur = sum(
            row["EUR Karşılığı"] for row in final_data if isinstance(row["EUR Karşılığı"], (int, float))
        )
        st.success(f"💶 Genel EUR Toplamı: {round(total_eur, 2)} EUR")

        # Excel indir
        excel = io.BytesIO()
        df.to_excel(excel, index=False)
        st.download_button("📥 Excel olarak indir", data=excel.getvalue(), file_name="rapor.xlsx")

        # TXT indir
        txt = df.to_csv(sep="\t", index=False)
        st.download_button("📄 TXT olarak indir", data=txt, file_name="rapor.txt")

    else:
        st.warning("⚠️ Geçerli para birimi bulunamadı.")
