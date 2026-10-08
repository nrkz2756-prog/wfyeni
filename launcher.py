import psutil
import subprocess
import time
import win32gui
import win32con
import win32api
import comtypes
import comtypes.client
from datetime import datetime
import os
import sys
import pyperclip
import ctypes
import ctypes.wintypes

# Exe'nin yanındaki klasörü baz al (PyInstaller veya normal çalışma)
BASE_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))

# comtypes gen dizinini yazılabilir temp klasörüne yönlendir
import tempfile
_comtypes_gen_dir = os.path.join(tempfile.gettempdir(), "comtypes_gen")
os.makedirs(_comtypes_gen_dir, exist_ok=True)
comtypes.client.gen_dir = _comtypes_gen_dir

# Eğer frozen exe içindeyse, önceden üretilmiş gen dosyalarını kopyala
if getattr(sys, 'frozen', False):
    _src = os.path.join(sys._MEIPASS, "comtypes", "gen")
    if os.path.isdir(_src):
        import shutil
        for _f in os.listdir(_src):
            _dst = os.path.join(_comtypes_gen_dir, _f)
            if not os.path.exists(_dst):
                try:
                    shutil.copy2(os.path.join(_src, _f), _dst)
                except Exception:
                    pass

# UI Automation COM arayüzü
comtypes.client.GetModule("UIAutomationCore.dll")
from comtypes.gen.UIAutomationClient import (
    CUIAutomation,
    IUIAutomation,
    UIA_EditControlTypeId,
    UIA_ButtonControlTypeId,
    TreeScope_Descendants,
)

# UIA modül referansı (fonksiyon içi import'u önler → ~1ms/çağrı kazanım)
import comtypes.gen.UIAutomationClient as _uiac

# ── AYARLAR ──────────────────────────────────────
LAUNCHER_PATH = os.path.join(BASE_DIR, "Wolfteam Turkiye", "NyxLauncher.exe")
LAUNCHER_TITLE = "Softnyx Game Launcher"
WOLFTEAM_EXE   = "WolfTeam.exe"
ACCOUNTS_FILE  = os.path.join(BASE_DIR, "accounts.txt")
LOG_FILE       = os.path.join(BASE_DIR, "launcher.log")
SUCCESS_FILE   = os.path.join(BASE_DIR, "success_accounts.txt")

# Hata anahtar kelimeleri (modül seviyesinde — her çağrıda yeniden oluşturmaz)
_ERROR_KEYWORDS = ("hatalı", "hatali", "incorrect", "invalid", "wrong",
                   "başarısız", "basarisiz", "error", "failed", "geçersiz",
                   "gecersiz", "bulunamadı", "bulunamadi", "yanlış", "yanlis")

# ══════════════════════════════════════════════════
# UIPI BYPASS: Admin pencerelerine mesaj göndermek için
# ══════════════════════════════════════════════════
_MSGFLT_ALLOW = 1
_uipi_allowed = set()  # (hwnd, msg) çiftlerini takip et

def _allow_message(hwnd, msg):
    """Belirli pencere için belirli mesaja UIPI izni ver."""
    key = (hwnd, msg)
    if key not in _uipi_allowed:
        try:
            ctypes.windll.user32.ChangeWindowMessageFilterEx(
                hwnd, msg, _MSGFLT_ALLOW, None
            )
            _uipi_allowed.add(key)
        except Exception:
            pass

def _allow_all_messages(hwnd):
    """Launcher penceresine gönderilebilecek tüm mesaj türlerini izinle."""
    for msg in (
        win32con.WM_KEYDOWN, win32con.WM_KEYUP,
        win32con.WM_CHAR, win32con.WM_SETTEXT,
        win32con.WM_LBUTTONDOWN, win32con.WM_LBUTTONUP,
        win32con.WM_CLOSE,
    ):
        _allow_message(hwnd, msg)

def _safe_post(hwnd, msg, wparam, lparam):
    """PostMessage wrapper — Access Denied alırsa UIPI bypass uygula ve tekrar dene."""
    try:
        win32gui.PostMessage(hwnd, msg, wparam, lparam)
    except Exception as e:
        if getattr(e, 'winerror', 0) == 5 or 'Access' in str(e):
            _allow_message(hwnd, msg)
            try:
                win32gui.PostMessage(hwnd, msg, wparam, lparam)
            except Exception:
                pass
        # Diğer hataları sessizce yut (pencere kapanmış olabilir)

# ══════════════════════════════════════════════════
# PERFORMANS: Tek UIA nesnesi (COM reuse — donma önleyici)
# ══════════════════════════════════════════════════
_uia_instance = None

def get_uia():
    """Tek bir UIA COM nesnesi döndür. Her seferinde yeni oluşturmaz → donma önlenir."""
    global _uia_instance
    if _uia_instance is None:
        _uia_instance = comtypes.client.CreateObject(
            CUIAutomation, interface=IUIAutomation
        )
    return _uia_instance

def reset_uia():
    """UIA nesnesini sıfırla (hata durumunda yeniden oluşturulması için)."""
    global _uia_instance
    _uia_instance = None

# ══════════════════════════════════════════════════
# PERFORMANS: Buffered Log (dosya açıp kapatmaz)
# ══════════════════════════════════════════════════
_log_buffer = []
_log_flush_time = 0

def log(msg):
    global _log_flush_time
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} - {msg}"
    _log_buffer.append(line)
    now = time.monotonic()
    if len(_log_buffer) >= 20 or (now - _log_flush_time) > 2.0:
        _flush_log()
        _log_flush_time = now

def _flush_log():
    global _log_buffer
    if not _log_buffer:
        return
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("\n".join(_log_buffer) + "\n")
    except Exception:
        pass
    _log_buffer = []

# ══════════════════════════════════════════════════
# PROCESS — Optimize edilmiş (psutil cache)
# ══════════════════════════════════════════════════
def _find_processes(name_lower):
    """Verilen isme sahip tüm process'leri bul (tek tarama)."""
    found = []
    for p in psutil.process_iter(['name', 'pid']):
        try:
            if (p.info.get('name') or "").lower() == name_lower:
                found.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return found

def kill_launcher():
    procs = _find_processes("nyxlauncher.exe")
    for p in procs:
        try:
            p.kill()
        except Exception:
            pass
    if procs:
        time.sleep(0.15)

def close_process(name):
    for p in _find_processes(name.lower()):
        try:
            p.kill()
        except Exception:
            pass

def _is_process_running(name):
    """Belirtilen isimde çalışan bir süreç var mı kontrol et.
    WolfTeam için geniş arama yapar — tam eşleşme + kısmi eşleşme."""
    name_lower = name.lower().replace(".exe", "")  # "wolfteam"
    for p in psutil.process_iter(['name']):
        try:
            pname = (p.info.get('name') or "").lower()
            # Tam eşleşme VEYA kısmi eşleşme (wolfteam.bin, WolfTeamTR.exe vb.)
            if name_lower in pname:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False

# ── PENCERE ──────────────────────────────────────
def find_hwnd():
    """
    Launcher penceresini bul — ALT-METİN ARAMASI (substring match).
    FindWindow kullanılamaz çünkü başlık "v2.1" gibi ekler içerebilir.
    """
    found = []
    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and LAUNCHER_TITLE in win32gui.GetWindowText(hwnd):
            found.append(hwnd)
    win32gui.EnumWindows(cb, None)
    return found[0] if found else None

def activate_hwnd(hwnd):
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass
    # UIPI: İlk aktivasyonda tüm mesajlara izin ver
    _allow_all_messages(hwnd)

def ensure_task_exists():
    """Uyumluluk için boş bırakıldı — artık doğrudan başlatma kullanılıyor."""
    pass

def start_launcher():
    log("Launcher başlatılıyor (Doğrudan NyxLauncher.exe)...")
    if not os.path.isfile(LAUNCHER_PATH):
        log(f"HATA: NyxLauncher bulunamadı: {LAUNCHER_PATH}")
        return False
    try:
        launcher_dir = os.path.dirname(LAUNCHER_PATH)
        subprocess.Popen(
            [LAUNCHER_PATH],
            cwd=launcher_dir,
            creationflags=0x00000008  # DETACHED_PROCESS
        )
    except Exception as e:
        log(f"HATA: Launcher başlatılamadı: {e}")
        return False
    for _ in range(30):   # max 3sn (30 × 0.1)
        time.sleep(0.1)   # eski: 0.15
        if find_hwnd():
            time.sleep(0.05)  # eski: 0.15
            log("Launcher açıldı.")
            return True
    log("HATA: Launcher penceresi açılmadı!")
    return False

# ── UI AUTOMATION ────────────────────────────────
def get_edit_fields(hwnd):
    """
    Verilen HWND altındaki tüm Edit alanlarını döndür.
    İlk = kullanıcı adı, ikinci = şifre (tipik launcher düzeni).
    """
    uia = get_uia()
    elem = uia.ElementFromHandle(hwnd)

    cond = uia.CreatePropertyCondition(
        30003,  # UIA_ControlTypePropertyId
        UIA_EditControlTypeId
    )
    result = elem.FindAll(TreeScope_Descendants, cond)
    fields = [result.GetElement(i) for i in range(result.Length)]
    return fields

def set_field_value(field, text):
    """
    UI Automation Value pattern ile alana yaz.
    Desteklemiyorsa Win32 API ile fallback.
    """
    try:
        val_pat = field.GetCurrentPattern(10002)  # UIA_ValuePatternId
        if val_pat:
            vp = val_pat.QueryInterface(_uiac.IUIAutomationValuePattern)
            vp.SetValue(text)
            return True
    except Exception:
        pass

    # Fallback: Win32 API ile doğrudan yaz (VDS uyumlu)
    try:
        native = int(field.CurrentNativeWindowHandle)
        if native:
            win32gui.SendMessage(native, win32con.WM_SETTEXT, 0, "")
            win32gui.SendMessage(native, win32con.WM_SETTEXT, 0, text)
            return True
    except Exception as e:
        log(f"Alan yazma hatası (WM_SETTEXT): {e}")
        return False

def _blind_vds_write(hwnd, text):
    """Körleme VDS modunda clipboard ile Paste simülasyonu."""
    try:
        pyperclip.copy(text)
        time.sleep(0.015)
        
        # CTRL + A
        _safe_post(hwnd, win32con.WM_KEYDOWN, win32con.VK_CONTROL, 0)
        _safe_post(hwnd, win32con.WM_KEYDOWN, ord('A'), 0)
        _safe_post(hwnd, win32con.WM_KEYUP, ord('A'), 0)
        _safe_post(hwnd, win32con.WM_KEYUP, win32con.VK_CONTROL, 0)
        time.sleep(0.015)
        
        # CTRL + V
        _safe_post(hwnd, win32con.WM_KEYDOWN, win32con.VK_CONTROL, 0)
        _safe_post(hwnd, win32con.WM_KEYDOWN, ord('V'), 0)
        _safe_post(hwnd, win32con.WM_KEYUP, ord('V'), 0)
        _safe_post(hwnd, win32con.WM_KEYUP, win32con.VK_CONTROL, 0)
        time.sleep(0.015)
    except Exception:
        pass

def send_enter(hwnd, edit_field=None):
    """
    Enter gönder — masaüstü durumuna göre otomatik yöntem seç:
    1) keybd_event  — aktif masaüstünde (en hızlı)
    2) PostMessage  — edit alanına (VDS uyumlu)
    3) PostMessage  — ana pencereye (son çare)
    """
    # Pencere ön planda mı kontrol et
    is_foreground = False
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        is_foreground = (win32gui.GetForegroundWindow() == hwnd)
    except Exception:
        pass

    # 1) Masaüstü aktif → keybd_event (en hızlı)
    if is_foreground:
        try:
            win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
            time.sleep(0.005)  # eski: 0.01
            win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
            return True
        except Exception:
            pass

    # 2) VDS modu → PostMessage doğrudan edit alanına
    if edit_field:
        try:
            native = int(edit_field.CurrentNativeWindowHandle)
            if native:
                _safe_post(native, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0x001C0001)
                time.sleep(0.005)
                _safe_post(native, win32con.WM_KEYUP, win32con.VK_RETURN, 0xC01C0001)
                return True
        except Exception:
            pass

    # 3) Son çare → PostMessage ana pencereye
    try:
        _safe_post(hwnd, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0x001C0001)
        time.sleep(0.005)
        _safe_post(hwnd, win32con.WM_KEYUP, win32con.VK_RETURN, 0xC01C0001)
        return True
    except Exception:
        return False


def click_login_button(hwnd, edit_field=None):
    """Login / Giriş butonunu bul ve tıkla. Buton yoksa Enter gönder."""
    try:
        uia = get_uia()
        elem = uia.ElementFromHandle(hwnd)
        cond = uia.CreatePropertyCondition(30003, UIA_ButtonControlTypeId)
        result = elem.FindAll(TreeScope_Descendants, cond)
        buttons = [result.GetElement(i) for i in range(result.Length)]
        for btn in buttons:
            name = (btn.CurrentName or "").lower()
            if any(k in name for k in ("login", "giriş", "oyna", "play", "start", "giris", "sign")):
                    try:
                        inv = btn.GetCurrentPattern(10004)  # InvokePattern
                        if inv:
                            inv.QueryInterface(_uiac.IUIAutomationInvokePattern).Invoke()
                            return True
                    except Exception:
                        pass
                        
                    # 2) VDS için Körleme Koordinat Tıkı (Blind Click)
                    try:
                        rect = btn.CurrentBoundingRectangle
                        if rect and rect.right > rect.left:
                            cx = (rect.left + rect.right) // 2
                            cy = (rect.top + rect.bottom) // 2
                            client_pt = win32gui.ScreenToClient(hwnd, (cx, cy))
                            lparam = (client_pt[1] << 16) | (client_pt[0] & 0xFFFF)
                            _safe_post(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
                            time.sleep(0.01)
                            _safe_post(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
                            return True
                    except Exception:
                        pass
                        
        # Buton bulunamazsa Enter gönder
        return send_enter(hwnd, edit_field)
    except Exception as e:
        log(f"Buton tıklama hatası: {e}")
        return send_enter(hwnd, edit_field)

# ── HESAPLAR ─────────────────────────────────────
def get_accounts():
    accounts = []
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith(";") or line == "username:password":
                    continue
                if ":" not in line:
                    continue
                user, pwd = line.split(":", 1)
                user, pwd = user.strip(), pwd.strip()
                if user and pwd:
                    accounts.append((user, pwd))
    except FileNotFoundError:
        log(f"HATA: {ACCOUNTS_FILE} bulunamadı!")
    return accounts

def save_success(username, password):
    with open(SUCCESS_FILE, "a", encoding="utf-8") as f:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"{ts} - {username}:{password}\n")

# ══════════════════════════════════════════════════
# GİRİŞ DENEMESİ — Optimize + Anti-Freeze
# ══════════════════════════════════════════════════
def check_login_error(hwnd):
    """
    Launcher penceresinde hata mesajı var mı?
    UIA tek instance kullanır (donma önleyici).
    """
    try:
        uia = get_uia()
        elem = uia.ElementFromHandle(hwnd)
        cond = uia.CreatePropertyCondition(30003, 50020)  # UIA_TextControlTypeId
        result = elem.FindAll(TreeScope_Descendants, cond)
        for i in range(result.Length):
            try:
                el = result.GetElement(i)
                name = (el.CurrentName or "").lower()
                val  = ""
                try:
                    vp = el.GetCurrentPattern(10002)
                    if vp:
                        vp2 = vp.QueryInterface(_uiac.IUIAutomationValuePattern)
                        val = (vp2.CurrentValue or "").lower()
                except Exception:
                    pass
                combined = name + " " + val
                if any(k in combined for k in _ERROR_KEYWORDS):
                    return True
            except Exception:
                pass
    except Exception:
        reset_uia()
    return False

def dismiss_error_dialog(hwnd):
    """
    Hata diyaloğundaki Tamam butonuna MUTLAKA basar.
    5 farklı yöntem dener — en az biri çalışacak.
    """
    # ═══ YÖNTEM 1: UIA ile "Tamam" / "OK" butonunu bul ve tıkla ═══
    try:
        uia = get_uia()
        elem = uia.ElementFromHandle(hwnd)
        btn_cond = uia.CreatePropertyCondition(30003, UIA_ButtonControlTypeId)
        buttons = elem.FindAll(TreeScope_Descendants, btn_cond)
        for i in range(buttons.Length):
            try:
                btn = buttons.GetElement(i)
                btn_name = (btn.CurrentName or "").lower().strip()
                if btn_name in ("tamam", "ok", "okay", "evet", "yes", "kapat", "close"):
                    # InvokePattern ile tıkla
                    try:
                        invoke = btn.GetCurrentPattern(10000)  # UIA_InvokePatternId
                        if invoke:
                            ip = invoke.QueryInterface(_uiac.IUIAutomationInvokePattern)
                            ip.Invoke()
                            time.sleep(0.02)
                            return True
                    except Exception:
                        pass
                    # Alternatif: butonun native handle'ına BM_CLICK gönder
                    try:
                        btn_hwnd = int(btn.CurrentNativeWindowHandle)
                        if btn_hwnd:
                            BM_CLICK = 0x00F5
                            _safe_post(btn_hwnd, BM_CLICK, 0, 0)
                            time.sleep(0.02)
                            return True
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception:
        pass

    # ═══ YÖNTEM 2: Ayrı hata pencerelerini bul ve kapat ═══
    for title in ("Error", "Hata", "Uyarı", "Warning", "Bilgi", "Information",
                  "Softnyx Game Launcher"):
        try:
            err_hwnd = win32gui.FindWindow(None, title)
            if err_hwnd and err_hwnd != hwnd and win32gui.IsWindowVisible(err_hwnd):
                _force_close_window(err_hwnd)
                time.sleep(0.03)
        except Exception:
            pass

    # ═══ YÖNTEM 3: keybd_event ile ENTER (donanım seviyesi) ═══
    try:
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.01)
        win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
        time.sleep(0.005)
        win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.015)
    except Exception:
        pass

    # ═══ YÖNTEM 4: PostMessage ile ENTER (mesaj seviyesi) ═══
    try:
        _safe_post(hwnd, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0x001C0001)
        _safe_post(hwnd, win32con.WM_KEYUP, win32con.VK_RETURN, 0xC01C0001)
        time.sleep(0.015)
    except Exception:
        pass

    # ═══ YÖNTEM 5: Varsayılan butona BM_CLICK ═══
    try:
        # DM_GETDEFID ile varsayılan buton ID'sini al
        DM_GETDEFID = 0x0400
        result = win32gui.SendMessage(hwnd, DM_GETDEFID, 0, 0)
        if result:
            btn_id = result & 0xFFFF
            btn_hwnd = win32gui.GetDlgItem(hwnd, btn_id)
            if btn_hwnd:
                BM_CLICK = 0x00F5
                _safe_post(btn_hwnd, BM_CLICK, 0, 0)
    except Exception:
        pass

    return True

def _force_close_window(err_hwnd):
    """Pencereye Escape, Enter ve Close sinyallerini art arda yollar."""
    _allow_all_messages(err_hwnd)
    try:
        _safe_post(err_hwnd, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
        _safe_post(err_hwnd, win32con.WM_KEYUP, win32con.VK_RETURN, 0)
        time.sleep(0.01)
        _safe_post(err_hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
        _safe_post(err_hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)
        time.sleep(0.01)
        _safe_post(err_hwnd, win32con.WM_CLOSE, 0, 0)
        return True
    except Exception:
        return False

def try_login(username, password):
    """
    Launcher'ı KAPATMADAN giriş dene.
    
    *** ANTİ-FREEZE: Tüm UIA çağrıları try/except + timeout korumalı ***
    """
    # Launcher yoksa başlat
    hwnd = find_hwnd()
    if not hwnd:
        kill_launcher()
        if not start_launcher():
            return False
        hwnd = find_hwnd()

    if not hwnd:
        log("Pencere bulunamadı!")
        return False

    activate_hwnd(hwnd)

    # Edit alanlarını bul — bulunamazsa tekrar dene
    fields = []
    for _retry in range(20):  # max 0.6 sn (0.03s × 20)
        try:
            fields = get_edit_fields(hwnd)
        except Exception as e:
            if _retry == 19:
                log(f"UIA edit alanı hatası: {e}")
                reset_uia()
            fields = []
        if len(fields) >= 2:
            break
        time.sleep(0.03)

    # Alanlar bulunamadıysa → Giriş formu kaybolmuş, launcher'ı yeniden başlat
    if len(fields) < 2:
        log("⚠ Giriş alanları bulunamadı — launcher yeniden başlatılıyor...")
        reset_uia()
        kill_launcher()
        time.sleep(0.5)
        if not start_launcher():
            return False
        hwnd = find_hwnd()
        if not hwnd:
            return False
        activate_hwnd(hwnd)
        # Tekrar dene
        for _retry in range(30):  # biraz daha uzun bekle
            try:
                fields = get_edit_fields(hwnd)
            except Exception:
                fields = []
            if len(fields) >= 2:
                break
            time.sleep(0.05)

    if len(fields) >= 2:
        # ---- UIA MODU ----
        set_field_value(fields[0], username)
        set_field_value(fields[1], password)
        if not click_login_button(hwnd, fields[1]):
            log(f"✗ BAŞARISIZ (login butonuna basılamadı): {username}")
            return False
    else:
        # ---- VDS KÖRLEME MODU (AHK Mantığı) ----
        log(f"VDS KÖRLEME moduna geçiliyor: {username}")
        
        # 1. Launcher pencere boyutlarını al
        rect = win32gui.GetWindowRect(hwnd)
        w = rect[2] - rect[0]
        h = rect[3] - rect[1]
        
        # Username koordinatları (AHK'daki gibi %30 X, %45 Y)
        ux = int(w * 0.3)
        uy = int(h * 0.45)
        lparam = (uy << 16) | (ux & 0xFFFF)
        
        # Oraya tıkla
        _safe_post(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
        time.sleep(0.02)
        _safe_post(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
        time.sleep(0.05)
        
        # Username yaz (Clipboard ile)
        _blind_vds_write(hwnd, username)
        
        # TAB tuşuna basıp şifre alanına geç
        _safe_post(hwnd, win32con.WM_KEYDOWN, win32con.VK_TAB, 0)
        _safe_post(hwnd, win32con.WM_KEYUP, win32con.VK_TAB, 0)
        time.sleep(0.05)
        
        # Password yaz
        _blind_vds_write(hwnd, password)
        
        # Enter tuşuna bas (Login)
        _safe_post(hwnd, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
        _safe_post(hwnd, win32con.WM_KEYUP, win32con.VK_RETURN, 0)
        time.sleep(0.05)

    # ══════════════════════════════════════════════
    # Sonucu bekle — ESKİ HIZLI DÖNGÜ (wfes ayarları)
    # ══════════════════════════════════════════════
    for i in range(100):  # 35×0.02 + 65×0.05 = 3.95 sn max
        if i < 35:
            time.sleep(0.02)
        else:
            time.sleep(0.05)

        hwnd2 = find_hwnd()
        if not hwnd2:
            # Pencere bulunamadı — launcher gerçekten kapandı mı?
            # İlk kontrol: hemen tekrar bak (geçici kaybolma olabilir)
            time.sleep(0.05)
            hwnd2 = find_hwnd()
            if hwnd2:
                continue  # pencere geri geldi, devam et
            
            # Pencere yok — hızlı WolfTeam doğrulaması (1 kez process tarama)
            if _is_process_running(WOLFTEAM_EXE):
                log(f"✓ BAŞARILI GİRİŞ (doğrulandı): {username}")
                _flush_log()
                return True
            
            # WolfTeam yok — launcher process kontrol
            if _is_process_running("NyxLauncher.exe"):
                # Süreç çalışıyor ama pencere yok — bekle
                time.sleep(0.2)
                continue
            
            # Her ikisi de yok — başarılı giriş (oyun açılmış ve kapanmış olabilir)
            log(f"✓ BAŞARILI GİRİŞ (launcher kapandı): {username}")
            _flush_log()
            return True

        # Ayrı hata penceresi var mı? (hafif kontrol — her turda)
        for title in ("Error", "Hata", "Uyarı", "Warning", "Bilgi"):
            try:
                err = win32gui.FindWindow(None, title)
                if err and win32gui.IsWindowVisible(err):
                    log(f"✗ BAŞARISIZ (diyalog): {username}")
                    dismiss_error_dialog(hwnd2)
                    return False
            except Exception:
                pass

        # Launcher içinde hata metni var mı? (her 2. turda)
        if i >= 1 and i % 2 == 0:
            try:
                if check_login_error(hwnd2):
                    log(f"✗ BAŞARISIZ (hata metni): {username}")
                    dismiss_error_dialog(hwnd2)
                    return False
            except Exception:
                reset_uia()

    log(f"✗ BAŞARISIZ (timeout): {username}")
    return False

# ── ANA PROGRAM ───────────────────────────────────
def main():
    log("=" * 40)
    log("PROGRAM BAŞLADI")
    log("=" * 40)

    accounts = get_accounts()
    if not accounts:
        log("HATA: Hesap listesi boş!")
        return

    log(f"Toplam {len(accounts)} hesap.")

    for idx, (username, password) in enumerate(accounts, 1):
        log(f"\n[{idx}/{len(accounts)}] Deneniyor: {username}")

        if try_login(username, password):
            log(f"✓ BAŞARILI: {username}")
            save_success(username, password)
            # Oyunu ve launcher'ı kapat
            close_process(WOLFTEAM_EXE)
            kill_launcher()
            time.sleep(0.2)  # eski: 0.3
            # Sonraki hesap varsa launcher'ı yeniden başlat
            if idx < len(accounts):
                log("Launcher yeniden başlatılıyor...")
                start_launcher()
        else:
            log(f"✗ BAŞARISIZ: {username}")

    _flush_log()
    log("=" * 40)
    log("TÜM HESAPLAR DENENDİ")
    log("=" * 40)
    _flush_log()

if __name__ == "__main__":
    main()
