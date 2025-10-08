# PDF Para Tespit Uygulaması

Bu depo, PDF dosyalarından para miktarlarını tespit eden örnek bir Flask uygulamasını içerir.

## Düzeltilen `app.py` dosyasını sunucuya yükleme

Yerelde güncellediğiniz `app.py` dosyasını sunucudaki projeye taşımak için aşağıdaki adımları izleyebilirsiniz:

1. **Dosyayı yerelde hazırla**  
   Düzenlediğiniz `app.py` dosyasının bilgisayarınızda bulunduğu dizini açın.

2. **Sunucuya bağlanın**  
   Sunucuya SSH ile bağlanın:
   ```bash
   ssh kullanici@sunucu-adresi
   ```

3. **Proje dizinine gidin**  
   Sunucuda oturum açtıktan sonra proje dizinine geçin:
   ```bash
   cd /path/to/pdf-para-tespit-uygulamasi
   ```

4. **Dosyayı kopyalayın**  
   Yerelden sunucuya dosya kopyalamak için `scp` kullanabilirsiniz:
   ```bash
   scp /yerel/dosya/yolu/app.py kullanici@sunucu-adresi:/path/to/pdf-para-tespit-uygulamasi/app.py
   ```
   Alternatif olarak bir SFTP istemcisi (FileZilla, WinSCP vb.) kullanarak da dosyayı sürükleyip bırakabilirsiniz.

5. **Uygulamayı yeniden başlatın (gerekirse)**  
   Uygulama bir servis olarak çalışıyorsa, dosya değişikliğinden sonra yeniden başlatmanız gerekebilir:
   ```bash
   systemctl restart pdf-para-tespit.service
   ```
   veya geliştirme sunucusu kullanıyorsanız çalıştırma komutunu tekrar verin:
   ```bash
   flask run
   ```

Bu adımlar sayesinde güncellediğiniz dosyayı sunucuya aktarıp uygulamanın düzeltmelerle çalışmasını sağlayabilirsiniz.
