"""Render a sample Armenian-language menu image for testing (no real restaurant)."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

FONT = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
OUT = Path(__file__).parent / "sample_menu_hy.png"

MENU = [
    ("ՆԱԽՈՒՏԵՍՏ", [
        ("Տոլմա խաղողի տերևով", "Աղացած միս, բրինձ, կանաչի, մածուն", "2800"),
        ("Բաստուրմա", "Չորացրած տավարի միս չամանով", "3500"),
        ("Ժինգյալով հաց", "Լավաշ 20 տեսակ կանաչիով", "1500"),
    ]),
    ("ՏԱՔ ՈՒՏԵՍՏՆԵՐ", [
        ("Խորոված խոզի", "Խոզի չալաղաջ, սոխ, լավաշ", "4200"),
        ("Խաշլամա", "Գառան միս բանջարեղենով", "4800"),
        ("Մանթի", "Խմորով գնդիկներ մսով, մածուն", "3200"),
        ("Ղափամա", "Դդում բրնձով, չամիչով և մեղրով", "5500"),
    ]),
    ("ԱՂԱՆԴԵՐ", [
        ("Գաթա", "Քաղցր խմորեղեն խորիզով", "1200"),
        ("Փախլավա", "Ընկույզ, մեղր", "1400"),
    ]),
    ("ԸՄՊԵԼԻՔՆԵՐ", [
        ("Թան", "Մածունով զովացուցիչ ըմպելիք", "600"),
        ("Հայկական սուրճ", "", "700"),
    ]),
]

def main():
    W, H = 900, 1350
    img = Image.new("RGB", (W, H), (250, 244, 232))
    d = ImageDraw.Draw(img)
    title = ImageFont.truetype(FONT, 46, index=0)
    sect = ImageFont.truetype(FONT, 30, index=0)
    item = ImageFont.truetype(FONT, 27, index=0)
    desc = ImageFont.truetype(FONT, 20, index=0)
    d.text((W // 2, 60), "Ճաշացանկ", font=title, fill=(90, 30, 20), anchor="mm")
    y = 130
    for section, items in MENU:
        d.text((60, y), section, font=sect, fill=(140, 50, 30))
        y += 50
        for name, description, price in items:
            d.text((70, y), name, font=item, fill=(30, 30, 30))
            d.text((W - 70, y), f"{price} դր.", font=item, fill=(30, 30, 30), anchor="ra")
            y += 36
            if description:
                d.text((80, y), description, font=desc, fill=(100, 100, 100))
                y += 32
            y += 8
        y += 20
    img.save(OUT)
    print(OUT)

if __name__ == "__main__":
    main()
