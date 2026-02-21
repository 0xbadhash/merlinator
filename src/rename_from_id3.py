#!/usr/bin/env python3
"""
Merlin MP3 & Image Renamer
Renames MP3 files using ID3 tags and paired images (jpg/jpeg)
Safe dry-run mode by default - originals never modified
"""
import os
import shutil
import argparse
from pathlib import Path

try:
    from mutagen.id3 import ID3
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False

def get_title_from_id3(filepath):
    """Extract title from MP3 ID3 tags"""
    if not HAS_MUTAGEN:
        return None
    try:
        tags = ID3(filepath)
        # Priority: TIT2 (title) > TIT1 (content group) > TRCK (track)
        if 'TIT2' in tags:
            return str(tags['TIT2'].text[0])
        elif 'TIT1' in tags:
            return str(tags['TIT1'].text[0])
        elif 'TRCK' in tags:
            return str(tags['TRCK'].text[0])
    except Exception as e:
        pass
    return None

def sanitize_filename(title, max_length=60):
    """Make filename safe for filesystem + Merlin constraints"""
    if not title:
        return "unnamed"
    # Remove/replace invalid characters
    safe = "".join(c if c.isalnum() or c in " _-." else "_" for c in title)
    # Collapse multiple spaces/underscores
    while "  " in safe:
        safe = safe.replace("  ", " ")
    while "__" in safe:
        safe = safe.replace("__", "_")
    # Trim and ensure UTF-8 byte length ≤64 (Merlin limit)
    safe = safe.strip().strip("._-")
    while len(safe.encode('utf-8')) > max_length and safe:
        safe = safe[:-1]
    return safe or "unnamed"

def find_matching_image(mp3_path, source_folder):
    """Find JPEG/JPG image with same base name as MP3"""
    base_name = mp3_path.stem  # filename without extension
    source = Path(source_folder)
    
    # Check for .jpg and .jpeg (case-insensitive)
    for ext in ['.jpg', '.jpeg', '.JPG', '.JPEG']:
        img_path = source / f"{base_name}{ext}"
        if img_path.exists():
            return img_path
    return None

def get_unique_path(output_dir, base_name, extension):
    """Generate unique filename if target already exists"""
    dst_path = output_dir / f"{base_name}{extension}"
    if not dst_path.exists():
        return dst_path
    
    counter = 1
    while True:
        dst_path = output_dir / f"{base_name}_{counter}{extension}"
        if not dst_path.exists():
            return dst_path
        counter += 1

def main():
    parser = argparse.ArgumentParser(
        description="Rename MP3 files using ID3 tags + paired images (safe dry-run)"
    )
    parser.add_argument("source_folder", help="Folder containing MP3 (and optional JPG) files")
    parser.add_argument("-o", "--output", help="Output folder for renamed copies (required to apply)")
    parser.add_argument("-e", "--export", action="store_true", help="Export mapping to CSV")
    parser.add_argument("-t", "--types", type=str, default="mp3", 
                       help="File types to process (comma-separated, e.g., 'mp3' or 'mp3,jpg')")
    parser.add_argument("--no-images", action="store_true", help="Skip image files even if found")
    args = parser.parse_args()

    # Check dependencies
    if not HAS_MUTAGEN:
        print("⚠️  mutagen not installed. Install with: pip install mutagen")
        print("   Without it, files will keep original names.\n")
    
    # Validate inputs
    source = Path(args.source_folder)
    if not source.is_dir():
        print(f"❌ Error: source folder not found: {source}")
        return
    
    # Find all MP3 files
    mp3_files = sorted(list(source.glob("*.mp3")) + list(source.glob("*.MP3")))
    
    if not mp3_files:
        print(f"❌ No MP3 files found in: {source}")
        return
    
    # Build mapping
    print(f"\n🔍 Found {len(mp3_files)} MP3 files (DRY RUN - no changes made):\n")
    print(f"{'MP3 File':<45} → {'New Name':<40} {'Image':<10} {'Status':<8}")
    print("-" * 110)
    
    mapping = []
    for mp3 in mp3_files:
        # Get ID3 title
        id3_title = get_title_from_id3(str(mp3))
        
        if id3_title:
            new_base = sanitize_filename(id3_title)
            status = "✓"
        else:
            new_base = mp3.stem  # keep original name
            id3_title = "(no ID3)"
            status = "⚠"
        
        # Find matching image
        img_path = None if args.no_images else find_matching_image(mp3, source)
        img_status = "✓" if img_path else "✗"
        
        print(f"{mp3.name:<45} → {new_base:<40} {img_status:<10} {status:<8}")
        
        mapping.append({
            'mp3_src': mp3,
            'mp3_new': f"{new_base}.mp3",
            'img_src': img_path,
            'img_new': f"{new_base}{img_path.suffix.lower()}" if img_path else None,
            'id3_title': id3_title,
            'status': status
        })
    
    # Export CSV if requested
    if args.export:
        csv_path = "rename_mapping.csv"
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("mp3_original,mp3_new,image_original,image_new,id3_title,status\n")
            for m in mapping:
                img_orig = m['img_src'].name if m['img_src'] else ""
                img_new = m['img_new'] if m['img_new'] else ""
                f.write(f'"{m["mp3_src"].name}","{m["mp3_new"]}","{img_orig}","{img_new}","{m["id3_title"]}","{m["status"]}"\n')
        print(f"\n✓ Mapping exported to {csv_path}")
    
    # Apply changes if output folder provided
    if args.output:
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        confirm = input(f"\n⚠️  Copy renamed files to: {output_dir.resolve()} ? (type 'yes' to confirm): ").strip().lower()
        if confirm != "yes":
            print("✅ Operation cancelled. Original files untouched.")
            return
        
        print(f"\n📦 Copying and renaming files to: {output_dir}")
        mp3_count = 0
        img_count = 0
        skipped_img = 0
        
        for m in mapping:
            # Copy MP3
            mp3_dst = get_unique_path(output_dir, Path(m['mp3_new']).stem, '.mp3')
            try:
                shutil.copy2(m['mp3_src'], mp3_dst)
                print(f"✓ MP3: {m['mp3_src'].name} → {mp3_dst.name}")
                mp3_count += 1
            except Exception as e:
                print(f"✗ MP3 Error: {m['mp3_src'].name}: {e}")
            
            # Copy matching image if exists
            if m['img_src'] and not args.no_images:
                img_dst = get_unique_path(output_dir, Path(m['img_new']).stem, Path(m['img_new']).suffix)
                try:
                    shutil.copy2(m['img_src'], img_dst)
                    print(f"  └─ ✓ IMG: {m['img_src'].name} → {img_dst.name}")
                    img_count += 1
                except Exception as e:
                    print(f"  └─ ✗ IMG Error: {m['img_src'].name}: {e}")
            elif m['img_src'] is None:
                skipped_img += 1
        
        print(f"\n🎉 Done!")
        print(f"   📁 Output folder: {output_dir.resolve()}")
        print(f"   🎵 MP3 files copied: {mp3_count}/{len(mapping)}")
        print(f"   🖼️  Images copied: {img_count} (skipped: {skipped_img})")
        print("\n💡 Tip: Verify the new folder works with your Merlin device before deleting originals.")
    
    else:
        print(f"\n💡 To apply changes, re-run with: -o /path/to/new/folder")
        print(f"   Example: python3 rename_from_id3.py ./mp3s -o ./renamed_safe")

if __name__ == "__main__":
    main()