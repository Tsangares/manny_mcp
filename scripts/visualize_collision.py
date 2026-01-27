#!/usr/bin/env python3
"""
Visualize OSRS collision data as a colored PNG image.

Maps 32-bit collision flags to colors:
- Black (0x000000): Fully blocked (BLOCK_MOVEMENT_FULL)
- Blue (0x0000FF): Water (BLOCK_MOVEMENT_FLOOR)
- Green (0x00FF00): Walkable (no flags)
- Red/Orange: Directional walls (N/E/S/W flags)
- Gradient: Mixed flags based on bitmask

Usage:
    python visualize_collision.py <region_id>
    python visualize_collision.py 12850  # Grand Exchange area
    python visualize_collision.py --around 3164 3464  # Around coordinates
"""

import struct
import sys
from pathlib import Path
from PIL import Image
import colorsys

COLLISION_DIR = Path("/home/wil/Desktop/manny/data/collision")
OUTPUT_DIR = Path("/home/wil/Desktop/manny/tmp/collision_viz")
REGION_SIZE = 64

# Collision flags from RuneLite API
BLOCK_MOVEMENT_FULL = 0x100
BLOCK_MOVEMENT_FLOOR = 0x200000  # Water/unwalkable
BLOCK_MOVEMENT_NORTH = 0x2
BLOCK_MOVEMENT_EAST = 0x8
BLOCK_MOVEMENT_SOUTH = 0x20
BLOCK_MOVEMENT_WEST = 0x80
BLOCK_MOVEMENT_NORTH_EAST = 0x4
BLOCK_MOVEMENT_NORTH_WEST = 0x1
BLOCK_MOVEMENT_SOUTH_EAST = 0x10
BLOCK_MOVEMENT_SOUTH_WEST = 0x40

# All directional flags combined
DIRECTIONAL_FLAGS = (
    BLOCK_MOVEMENT_NORTH | BLOCK_MOVEMENT_EAST |
    BLOCK_MOVEMENT_SOUTH | BLOCK_MOVEMENT_WEST |
    BLOCK_MOVEMENT_NORTH_EAST | BLOCK_MOVEMENT_NORTH_WEST |
    BLOCK_MOVEMENT_SOUTH_EAST | BLOCK_MOVEMENT_SOUTH_WEST
)


def flag_to_color(flags: int) -> tuple:
    """
    Map collision flags to RGB color.

    Color scheme:
    - Green (0, 200, 0): Fully walkable (no flags)
    - Black (0, 0, 0): Fully blocked
    - Blue (0, 100, 200): Water
    - Red shades: Directional walls (intensity based on count)
    - Yellow: Mixed flags
    """
    if flags == 0:
        return (100, 200, 100)  # Light green - walkable

    if flags & BLOCK_MOVEMENT_FULL:
        return (40, 40, 40)  # Dark gray - fully blocked

    if flags & BLOCK_MOVEMENT_FLOOR:
        return (50, 100, 180)  # Blue - water

    # Count directional flags
    dir_count = bin(flags & DIRECTIONAL_FLAGS).count('1')

    if dir_count > 0:
        # Red intensity based on number of blocked directions
        intensity = min(255, 100 + dir_count * 30)
        return (intensity, 50, 50)  # Red shades for walls

    # Unknown flags - yellow
    return (200, 200, 50)


def flag_to_color_spectrum(flags: int) -> tuple:
    """
    Alternative: Map flags to HSV color spectrum for visual variety.
    Hue based on flag value, saturation based on blocking severity.
    """
    if flags == 0:
        return (100, 200, 100)  # Green - walkable

    if flags & BLOCK_MOVEMENT_FULL:
        return (20, 20, 20)  # Near black - blocked

    if flags & BLOCK_MOVEMENT_FLOOR:
        return (50, 80, 150)  # Blue - water

    # Map other flags to hue (0-360 degrees)
    # Use lower bits for hue variation
    hue = (flags & 0xFF) / 255.0
    saturation = 0.7
    value = 0.8

    r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
    return (int(r * 255), int(g * 255), int(b * 255))


def load_region(region_id: int) -> list | None:
    """Load collision data from .dat file."""
    dat_file = COLLISION_DIR / f"region_{region_id}.dat"

    if not dat_file.exists():
        print(f"Region file not found: {dat_file}")
        return None

    with open(dat_file, 'rb') as f:
        # Read magic number
        magic = struct.unpack('>I', f.read(4))[0]
        if magic != 0xC0111510:
            print(f"Invalid magic number: {hex(magic)}")
            return None

        # Read collision flags: [plane][x][y]
        data = []
        for plane in range(4):
            plane_data = []
            for x in range(REGION_SIZE):
                row = []
                for y in range(REGION_SIZE):
                    flags = struct.unpack('>I', f.read(4))[0]
                    row.append(flags)
                plane_data.append(row)
            data.append(plane_data)

        return data


def visualize_region(region_id: int, plane: int = 0, use_spectrum: bool = False):
    """Generate PNG visualization for a single region."""
    data = load_region(region_id)
    if data is None:
        return None

    # Create image (64x64 tiles, scale up 8x for visibility)
    scale = 8
    img = Image.new('RGB', (REGION_SIZE * scale, REGION_SIZE * scale))
    pixels = img.load()

    color_func = flag_to_color_spectrum if use_spectrum else flag_to_color

    for x in range(REGION_SIZE):
        for y in range(REGION_SIZE):
            flags = data[plane][x][y]
            color = color_func(flags)

            # Fill scaled pixel block
            for dx in range(scale):
                for dy in range(scale):
                    # Flip Y axis (OSRS Y increases north, image Y increases down)
                    img_y = (REGION_SIZE - 1 - y) * scale + dy
                    img_x = x * scale + dx
                    pixels[img_x, img_y] = color

    # Add grid lines
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    grid_color = (80, 80, 80)

    for i in range(0, REGION_SIZE + 1, 8):
        # Vertical lines
        draw.line([(i * scale, 0), (i * scale, REGION_SIZE * scale)], fill=grid_color)
        # Horizontal lines
        draw.line([(0, i * scale), (REGION_SIZE * scale, i * scale)], fill=grid_color)

    return img


def visualize_multi_region(center_x: int, center_y: int, radius: int = 1, plane: int = 0):
    """
    Visualize multiple regions around a world coordinate.

    Args:
        center_x, center_y: World coordinates
        radius: Number of regions in each direction (1 = 3x3 grid)
        plane: Game plane (0-3)
    """
    # Calculate center region
    base_x = center_x // REGION_SIZE
    base_y = center_y // REGION_SIZE
    center_region = (base_x << 8) | base_y

    print(f"Center: ({center_x}, {center_y}) -> Region {center_region}")

    # Calculate region grid
    regions = []
    for dy in range(-radius, radius + 1):
        row = []
        for dx in range(-radius, radius + 1):
            region_id = ((base_x + dx) << 8) | (base_y + dy)
            row.append(region_id)
        regions.append(row)

    # Size of combined image
    grid_size = 2 * radius + 1
    scale = 8
    tile_size = REGION_SIZE * scale
    img = Image.new('RGB', (grid_size * tile_size, grid_size * tile_size), (30, 30, 30))

    for row_idx, row in enumerate(regions):
        for col_idx, region_id in enumerate(row):
            region_img = visualize_region(region_id, plane)
            if region_img:
                # Paste into combined image (flip row index for correct orientation)
                paste_y = (grid_size - 1 - row_idx) * tile_size
                paste_x = col_idx * tile_size
                img.paste(region_img, (paste_x, paste_y))
                print(f"  Added region {region_id} at grid ({col_idx}, {row_idx})")
            else:
                print(f"  Missing region {region_id}")

    return img


def coords_to_region(x: int, y: int) -> int:
    """Convert world coordinates to region ID."""
    base_x = x // REGION_SIZE
    base_y = y // REGION_SIZE
    return (base_x << 8) | base_y


def visualize_live_dump(json_path: Path = Path("/tmp/manny_collision.json")):
    """
    Visualize collision data dumped from the live game via DUMP_COLLISION command.
    """
    import json

    if not json_path.exists():
        print(f"Collision dump not found: {json_path}")
        print("Run 'DUMP_COLLISION' command in-game first")
        return None

    with open(json_path) as f:
        data = json.load(f)

    player = data["player"]
    scene_base = data["scene_base"]
    width = data["width"]
    height = data["height"]
    flags = data["flags"]

    print(f"Player at: ({player['x']}, {player['y']}, plane {player['plane']})")
    print(f"Scene base: ({scene_base['x']}, {scene_base['y']})")
    print(f"Grid size: {width}x{height}")

    # Create image
    scale = 4
    img = Image.new('RGB', (width * scale, height * scale))
    pixels = img.load()

    for x in range(width):
        for y in range(height):
            flag = flags[x][y]
            color = flag_to_color(flag)

            # Fill scaled pixel block (flip Y for display)
            for dx in range(scale):
                for dy in range(scale):
                    img_y = (height - 1 - y) * scale + dy
                    img_x = x * scale + dx
                    pixels[img_x, img_y] = color

    # Draw player position marker
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)

    player_scene_x = player['x'] - scene_base['x']
    player_scene_y = player['y'] - scene_base['y']

    if 0 <= player_scene_x < width and 0 <= player_scene_y < height:
        px = player_scene_x * scale + scale // 2
        py = (height - 1 - player_scene_y) * scale + scale // 2
        # Draw white dot with black outline for visibility
        draw.ellipse([px - 5, py - 5, px + 5, py + 5], fill=(255, 255, 255), outline=(0, 0, 0), width=1)

    # Add grid lines every 8 tiles
    grid_color = (60, 60, 60)
    for i in range(0, width + 1, 8):
        draw.line([(i * scale, 0), (i * scale, height * scale)], fill=grid_color)
    for i in range(0, height + 1, 8):
        draw.line([(0, i * scale), (width * scale, i * scale)], fill=grid_color)

    return img


def main():
    import json
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if len(sys.argv) < 2:
        print(__doc__)
        print("\nUsage:")
        print("  python visualize_collision.py --live      # Visualize from DUMP_COLLISION output")
        print("  python visualize_collision.py <region_id> # Visualize extracted region")
        print("  python visualize_collision.py --around X Y [radius]  # Multi-region view")
        return

    if sys.argv[1] == '--live':
        # Visualize from live game dump
        img = visualize_live_dump()
        if img:
            output_path = OUTPUT_DIR / "collision_live.png"
            img.save(output_path)
            print(f"\nSaved: {output_path}")
            print(f"Size: {img.size[0]}x{img.size[1]} pixels")
            print("\nColor Legend:")
            print("  Light Green: Walkable (no flags)")
            print("  Dark Gray:   Fully blocked")
            print("  Blue:        Water")
            print("  Red shades:  Directional walls")
            print("  Yellow crosshair: Player position")
        return

    if sys.argv[1] == '--around':
        # Visualize around coordinates
        x, y = int(sys.argv[2]), int(sys.argv[3])
        radius = int(sys.argv[4]) if len(sys.argv) > 4 else 1
        plane = int(sys.argv[5]) if len(sys.argv) > 5 else 0

        img = visualize_multi_region(x, y, radius, plane)
        if img:
            output_path = OUTPUT_DIR / f"collision_around_{x}_{y}_r{radius}.png"
            img.save(output_path)
            print(f"\nSaved: {output_path}")
            print(f"Size: {img.size[0]}x{img.size[1]} pixels")

    elif sys.argv[1] == '--spectrum':
        # Use spectrum coloring
        region_id = int(sys.argv[2])
        plane = int(sys.argv[3]) if len(sys.argv) > 3 else 0

        img = visualize_region(region_id, plane, use_spectrum=True)
        if img:
            output_path = OUTPUT_DIR / f"collision_spectrum_{region_id}_p{plane}.png"
            img.save(output_path)
            print(f"Saved: {output_path}")

    else:
        # Single region
        region_id = int(sys.argv[1])
        plane = int(sys.argv[2]) if len(sys.argv) > 2 else 0

        img = visualize_region(region_id, plane)
        if img:
            output_path = OUTPUT_DIR / f"collision_{region_id}_p{plane}.png"
            img.save(output_path)
            print(f"Saved: {output_path}")

            # Print color legend
            print("\nColor Legend:")
            print("  Light Green: Walkable (no flags)")
            print("  Dark Gray:   Fully blocked (walls, buildings)")
            print("  Blue:        Water/unwalkable floor")
            print("  Red shades:  Directional walls (darker = more directions blocked)")


if __name__ == '__main__':
    main()
