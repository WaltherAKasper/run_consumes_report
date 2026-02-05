#!/usr/bin/env python3
"""
PNG Manual Cropper
Crop specific amounts from each edge of a PNG file.
"""

import sys
from pathlib import Path
from PIL import Image


def crop_manual(input_path: Path, output_path: Path, top=0, right=0, bottom=0, left=0):
    """
    Crop specific amounts from each edge of an image.
    
    Args:
        input_path: Path to input PNG file
        output_path: Path to output PNG file
        top: Pixels to remove from top
        right: Pixels to remove from right
        bottom: Pixels to remove from bottom
        left: Pixels to remove from left
    """
    print(f"[INFO] Loading image: {input_path}")
    img = Image.open(input_path)
    
    width, height = img.size
    print(f"[INFO] Original size: {width}x{height}")
    
    # Calculate new dimensions
    new_left = left
    new_top = top
    new_right = width - right
    new_bottom = height - bottom
    
    # Validate crop box
    if new_right <= new_left or new_bottom <= new_top:
        print("[ERROR] Invalid crop dimensions - would result in zero or negative size!")
        print(f"  Left: {new_left}, Top: {new_top}, Right: {new_right}, Bottom: {new_bottom}")
        return False
    
    # Crop the image
    cropped = img.crop((new_left, new_top, new_right, new_bottom))
    
    new_width, new_height = cropped.size
    print(f"[INFO] Cropped size: {new_width}x{new_height}")
    print(f"[INFO] Removed - Top: {top}px, Right: {right}px, Bottom: {bottom}px, Left: {left}px")
    
    # Calculate savings
    original_pixels = width * height
    new_pixels = new_width * new_height
    reduction = (1 - new_pixels / original_pixels) * 100
    print(f"[INFO] Size reduction: {reduction:.1f}%")
    
    # Save the cropped image
    cropped.save(output_path, 'PNG', optimize=True)
    print(f"[OK] Saved cropped image: {output_path}")
    return True


def main():
    if len(sys.argv) < 3:
        print("Usage: crop_png_manual.py <input.png> <output.png> [top] [right] [bottom] [left]")
        print("")
        print("Arguments:")
        print("  input.png   - Input PNG file")
        print("  output.png  - Output PNG file (can be same as input to overwrite)")
        print("  top         - Pixels to remove from top (default: 0)")
        print("  right       - Pixels to remove from right (default: 0)")
        print("  bottom      - Pixels to remove from bottom (default: 0)")
        print("  left        - Pixels to remove from left (default: 0)")
        print("")
        print("Examples:")
        print("  # Remove 300px from bottom, 200px from right")
        print("  crop_png_manual.py input.png output.png 0 200 300 0")
        print("")
        print("  # Remove 350px from bottom only")
        print("  crop_png_manual.py discord-card.png discord-card.png 0 0 350 0")
        return 1
    
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    
    top = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    right = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    bottom = int(sys.argv[5]) if len(sys.argv) > 5 else 0
    left = int(sys.argv[6]) if len(sys.argv) > 6 else 0
    
    if not input_path.exists():
        print(f"[ERROR] Input file not found: {input_path}")
        return 1
    
    try:
        success = crop_manual(input_path, output_path, top, right, bottom, left)
        return 0 if success else 1
    except Exception as e:
        print(f"[ERROR] Failed to crop image: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
