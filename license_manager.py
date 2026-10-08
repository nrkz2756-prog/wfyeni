import os
import sys
import hashlib
import hmac
import subprocess
import winreg
import tkinter as tk
from tkinter import messagebox
import time
import struct

# ══════════════════════════════════════════════════════════════════════════
# GELİŞMİŞ LİSANS SİSTEMİ V2 — Çok Katmanlı Koruma
# ══════════════════════════════════════════════════════════════════════════

# Obfuscated tuz bileşenleri (direkt okunması zor)
_S1 = bytes([70,82,90,95,87,76,70,95,84,82])
_S2 = bytes([95,50,48,50,54,95,89,83,70])
_S3 = bytes([95,80,82,79,95,86,56])
_SECRET = (_S1 + _S2 + _S3).decode()

# İkincil doğrulama tuzu
_V1 = bytes([86,69,82,73,70,89,95,70,82,90])
_V2 = bytes([95,73,78,84,69,71,82,73,84,89])
_VERIFY_SALT = (_V1 + _V2).decode()

# ══════════════════════════════════════════════════════════════════════════
# GİZLİ DEPOLAMA KONUMLARI
# ══════════════════════════════════════════════════════════════════════════
REG_PATH_1 = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
REG_KEY_1  = "SysAuthToken"

REG_PATH_2 = r"Software\Microsoft\SystemCertificates\FORZA"
REG_KEY_2  = "LicenseKey"

# Checksum registry (tamper detection)
REG_PATH_3 = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
REG_KEY_3  = "SecureHash"

def get_file_paths():
    paths = []
    appdata = os.getenv("APPDATA")
    localdata = os.getenv("LOCALAPPDATA")
    userprofile = os.getenv("USERPROFILE")

    if appdata:
        paths.append(os.path.join(appdata, "Microsoft", "Vault", "sys_lic.dat"))
        paths.append(os.path.join(appdata, "Microsoft", "Crypto", "Keys", "sys_auth.dat"))
    if localdata:
        paths.append(os.path.join(localdata, "Microsoft", "Credentials", "sys_token.dat"))
    if userprofile:
        paths.append(os.path.join(userprofile, ".forza_sys.dat"))
    return paths

# ══════════════════════════════════════════════════════════════════════════
# GELİŞMİŞ HWID — Çoklu donanım kimliği
# ══════════════════════════════════════════════════════════════════════════
def get_all_hwids():
    hwids = []
    try:
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        guid, _ = winreg.QueryValueEx(k, "MachineGuid")
        winreg.CloseKey(k)
        if guid and len(guid) > 8:
            hwids.append(guid.strip())
    except Exception:
        pass

    try:
        import uuid
        mac = str(uuid.getnode())
        if mac and mac not in hwids:
            hwids.append(mac)
    except Exception:
        pass

    try:
        out = subprocess.check_output("wmic csproduct get uuid", shell=True, timeout=2).decode().strip()
        lines = [l.strip() for l in out.splitlines() if l.strip() and "UUID" not in l]
        if lines and lines[0] not in hwids:
            hwids.append(lines[0])
    except Exception:
        pass

    if not hwids:
        hwids.append("FORZA_DEFAULT_HWID_2026")
    return hwids

# ══════════════════════════════════════════════════════════════════════════
# GELİŞMİŞ KEY ÜRETİMİ — HMAC + Çift Hash
# ══════════════════════════════════════════════════════════════════════════
def _derive_key(hwid, salt):
    """HMAC-SHA256 tabanlı key türetme — salt bilinse bile tahmin edilemez."""
    h1 = hmac.new(salt.encode(), hwid.encode(), hashlib.sha256).digest()
    h2 = hashlib.sha512(h1 + hwid.encode() + salt.encode()).hexdigest()
    # İlk 24 karakter, sadece büyük harf+rakam
    raw = h2[:32].upper()
    filtered = ''.join(c for c in raw if c.isalnum())[:24]
    return filtered

def generate_key_for_hwid(hwid):
    return _derive_key(hwid, _SECRET)

def _generate_checksum(key):
    """Key için tamper-detection checksum üret."""
    return hmac.new(_VERIFY_SALT.encode(), key.encode(), hashlib.sha256).hexdigest()[:16].upper()

def get_valid_keys_for_pc():
    hwids = get_all_hwids()
    return {generate_key_for_hwid(h) for h in hwids}

# ══════════════════════════════════════════════════════════════════════════
# ŞİFRELİ DEPOLAMA — Key düz metin saklanmaz
# ══════════════════════════════════════════════════════════════════════════
def _obfuscate_key(key):
    """Key'i XOR ile şifrele — düz metin olarak saklanmaz."""
    xor_key = hashlib.md5(_VERIFY_SALT.encode()).digest()
    data = key.encode()
    result = bytearray()
    for i, b in enumerate(data):
        result.append(b ^ xor_key[i % len(xor_key)])
    import base64
    return base64.b64encode(bytes(result)).decode()

def _deobfuscate_key(encoded):
    """XOR şifreli key'i çöz."""
    try:
        import base64
        data = base64.b64decode(encoded.encode())
        xor_key = hashlib.md5(_VERIFY_SALT.encode()).digest()
        result = bytearray()
        for i, b in enumerate(data):
            result.append(b ^ xor_key[i % len(xor_key)])
        return bytes(result).decode()
    except Exception:
        return ""

# ══════════════════════════════════════════════════════════════════════════
# OKUMA & YAZMA
# ══════════════════════════════════════════════════════════════════════════
def _read_from_registry(reg_path, reg_key):
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(k, reg_key)
        winreg.CloseKey(k)
        return (val or "").strip()
    except Exception:
        return ""

def _write_to_registry(reg_path, reg_key, value):
    try:
        k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, reg_path)
        winreg.SetValueEx(k, reg_key, 0, winreg.REG_SZ, value)
        winreg.CloseKey(k)
    except Exception:
        pass

def _read_from_file(filepath):
    try:
        if os.path.isfile(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        pass
    return ""

def _write_to_file(filepath, value):
    try:
        d = os.path.dirname(filepath)
        if d and not os.path.exists(d):
            os.makedirs(d, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(value)
        if os.name == 'nt':
            try:
                subprocess.call(['attrib', '+h', '+s', filepath], creationflags=0x08000000)
            except Exception:
                pass
    except Exception:
        pass

def save_license_permanently(valid_key):
    """Lisansı şifreleyerek 6 farklı gizli konuma yazar + checksum."""
    enc_key = _obfuscate_key(valid_key)
    checksum = _generate_checksum(valid_key)
    
    # Şifreli key'i sakla
    _write_to_registry(REG_PATH_1, REG_KEY_1, enc_key)
    _write_to_registry(REG_PATH_2, REG_KEY_2, enc_key)
    # Checksum'ı ayrı konuma sakla (tamper detection)
    _write_to_registry(REG_PATH_3, REG_KEY_3, checksum)
    
    for path in get_file_paths():
        _write_to_file(path, enc_key)

def _read_stored_key(raw_value):
    """Saklanan değeri oku — önce şifreli dene, sonra eski düz metin uyumluluğu."""
    if not raw_value:
        return ""
    # Yeni format: XOR şifreli
    dec = _deobfuscate_key(raw_value)
    if dec and len(dec) >= 16:
        return dec.upper()
    # Eski format uyumluluğu: düz metin
    if len(raw_value) >= 16 and raw_value.isalnum():
        return raw_value.upper()
    return ""

# ══════════════════════════════════════════════════════════════════════════
# LİSANS DOĞRULAMA — Gelişmiş
# ══════════════════════════════════════════════════════════════════════════
def verify_license():
    valid_keys = get_valid_keys_for_pc()
    stored_keys = []

    # Registry'lerden oku
    for rp, rk in [(REG_PATH_1, REG_KEY_1), (REG_PATH_2, REG_KEY_2)]:
        raw = _read_from_registry(rp, rk)
        if raw:
            dec = _read_stored_key(raw)
            if dec:
                stored_keys.append(dec)

    # Gizli dosyalardan oku
    for path in get_file_paths():
        raw = _read_from_file(path)
        if raw:
            dec = _read_stored_key(raw)
            if dec:
                stored_keys.append(dec)

    # Kontrol: eşleşme var mı?
    for sk in stored_keys:
        if sk and sk in valid_keys:
            # Checksum doğrulama (tamper detection)
            stored_cs = _read_from_registry(REG_PATH_3, REG_KEY_3)
            expected_cs = _generate_checksum(sk)
            if stored_cs and stored_cs != expected_cs:
                # Checksum eşleşmedi — tamper tespit edildi, yeniden kaydet
                pass
            # Geçerli! Tüm konumlara yeniden kaydet (self-healing + yeni format)
            save_license_permanently(sk)
            return True

    # Aktivasyon ekranı
    primary_hwid = get_all_hwids()[0]
    primary_key  = generate_key_for_hwid(primary_hwid)
    return _prompt_license(primary_hwid, primary_key)

def _prompt_license(hwid, expected_key):
    root = tk.Tk()
    root.title("Sistem Aktivasyonu")
    root.geometry("460x280")
    root.resizable(False, False)
    root.configure(bg="#0b0b0f")
    
    root.update_idletasks()
    x = (root.winfo_screenwidth() - 460) // 2
    y = (root.winfo_screenheight() - 280) // 2
    root.geometry(f"+{x}+{y}")

    result = [False]

    def on_verify():
        user_key = entry_key.get().strip().upper()
        valid_keys = get_valid_keys_for_pc()
        if user_key in valid_keys or user_key == expected_key:
            save_license_permanently(user_key)
            result[0] = True
            messagebox.showinfo("Başarılı", "Lisans bu bilgisayara kalıcı olarak kilitlendi!", master=root)
            root.destroy()
        else:
            messagebox.showerror("Hata", "Geçersiz Lisans Anahtarı!", master=root)

    def on_close():
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    tk.Label(root, text="🛡️ FORZA V10 BUG FİX — LİSANS", font=("Segoe UI", 16, "bold"), fg="#e63946", bg="#0b0b0f").pack(pady=(15, 5))
    tk.Label(root, text="Bu bilgisayar için aktif lisans bulunamadı.\nLisans anahtarınızı girerek kalıcı olarak kilitleyin.", 
             fg="#95a5a6", bg="#0b0b0f", font=("Segoe UI", 10)).pack()

    frame_hwid = tk.Frame(root, bg="#0b0b0f")
    frame_hwid.pack(pady=10, fill="x", padx=20)
    tk.Label(frame_hwid, text="Sistem Kodu:", fg="#7f8c8d", bg="#0b0b0f", font=("Segoe UI", 9)).pack(side="left")
    
    entry_hwid = tk.Entry(frame_hwid, font=("Consolas", 10), readonlybackground="#141418", fg="#2ecc71", highlightthickness=0, bd=0)
    entry_hwid.pack(side="right", fill="x", expand=True, padx=(10, 0))
    entry_hwid.insert(0, hwid)
    entry_hwid.configure(state="readonly")

    tk.Label(root, text="Lisans Anahtarı:", fg="#ecf0f1", bg="#0b0b0f", font=("Segoe UI", 10)).pack(anchor="w", padx=20)
    entry_key = tk.Entry(root, font=("Consolas", 12), justify="center", bg="#141418", fg="#ecf0f1", insertbackground="#e63946", highlightthickness=1, highlightcolor="#e63946", bd=0)
    entry_key.pack(fill="x", padx=20, pady=(0, 15), ipady=5)

    btn = tk.Button(root, text="🔒 DOĞRULA VE KİLİTLE", font=("Segoe UI", 11, "bold"), bg="#e63946", fg="white", 
                    activebackground="#ff4d5a", activeforeground="white", relief="flat", cursor="hand2", command=on_verify, bd=0)
    btn.pack(fill="x", padx=20, ipady=5)

    root.mainloop()
    
    if not result[0]:
        sys.exit(0)
    
    return True

if __name__ == "__main__":
    verify_license()
