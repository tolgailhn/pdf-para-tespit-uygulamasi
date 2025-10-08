import streamlit as st
import pdfplumber
import pytesseract
from PIL import Image
import pandas as pd
import io
import re
import requests

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
        matches = re.findall(rf"{currency}\s?[\d,]+\.\d+", text)
        for match in matches:
            amount = float(match.replace(currency, "").replace(",", "").strip())
            if amount != 0:
                results.append((currency, amount))
    return results

def convert_to_eur(currency, amount):
    if currency == "EUR":
        return amount
    try:
        url = f"https://api.exchangerate.host/convert?from={currency}&to=EUR&amount={amount}"
        response = requests.get(url).json()
        return response['result']
    except:
        return None

st.title("💸 PDF Para Birimi Tarayıcı & Döviz Çevirici")

uploaded_files = st.file_uploader("PDF dosyalarını yükleyin", type="pdf", accept_multiple_files=True)
convert = st.checkbox("Tutarları EUR'a çevir")
show_negative = st.checkbox("Negatif değerleri göster")

if uploaded_files:
    final_data = []
    for file in uploaded_files:
        text = extract_text_from_pdf(file)
        results = find_currency_amounts(text)
        file_data = []
        for currency, amount in results:
            if not show_negative and amount < 0:
                continue
            converted = convert_to_eur(currency, amount) if convert else None
            file_data.append({
                "Dosya": file.name,
                "Para Birimi": currency,
                "Tutar": amount,
                "EUR Karşılığı": round(converted, 2) if converted else "-"
            })
        final_data.extend(file_data)

    if final_data:
        df = pd.DataFrame(final_data)
        st.dataframe(df)

        # İndirme butonları
        excel = io.BytesIO()
        df.to_excel(excel, index=False)
        st.download_button("📥 Excel olarak indir", data=excel.getvalue(), file_name="rapor.xlsx")

        txt = df.to_csv(sep="\t", index=False)
        st.download_button("📄 TXT olarak indir", data=txt, file_name="rapor.txt")
    else:
        st.info("Hiç geçerli para birimi bulunamadı.")

