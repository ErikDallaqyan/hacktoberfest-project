"""Build a folder of realistic clutter to try Sloth Sort on.

Every company here is made up. Pages are rendered with headless Chrome so they look like real
screenshots and PDFs; one receipt becomes an image-only PDF, like a phone scan.

    python scripts/make_demo_files.py ~/Desktop/sloth-demo
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageFilter

CHROME = os.getenv("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

BASE_CSS = """
body { margin:0; font: 15px -apple-system, 'Helvetica Neue', Arial, sans-serif; color:#1d1d1f; background:#f5f5f7; }
.wrap { max-width: 760px; margin: 40px auto; background:#fff; border-radius:14px; padding:32px 36px;
        box-shadow: 0 2px 12px rgba(0,0,0,.08); }
h1 { margin:0 0 4px; font-size:26px; } .muted { color:#6e6e73; } table { width:100%; border-collapse:collapse; }
td, th { padding:9px 4px; border-bottom:1px solid #eee; text-align:left; } .r { text-align:right; }
"""

PAGES = {
    # name -> (kind, width, height, html body)
    "Screenshot 2026-10-14 at 9.41.22 AM.png": ("png", 1100, 640, """
<div class="wrap" style="background:linear-gradient(135deg,#0b3d91,#1565c0);color:#fff">
 <div style="display:flex;justify-content:space-between"><b style="font-size:22px">SKYLINE AIR</b><span>Boarding pass</span></div>
 <div style="display:flex;justify-content:space-between;margin:28px 0;font-size:54px;font-weight:700">
  <span>SFO</span><span style="font-size:30px;align-self:center">✈︎</span><span>JFK</span></div>
 <div style="display:flex;justify-content:space-between">
  <div>Passenger<br><b>JORDAN RIVERS</b></div><div>Flight<br><b>SK 418</b></div>
  <div>Date<br><b>Oct 24, 2026</b></div><div>Boards<br><b>6:55 AM</b></div><div>Seat<br><b>21C</b></div><div>Gate<br><b>B12</b></div></div>
</div>"""),
    "Screenshot 2026-10-15 at 2.03.10 PM.png": ("png", 1000, 520, """
<div style="background:#1e1e1e;color:#d4d4d4;font:14px Menlo,monospace;padding:18px;height:100vh;box-sizing:border-box">
<div style="color:#6a9955">~/work/billing $ python3 billing/run_invoices.py --month 2026-10</div>
Loading 1,284 customers from billing.db ...<br>Traceback (most recent call last):<br>
&nbsp;&nbsp;File "/Users/jr/work/billing/run_invoices.py", line 88, in &lt;module&gt;<br>
&nbsp;&nbsp;&nbsp;&nbsp;totals = build_totals(rows)<br>
&nbsp;&nbsp;File "/Users/jr/work/billing/run_invoices.py", line 41, in build_totals<br>
&nbsp;&nbsp;&nbsp;&nbsp;cid = row["customer_id"]<br>
<span style="color:#f48771">KeyError: 'customer_id'</span><br>
<div style="color:#6a9955">~/work/billing $ █</div></div>"""),
    "Screenshot 2026-10-16 at 7.12.45 PM.png": ("png", 520, 760, """
<div style="background:#fff;height:100vh;padding:14px;box-sizing:border-box;font-size:15px">
<div style="text-align:center;border-bottom:1px solid #eee;padding-bottom:10px"><b>Roommates 🏠</b><div class="muted" style="font-size:12px">Maya, Theo, Sam</div></div>
<style>.m{max-width:72%;padding:9px 13px;border-radius:18px;margin:8px 0}.o{background:#e9e9eb}.me{background:#0a84ff;color:#fff;margin-left:auto}.n{font-size:11px;color:#8e8e93;margin:10px 4px 0}</style>
<div class="n">Maya</div><div class="m o">dinner friday?? I was thinking that new taco place on Grand Ave</div>
<div class="n">Theo</div><div class="m o">I'm in. 7:30 works</div>
<div class="m me">yes!! can someone book? I'll bring dessert</div>
<div class="n">Sam</div><div class="m o">booked for 4 at 7:30 at Casa Lupita 🌮</div>
<div class="m me">legend</div></div>"""),
    "Screenshot 2026-10-17 at 11.30.02 AM.png": ("png", 1100, 700, """
<div class="wrap"><div class="muted">HomeNest · Oakland, CA · For rent</div>
<div style="height:220px;border-radius:10px;margin:14px 0;background:linear-gradient(160deg,#c9b79c,#8a9a5b)"></div>
<h1>$2,850/mo</h1><div style="font-size:17px">2 bd · 1 ba · 940 sqft — 4127 Linden St, Oakland, CA 94608</div>
<p class="muted">Sunny top-floor unit near MacArthur BART. In-unit laundry, hardwood floors, cats OK. Available Nov 1.</p>
<button style="background:#2e7d32;color:#fff;border:0;padding:10px 18px;border-radius:8px;font-size:15px">Request a tour</button></div>"""),
    "download.pdf": ("pdf", 0, 0, """
<div class="wrap" style="box-shadow:none"><div style="display:flex;justify-content:space-between">
<div><h1>Acme Cloud</h1><div class="muted">acmecloud.example · 500 Market St, San Francisco, CA</div></div>
<div class="r"><b style="font-size:20px">INVOICE</b><br>INV-20481<br>Date: October 2, 2026<br>Due: October 16, 2026</div></div>
<p>Bill to:<br><b>Rivers Design LLC</b></p>
<table><tr><th>Description</th><th class="r">Qty</th><th class="r">Amount</th></tr>
<tr><td>Pro plan, Oct 1 – Oct 31, 2026</td><td class="r">1</td><td class="r">$40.00</td></tr>
<tr><td>Extra storage (100 GB)</td><td class="r">1</td><td class="r">$8.00</td></tr>
<tr><td><b>Total due</b></td><td></td><td class="r"><b>$48.00</b></td></tr></table>
<p class="muted">Paid with card ending 4417. Thank you for your business.</p></div>"""),
    "document (1).pdf": ("pdf", 0, 0, """
<div class="wrap" style="box-shadow:none"><h1 style="color:#e65100">EastBay Power &amp; Light</h1>
<div class="muted">Residential electric service</div>
<p>Account holder: <b>Jordan Rivers</b><br>Service address: 4127 Linden St, Oakland, CA 94608<br>
Account number: 7730 2219 5541<br>Statement date: September 28, 2026 · Billing period: Aug 27 – Sep 25, 2026</p>
<table><tr><td>Electricity used</td><td class="r">312 kWh</td></tr><tr><td>Energy charges</td><td class="r">$94.18</td></tr>
<tr><td>Taxes and fees</td><td class="r">$7.40</td></tr><tr><td><b>Amount due by Oct 20, 2026</b></td><td class="r"><b>$101.58</b></td></tr></table></div>"""),
    "Scan 2026-10-12.pdf": ("scan", 520, 900, """
<div style="background:#fff;width:380px;margin:20px auto;padding:22px;font:15px 'Courier New',monospace;text-align:center">
<b style="font-size:20px">CORNER HARDWARE</b><br>212 Piedmont Ave, Oakland CA<br>10/12/2026 &nbsp; 3:42 PM<br><br>
<div style="text-align:left">Paint roller 9in ........ 8.99<br>Painter's tape x2 ....... 11.98<br>Interior paint 1gal .... 42.50<br>
Drop cloth ............... 6.49<br><br>SUBTOTAL ............... 69.96<br>TAX 10.25% .............. 7.17<br><b>TOTAL .................. 77.13</b><br>
VISA **** 4417</div><br>THANK YOU! KEEP RECEIPT FOR RETURNS</div>"""),
    "image (3).png": ("png", 900, 560, """
<div class="wrap"><b style="font-size:18px">Newsletter signups per week — Q3 2026</b>
<div style="display:flex;align-items:flex-end;gap:14px;height:300px;margin-top:22px;border-bottom:2px solid #333">
""" + "".join(f'<div style="flex:1;background:#5e60ce;height:{h}%;position:relative"><span style="position:absolute;top:-20px;width:100%;text-align:center;font-size:12px">{v}</span></div>'
              for h, v in [(30, 120), (38, 151), (35, 140), (52, 208), (48, 190), (61, 244), (70, 280), (66, 262), (82, 330), (90, 361)]) + """
</div><div class="muted" style="margin-top:6px">Weeks 27–36 · source: HomeNest marketing</div></div>"""),
    "Screenshot 2026-10-18 at 4.55.31 PM.png": ("png", 1100, 520, """
<div class="wrap"><div class="muted">Acme Cloud · Settings · API keys</div><h1>Your API keys</h1>
<p class="muted">Keep these secret. Anyone with a key can use your account.</p>
<table><tr><th>Name</th><th>Key</th><th>Created</th></tr>
<tr><td>production</td><td style="font-family:Menlo">ak_live_9f3K2pQx7LmT4vRb8sYz1nWc</td><td>Oct 18, 2026</td></tr>
<tr><td>staging</td><td style="font-family:Menlo">ak_test_4Hq8ZcVt2NbX6mRk0pLs9yUe</td><td>Sep 2, 2026</td></tr></table></div>"""),
    "8f14e45fceea167a5a36dedd4bea2543.png": ("png", 700, 700, """
<div style="background:#111;color:#fff;height:100vh;display:flex;flex-direction:column;justify-content:space-between;
text-align:center;font:900 44px Impact,'Arial Black',sans-serif;padding:30px;box-sizing:border-box;text-transform:uppercase">
<div>Me: I'll name my files later</div><div style="font-size:160px">🦥</div><div>My Desktop: 412 screenshots</div></div>"""),
    "Screenshot 2026-10-19 at 8.20.14 PM.png": ("png", 1100, 620, """
<div class="wrap"><div class="muted">Shopwell · Your cart (1 item)</div>
<div style="display:flex;gap:22px;margin-top:16px"><div style="width:180px;height:140px;border-radius:10px;background:linear-gradient(#a1887f,#6d4c41)"></div>
<div><h1 style="font-size:22px">Ergo Lift Standing Desk, 55 × 28 in, Walnut</h1><div class="muted">Electric height adjustment · 3 memory presets</div>
<p style="font-size:22px"><b>$349.99</b> <s class="muted">$429.99</s></p><div style="color:#2e7d32">In stock · Free delivery Thu, Oct 29</div></div></div>
<button style="margin-top:18px;background:#ffb300;border:0;padding:12px 26px;border-radius:20px;font-size:15px">Proceed to checkout</button></div>"""),
    # A file someone named on purpose. Sloth Sort must leave it alone.
    "taxes 2025 notes.pdf": ("pdf", 0, 0, """
<div class="wrap" style="box-shadow:none"><h1>Taxes 2025 — notes</h1><ul><li>Find 1099 from Rivers Design LLC</li>
<li>Home office: 120 sq ft</li><li>Ask about EV credit</li></ul></div>"""),
}


def render(name: str, kind: str, w: int, h: int, body: str, out_dir: Path, tmp: Path) -> None:
    html = tmp / "page.html"
    html.write_text(f"<!doctype html><meta charset=utf-8><style>{BASE_CSS}</style>{body}")
    target = out_dir / name
    common = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-pdf-header-footer"]
    if kind == "pdf":
        subprocess.run(common + [f"--print-to-pdf={target}", html.as_uri()], check=True, capture_output=True)
        return
    png = tmp / "shot.png"
    subprocess.run(common + ["--force-device-scale-factor=2", f"--window-size={w},{h}",
                             f"--screenshot={png}", html.as_uri()], check=True, capture_output=True)
    if kind == "png":
        png.replace(target)
        return
    # "scan": a slightly tilted, soft, grey photo of the receipt saved as an image-only PDF.
    img = Image.open(png).convert("L").rotate(1.2, expand=True, fillcolor=200).filter(ImageFilter.GaussianBlur(0.8))
    img.point(lambda p: p * 0.93 + 8).convert("RGB").save(target, "PDF", resolution=150)


def main() -> None:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "demo").expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        for name, (kind, w, h, body) in PAGES.items():
            render(name, kind, w, h, body, out_dir, Path(t))
            print("made", name)


if __name__ == "__main__":
    main()
