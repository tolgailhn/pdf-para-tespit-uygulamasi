 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/app.py b/app.py
index e16f00b0a4b439375775a374d12b56a6a92e089d..3a18aeefb91b009a6585cd1c2f0764d0e7ec1d87 100644
--- a/app.py
+++ b/app.py
@@ -10,57 +10,66 @@ from decimal import Decimal, InvalidOperation
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
     '2,572.13' -> '2572.13'
     '2.572,13' -> '2572.13'
     '490.77'   -> '490.77'
     '490,77'   -> '490.77'
     """
-    s = s.strip()
-    # önce boşluk ve para birimi yazılarını ayıkla
-    s = re.sub(r"[^\d,.\-]", "", s)
-    if s.count(",") == 1 and s.count(".") >= 1:
-        # binlik . ve ondalık , varsay → noktaları sil, virgülü noktaya çevir
-        s = s.replace(".", "")
-        s = s.replace(",", ".")
+    s = s.strip()
+    # önce boşluk ve para birimi yazılarını ayıkla
+    s = re.sub(r"[^\d,.\-]", "", s)
+
+    # Bazı PDF çıktılarında sayıların sonunda fazladan nokta/virgül olabiliyor
+    # (örn. "6,30."), bu durum ondalık kısmın düşmesine sebep oluyordu.
+    # Hem baştaki hem sondaki ayracı temizleyelim.
+    while s and s[-1] in ",.":
+        s = s[:-1]
+    while s and s[0] in ",.":
+        s = s[1:]
+
+    if s.count(",") == 1 and s.count(".") >= 1:
+        # binlik . ve ondalık , varsay → noktaları sil, virgülü noktaya çevir
+        s = s.replace(".", "")
+        s = s.replace(",", ".")
     elif s.count(",") == 1 and s.count(".") == 0:
         # sadece virgül varsa → ondalık ayırıcıdır
         s = s.replace(",", ".")
     # şimdi sadece rakam . - kalsın
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
     Genel tarama: 'EUR 490.77' gibi tüm eşleşmeleri yakalar.
     """
     results = []
     for currency in CURRENCIES:
         pattern = rf"{currency}\s?([0-9\.,]+)"
 
EOF
)
