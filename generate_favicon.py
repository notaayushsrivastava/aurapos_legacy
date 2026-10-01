"""
Generate AuraPOS favicon.ico with multiple resolutions matching the brand mark:
Orange rounded squircle background (#c2410c / #ea580c)
Segmented circular halo (aperture ring)
Crisp geometric white 'A'
"""

import math
from PIL import Image, ImageDraw

def render_aurapos_icon(size):
    # Render at 4x supersampling for ultra-crisp antialiased edges
    scale = 4
    canvas_size = size * scale
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Background rounded rectangle (squircle)
    # Brand: viewBox 0 0 32 32, rx = 8 -> 25% corner radius
    radius = int(canvas_size * 0.25)
    
    # Gradient or solid brand orange: #c2410c -> #ea580c
    # In _brand.html: fill="#c2410c" with brand-gradient (linear orange-600 to orange-500)
    # Let's draw a vertical subtle brand gradient
    c_top = (234, 88, 12)    # #ea580c (orange-600)
    c_bot = (194, 65, 12)    # #c2410c (orange-700)
    
    # Create mask for rounded rect
    mask = Image.new("L", (canvas_size, canvas_size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([0, 0, canvas_size - 1, canvas_size - 1], radius=radius, fill=255)
    
    # Fill gradient
    grad = Image.new("RGBA", (canvas_size, canvas_size))
    for y in range(canvas_size):
        ratio = y / max(1, canvas_size - 1)
        r = int(c_top[0] + (c_bot[0] - c_top[0]) * ratio)
        g = int(c_top[1] + (c_bot[1] - c_top[1]) * ratio)
        b = int(c_top[2] + (c_bot[2] - c_top[2]) * ratio)
        for x in range(canvas_size):
            grad.putpixel((x, y), (r, g, b, 255))
            
    img.paste(grad, (0, 0), mask)
    draw = ImageDraw.Draw(img)

    # Unit grid base: 32x32
    u = canvas_size / 32.0

    # 2. Segmented circular halo
    # SVG: cx=16, cy=16, r=12.3, stroke-width=1.7, opacity=0.45, pathLength=100, stroke-dasharray="17 8"
    # Four segments of arc around circle
    cx, cy = 16.0 * u, 16.0 * u
    r = 12.3 * u
    halo_width = max(1, int(round(1.7 * u)))
    halo_color = (255, 255, 255, int(255 * 0.55))

    # Dash array 17 dash, 8 gap on pathLength 100 => 4 dashes (17*4 = 68, 8*4 = 32 -> total 100)
    # In angles: 17% of 360 deg = 61.2 deg dash, 8% of 360 deg = 28.8 deg gap
    # Start angles roughly: 0, 90, 180, 270 (rotated slightly to look balanced)
    start_angle_offset = -14.4
    for i in range(4):
        dash_deg = 61.2
        gap_deg = 28.8
        start_deg = start_angle_offset + i * (dash_deg + gap_deg)
        end_deg = start_deg + dash_deg
        bbox = [cx - r, cy - r, cx + r, cy + r]
        draw.arc(bbox, start=start_deg, end=end_deg, fill=halo_color, width=halo_width)

    # 3. Geometric 'A'
    # SVG path: M10 23.2 16 7.2l6 16, stroke-width=2.7, stroke-linecap=round, stroke-linejoin=round
    # Crossbar: M12.3 17h7.4, stroke-width=2.7
    stroke_w = max(1, int(round(2.7 * u)))
    a_color = (255, 255, 255, 255)

    p1 = (10.0 * u, 23.2 * u)
    p_apex = (16.0 * u, 7.2 * u)
    p2 = (22.0 * u, 23.2 * u)

    # Left leg
    draw.line([p1, p_apex], fill=a_color, width=stroke_w)
    # Right leg
    draw.line([p_apex, p2], fill=a_color, width=stroke_w)
    # Crossbar
    bar_y = 17.0 * u
    bar_x1 = 12.3 * u
    bar_x2 = 19.7 * u
    draw.line([(bar_x1, bar_y), (bar_x2, bar_y)], fill=a_color, width=stroke_w)

    # Round joints / end caps
    cap_r = stroke_w / 2.0
    for pt in [p1, p_apex, p2, (bar_x1, bar_y), (bar_x2, bar_y)]:
        draw.ellipse([pt[0] - cap_r, pt[1] - cap_r, pt[0] + cap_r, pt[1] + cap_r], fill=a_color)

    # Downsample cleanly with Lanczos
    resampled = img.resize((size, size), Image.Resampling.LANCZOS)
    return resampled

def main():
    sizes = [16, 32, 48, 64, 128, 256]
    images = [render_aurapos_icon(s) for s in sizes]
    
    # Save multi-size ICO to public/favicon.ico
    # Google Search specifically recommends 48x48 or multiples of 48px (48x48, 96x96, etc.)
    # and browsers need 16x16 and 32x32.
    target_path = "public/favicon.ico"
    # Primary image is 48x48 for search indexing standards, with other sizes appended
    base_img = render_aurapos_icon(48)
    base_img.save(
        target_path,
        format="ICO",
        sizes=[(s, s) for s in [16, 32, 48, 64, 128]]
    )
    print(f"Successfully generated {target_path} with sizes: 16, 32, 48, 64, 128")

if __name__ == "__main__":
    main()
