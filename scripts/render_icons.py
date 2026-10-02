import os
import re
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
            ("fa_sun_white.png", "#FFFFFF"),
            ("fa_sun_light.png", "#F8FAFC"),
            ("fa_sun_dark.png", "#0F172A"),
            ("fa_sun_muted_light.png", "#64748B"),
            ("fa_sun_muted_dark.png", "#94A3B8"),
        ]
    ),
    (
        "fa_moon.svg",
        [
            ("fa_moon_white.png", "#FFFFFF"),
            ("fa_moon_light.png", "#F8FAFC"),
            ("fa_moon_dark.png", "#0F172A"),
            ("fa_moon_muted_light.png", "#64748B"),
            ("fa_moon_muted_dark.png", "#94A3B8"),
        ]
    ),
    (
        "fa_gears.svg",
        [
            ("fa_gears_white.png", "#FFFFFF"),
            ("fa_gears_light.png", "#F8FAFC"),
            ("fa_gears_dark.png", "#0F172A"),
            ("fa_gears_muted_light.png", "#64748B"),
            ("fa_gears_muted_dark.png", "#94A3B8"),
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
    ),
    (
        "fa_magnifying_glass.svg",
        [
            ("fa_magnifying_glass_white.png", "#FFFFFF"),
            ("fa_magnifying_glass_light.png", "#F8FAFC"),
            ("fa_magnifying_glass_dark.png", "#0F172A"),
        ]
    ),
    (
        "fa_file_csv.svg",
        [
            ("fa_file_csv_white.png", "#FFFFFF"),
            ("fa_file_csv_light.png", "#F8FAFC"),
            ("fa_file_csv_dark.png", "#0F172A"),
        ]
    ),
    (
        "fa_file_pdf.svg",
        [
            ("fa_file_pdf_white.png", "#FFFFFF"),
            ("fa_file_pdf_light.png", "#F8FAFC"),
            ("fa_file_pdf_dark.png", "#0F172A"),
        ]
    ),
    (
        "fa_file_lines.svg",
        [
            ("fa_file_lines_white.png", "#FFFFFF"),
            ("fa_file_lines_light.png", "#F8FAFC"),
            ("fa_file_lines_dark.png", "#0F172A"),
        ]
    ),
    (
        "fa_arrows_rotate.svg",
        [
            ("fa_arrows_rotate_white.png", "#FFFFFF"),
            ("fa_arrows_rotate_light.png", "#F8FAFC"),
            ("fa_arrows_rotate_dark.png", "#0F172A"),
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
            colored_svg = re.sub(r'fill="[^"]+"', f'fill="{color}"', svg_content)
        else:
            colored_svg = svg_content.replace("<path ", f'<path fill="{color}" ')
        
        doc = fitz.open(stream=colored_svg.encode("utf-8"), filetype="svg")
        pix = doc[0].get_pixmap(dpi=300, alpha=True)
        raw_im = Image.frombytes("RGBA", [pix.width, pix.height], pix.samples)

        # Center in a true square canvas (1:1 aspect ratio) with zero distortion
        max_dim = max(raw_im.width, raw_im.height)
        square_im = Image.new("RGBA", (max_dim, max_dim), (0, 0, 0, 0))
        offset = ((max_dim - raw_im.width) // 2, (max_dim - raw_im.height) // 2)
        square_im.paste(raw_im, offset)

        out_path = os.path.join(img_dir, out_name)
        square_im.save(out_path)
        print(f"Generated {out_name}: raw_size={raw_im.size} -> square_size={square_im.size}, offset={offset}")

print("All icons successfully rendered with 1:1 square aspect ratio!")
