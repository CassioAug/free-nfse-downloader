import pymupdf as fitz
import os
from PIL import Image

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
svg_path = os.path.join(base_dir, "docs", "images", "refinedgithub.svg")
with open(svg_path, "r", encoding="utf-8") as f:
    svg_content = f.read()

# 1. Dark theme icon (White silhouette #F8FAFC on transparent background)
svg_white = svg_content.replace("<path ", '<path fill="#F8FAFC" ')
doc_w = fitz.open(stream=svg_white.encode("utf-8"), filetype="svg")
pix_w = doc_w[0].get_pixmap(dpi=300, alpha=True)
out_light = os.path.join(base_dir, "docs", "images", "github_mark_light.png")
pix_w.save(out_light)

# 2. Light theme icon (Charcoal silhouette #1F2328 on transparent background)
svg_dark = svg_content.replace("<path ", '<path fill="#1F2328" ')
doc_d = fitz.open(stream=svg_dark.encode("utf-8"), filetype="svg")
pix_d = doc_d[0].get_pixmap(dpi=300, alpha=True)
out_dark = os.path.join(base_dir, "docs", "images", "github_mark_dark.png")
pix_d.save(out_dark)

# Verification
im1 = Image.open(out_dark)
im2 = Image.open(out_light)
print("Dark icon:", im1.mode, im1.size, "corner pixel:", im1.getpixel((0, 0)))
print("Light icon:", im2.mode, im2.size, "corner pixel:", im2.getpixel((0, 0)))
print("Successfully generated Refined GitHub icons with true transparency!")
