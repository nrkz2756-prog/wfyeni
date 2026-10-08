@echo off
:: ═══════════════════════════════════════════════════
::  FORZA - WOLFTEAM | Güvenli VDS Çıkış Scripti
:: ═══════════════════════════════════════════════════
::
::  Bu script RDP bağlantısını keser AMA masaüstü
::  oturumu aktif kalır. Programlar kesintisiz
::  çalışmaya devam eder.
::
::  ÖNEMLİ: RDP'den çıkarken X butonuna basmayın!
::  Bunun yerine bu scripti çalıştırın.
::
::  Admin olarak çalıştırılmalıdır.
:: ═══════════════════════════════════════════════════

echo.
echo  ╔═══════════════════════════════════════════╗
echo  ║  🐺 FORZA - WOLFTEAM                     ║
echo  ║  Güvenli VDS Çıkış                        ║
echo  ╚═══════════════════════════════════════════╝
echo.
echo  RDP bağlantısı kesilecek ama masaüstü
echo  aktif kalacak. Programlar çalışmaya
echo  devam edecek.
echo.

:: Mevcut oturum adını kullanarak çık
:: %SESSIONNAME% = RDP oturum adı (ör: RDP-Tcp#0)
if defined SESSIONNAME (
    echo  Oturum: %SESSIONNAME%
    echo  Kesiliyor...
    %windir%\System32\tscon.exe %SESSIONNAME% /dest:console
    if %errorlevel% equ 0 (
        echo  Başarılı! Masaüstü aktif kalacak.
    ) else (
        echo  tscon başarısız, alternatif deneniyor...
        :: Alternatif: oturum ID ile dene
        for /f "tokens=3" %%i in ('query session %USERNAME% 2^>nul ^| findstr /i "Active"') do (
            echo  Oturum ID: %%i
            %windir%\System32\tscon.exe %%i /dest:console
        )
    )
) else (
    echo  HATA: SESSIONNAME bulunamadı!
    echo  Bu script sadece RDP oturumunda çalışır.
    pause
)
