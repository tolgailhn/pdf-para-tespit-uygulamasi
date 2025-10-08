 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/README.md b/README.md
index d3f5a12faa99758192ecc4ed3fc22c9249232e86..528e56217dac4ef6fd67828a8cc58bc7df59bbe9 100644
--- a/README.md
+++ b/README.md
@@ -1 +1,48 @@
-
+# PDF & Satış Analiz Aracı
+
+Bu depo, PDF dosyalarındaki para birimi tutarlarını ve satış Excel dosyalarını analiz etmek için geliştirilen Streamlit tabanlı uygulamayı içerir.
+
+## Geliştirilmiş `app.py` dosyasını üretim ortamına aktarma
+
+Aşağıdaki adımlar, burada düzeltilen `app.py` dosyasını kendi Streamlit sunucunuza veya VPS'inize taşımanıza yardımcı olur:
+
+1. **Depodaki son değişikliği çekin**  
+   Sunucunuzda ya da geliştirici bilgisayarınızda depo klasörüne girin ve güncel dosyaları alın:
+   ```bash
+   cd pdf-para-tespit-uygulamasi
+   git pull origin main
+   ```
+
+2. **Yereldeki `app.py` dosyasını kopyalayın**  
+   Eğer dosyayı manuel olarak aktarmak istiyorsanız, güncel `app.py` dosyasını SCP/SFTP ile sunucunuza gönderin:
+   ```bash
+   scp app.py user@sunucu-adresi:/path/to/pdf-para-tespit-uygulamasi/app.py
+   ```
+   > `user`, `sunucu-adresi` ve hedef yolu kendi ortamınıza göre düzenleyin.
+
+3. **Streamlit servisiniz varsa yeniden başlatın**  
+   * Streamlit Cloud kullanıyorsanız depo güncellemesi otomatik olarak yeni sürümü kullanır.  
+   * Kendi VPS'inizde çalıştırıyorsanız süreci yeniden başlatın:
+     ```bash
+     pkill streamlit  # servis arka planda çalışıyorsa
+     streamlit run app.py --server.port 8501
+     ```
+
+4. **Değişiklikleri doğrulayın**  
+   Tarayıcıda uygulamanızı açarak PDF toplamlarının doğru göründüğünü kontrol edin.
+
+## Uygulamayı çalıştırma
+
+1. Bağımlılıkları yükleyin:
+   ```bash
+   pip install -r requirements.txt
+   ```
+2. Uygulamayı başlatın:
+   ```bash
+   streamlit run app.py
+   ```
+3. Tarayıcıdan `http://localhost:8501` adresine giderek arayüzü kullanın.
+
+## Destek
+
+Bir sorunla karşılaşırsanız GitHub Issues veya e-posta üzerinden geri bildirim gönderebilirsiniz.
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
