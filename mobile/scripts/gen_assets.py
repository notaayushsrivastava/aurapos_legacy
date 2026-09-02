"""One-shot generator for the mobile app's PNG assets (solid brand colors)."""
import struct, zlib, os

def make_png(path: str, size: int, rgb: tuple[int, int, int]) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)  # 8-bit RGB
    row = b"\x00" + bytes(rgb) * size
    idat = zlib.compress(row * size, 9)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b""))
    print("wrote", path, size)

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # mobile/
assets = os.path.join(base, "assets")
os.makedirs(assets, exist_ok=True)

DARK = (12, 12, 18)   # #0c0c12 — AuraPOS sidebar/card surface
CYAN = (0, 245, 212)  # #00f5d4 — neon accent

make_png(os.path.join(assets, "icon.png"), 1024, DARK)
make_png(os.path.join(assets, "adaptive-icon.png"), 1024, DARK)
make_png(os.path.join(assets, "splash-icon.png"), 512, CYAN)
make_png(os.path.join(assets, "favicon.png"), 48, CYAN)
print("done")
