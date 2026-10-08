import hashlib
import hmac
import sys

# ═══════════════════════════════════════════════════════════════════════
# FORZA V8 — LİSANS ÜRETİCİ (KEYGEN)
# license_manager.py V2 ile uyumlu — HMAC-SHA256 + SHA512
# ═══════════════════════════════════════════════════════════════════════

# Bu değerler license_manager.py içindeki ile BİREBİR AYNI olmalıdır!
_S1 = bytes([70,82,90,95,87,76,70,95,84,82])
_S2 = bytes([95,50,48,50,54,95,89,83,70])
_S3 = bytes([95,80,82,79,95,86,56])
_SECRET = (_S1 + _S2 + _S3).decode()

def generate_key(hwid):
    """HMAC-SHA256 + SHA512 çift hash key üretimi."""
    hwid = hwid.strip()
    h1 = hmac.new(_SECRET.encode(), hwid.encode(), hashlib.sha256).digest()
    h2 = hashlib.sha512(h1 + hwid.encode() + _SECRET.encode()).hexdigest()
    raw = h2[:32].upper()
    filtered = ''.join(c for c in raw if c.isalnum())[:24]
    return filtered

if __name__ == "__main__":
    print("=" * 55)
    print("🐺  FORZA V10 BUG FİX — LİSANS ÜRETİCİ")
    print("=" * 55)
    
    while True:
        try:
            hwid_input = input("\nMüşterinin Sistem Kodunu (HWID) Yapıştırın (Q = Çık): ").strip()
            if hwid_input.lower() == 'q':
                break
            
            if not hwid_input:
                continue
                
            key = generate_key(hwid_input)
            print("\n" + "─" * 55)
            print("  BU KODU MÜŞTERİYE GÖNDERİN:")
            print(f"  >>> {key} <<<")
            print("─" * 55)
        except KeyboardInterrupt:
            break
