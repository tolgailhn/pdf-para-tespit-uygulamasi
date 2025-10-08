# PDF & Satış Analiz Aracı

Bu depo, PDF dosyalarındaki para birimi tutarlarını ve satış Excel dosyalarını analiz etmek için geliştirilen Streamlit tabanlı uygulamayı içerir.

## Geliştirilmiş `app.py` dosyasını üretim ortamına aktarma

Aşağıdaki adımlar, burada düzeltilen `app.py` dosyasını kendi Streamlit sunucunuza veya VPS'inize taşımanıza yardımcı olur:

1. **Depodaki son değişikliği çekin**  
   Sunucunuzda ya da geliştirici bilgisayarınızda depo klasörüne girin ve güncel dosyaları alın:
   ```bash
   cd pdf-para-tespit-uygulamasi
   git pull origin main
   ```

2. **Yereldeki `app.py` dosyasını kopyalayın**  
   Eğer dosyayı manuel olarak aktarmak istiyorsanız, güncel `app.py` dosyasını SCP/SFTP ile sunucunuza gönderin:
   ```bash
   scp app.py user@sunucu-adresi:/path/to/pdf-para-tespit-uygulamasi/app.py
   ```
   > `user`, `sunucu-adresi` ve hedef yolu kendi ortamınıza göre düzenleyin.

3. **Streamlit servisiniz varsa yeniden başlatın**  
   * Streamlit Cloud kullanıyorsanız depo güncellemesi otomatik olarak yeni sürümü kullanır.  
   * Kendi VPS'inizde çalıştırıyorsanız süreci yeniden başlatın:
     ```bash
     pkill streamlit  # servis arka planda çalışıyorsa
     streamlit run app.py --server.port 8501
     ```

4. **Değişiklikleri doğrulayın**  
   Tarayıcıda uygulamanızı açarak PDF toplamlarının doğru göründüğünü kontrol edin.

## Uygulamayı çalıştırma

1. Bağımlılıkları yükleyin:
   ```bash
   pip install -r requirements.txt
   ```
2. Uygulamayı başlatın:
   ```bash
   streamlit run app.py
   ```
3. Tarayıcıdan `http://localhost:8501` adresine giderek arayüzü kullanın.

## Destek

Bir sorunla karşılaşırsanız GitHub Issues veya e-posta üzerinden geri bildirim gönderebilirsiniz.
