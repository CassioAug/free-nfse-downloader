import os
import pymupdf as fitz
from PIL import Image

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
img_dir = os.path.join(base_dir, "docs", "images")

# Icons and their variants to render
# Format: (svg_filename, [(output_png_name, fill_color)])
icons = [
    (
        "fa_sun.svg",
        [
            ("fa_sun_light.png", "#F8FAFC"),   # For dark theme UI
            ("fa_sun_dark.png", "#0F172A"),    # For light theme UI
            ("fa_sun_amber.png", "#D97706"),   # Accent amber
        ]
    ),
    (
        "fa_moon.svg",
        [
            ("fa_moon_light.png", "#F8FAFC"),  # For dark theme UI
            ("fa_moon_dark.png", "#0F172A"),   # For light theme UI
            ("fa_moon_indigo.png", "#6366F1"), # Accent indigo
        ]
    ),
    (
        "fa_gears.svg",
        [
            ("fa_gears_light.png", "#F8FAFC"), # For dark theme UI
            ("fa_gears_dark.png", "#0F172A"),  # For light theme UI
        ]
    ),
    (
        "fa_circle_play.svg",
        [
            ("fa_circle_play_white.png", "#FFFFFF"),
            ("fa_circle_play_dark.png", "#0F172A"),
            ("fa_circle_play_light.png", "#F8FAFC"),
        ]
    ),
    (
        "fa_circle_xmark.svg",
        [
            ("fa_circle_xmark_white.png", "#FFFFFF"),
            ("fa_circle_xmark_dark.png", "#0F172A"),
            ("fa_circle_xmark_disabled_light.png", "#94A3B8"),
            ("fa_circle_xmark_disabled_dark.png", "#64748B"),
        ]
    ),
    (
        "fa_cloud_arrow_up.svg",
        [
            ("fa_cloud_arrow_up_white.png", "#FFFFFF"),
            ("fa_cloud_arrow_up_dark.png", "#0F172A"),
            ("fa_cloud_arrow_up_light.png", "#F8FAFC"),
        ]
    ),
    (
        "fa_trash.svg",
        [
            ("fa_trash_white.png", "#FFFFFF"),
            ("fa_trash_dark.png", "#0F172A"),
            ("fa_trash_light.png", "#F8FAFC"),
        ]
    ),
    (
        "refinedgithub.svg",
        [
            ("github_mark_white.png", "#FFFFFF"),
            ("github_mark_light.png", "#F8FAFC"),
            ("github_mark_dark.png", "#0F172A"),
        ]
    )
]

for svg_file, variants in icons:
    svg_path = os.path.join(img_dir, svg_file)
    if not os.path.exists(svg_path):
        print(f"Warning: {svg_path} not found!")
        continue
    
    with open(svg_path, "r", encoding="utf-8") as f:
        svg_content = f.read()

    for out_name, color in variants:
        # Inject fill color into <path ...>
        if "<path fill=" in svg_content:
            # Replace existing fill
            import re
            colored_svg = re.sub(r'fill="[^"]+"', f'fill="{color}"', svg_content)
        else:
            colored_svg = svg_content.replace("<path ", f'<path fill="{color}" ')
        
        doc = fitz.open(stream=colored_svg.encode("utf-8"), filetype="svg")
        pix = doc[0].get_pixmap(dpi=300, alpha=True)
        out_path = os.path.join(img_dir, out_name)
        pix.save(out_path)
        
        im = Image.open(out_path)
        print(f"Generated {out_name}: size={im.size}, mode={im.mode}, corner_alpha={im.getpixel((0,0))[-1]}")

print("All FontAwesome and GitHub icons successfully rendered!")
