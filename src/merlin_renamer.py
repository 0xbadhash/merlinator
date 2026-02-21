#!/usr/bin/env python3
"""
Merlin Playlist Renamer - FINAL v6.1
Preserves apostrophes and ALL accented characters (é, è, ê, ë, à, â, ä, ù, û, ü, ï, î, ô, ö, ç, etc.)
"""
import struct
import os
import shutil
import argparse
import re
from pathlib import Path

try:
    from mutagen.id3 import ID3
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False

ENTRY_SIZE = 256
UUID_MARKER = b'La\x94i$'
UUID_PATTERN = rb'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'

# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def sanitize_filename(title, max_length=60):
    """
    Make filename safe while PRESERVING:
    - Apostrophes (')
    - ALL accented characters (é, è, ê, ë, à, â, ä, ù, û, ü, ï, î, ô, ö, ç, É, È, etc.)
    - Spaces, hyphens, underscores, periods
    """
    if not title:
        return "unnamed"
    
    # Characters to REMOVE (invalid on Windows/filesystems)
    # \ / : * ? " < > | and control chars
    invalid_chars = r'[\\/:*?"<>|\x00-\x1f]'
    safe = re.sub(invalid_chars, '_', title)
    
    # Collapse multiple spaces/underscores
    while "  " in safe: safe = safe.replace("  ", " ")
    while "__" in safe: safe = safe.replace("__", "_")
    
    # Trim (but keep apostrophes and accents!)
    safe = safe.strip().strip("._-")
    
    # Ensure UTF-8 byte length ≤64 (Merlin limit)
    # Note: accented chars count as 2 bytes each in UTF-8
    while len(safe.encode('utf-8')) > max_length and safe:
        safe = safe[:-1]
    
    return safe or "unnamed"

def is_uuid_like(text):
    """Check if text looks like a UUID (should not be used as title)"""
    if not text:
        return False
    if re.search(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}', text):
        return True
    hex_chars = sum(1 for c in text if c in '0123456789abcdefABCDEF-')
    if len(text) > 10 and hex_chars / len(text) > 0.7:
        return True
    return False

def find_uuids_in_entry(entry):
    """Find all UUIDs in an entry"""
    uuids = []
    for match in re.finditer(UUID_PATTERN, entry):
        uuid = match.group().decode('ascii')
        offset = match.start()
        has_marker = False
        for marker_offset in range(max(0, offset - 5), offset):
            if entry[marker_offset:marker_offset + len(UUID_MARKER)] == UUID_MARKER:
                has_marker = True
                break
        uuids.append({'uuid': uuid, 'offset': offset, 'has_marker': has_marker})
    return uuids

def extract_title_from_entry(entry, uuid_offsets):
    """Extract title text with proper UTF-8 decoding"""
    text_sequences = []
    i = 0
    
    while i < len(entry):
        if entry[i] >= 32:
            start = i
            while i < len(entry) and entry[i] >= 32:
                i += 1
            
            try:
                text = entry[start:i].decode('utf-8').strip()
                
                if len(text) >= 8:
                    if not is_uuid_like(text):
                        if sum(1 for c in text if c.isalpha()) >= 3:
                            text_sequences.append({'offset': start, 'text': text})
            except UnicodeDecodeError:
                try:
                    text = entry[start:i].decode('latin-1').strip()
                    if len(text) >= 8 and not is_uuid_like(text):
                        if sum(1 for c in text if c.isalpha()) >= 3:
                            text_sequences.append({'offset': start, 'text': text})
                except:
                    pass
        else:
            i += 1
    
    if text_sequences:
        text_sequences.sort(key=lambda x: len(x['text']), reverse=True)
        return text_sequences[0]['text']
    
    return ""

def read_merlin_playlist(filepath):
    """Parse playlist.bin"""
    items = []
    file_size = os.path.getsize(filepath)
    num_entries = file_size // ENTRY_SIZE
    
    print(f"📊 File size: {file_size} bytes")
    print(f"📊 Expected entries: {num_entries}")
    
    with open(filepath, 'rb') as f:
        for i in range(num_entries):
            f.seek(i * ENTRY_SIZE)
            entry = f.read(ENTRY_SIZE)
            
            if len(entry) < ENTRY_SIZE:
                break
            
            uuids = find_uuids_in_entry(entry)
            
            if len(uuids) >= 1:
                uuid_with_marker = [u for u in uuids if u['has_marker']]
                file_uuid = uuid_with_marker[0]['uuid'] if uuid_with_marker else uuids[0]['uuid']
                title = extract_title_from_entry(entry, uuids)
                
                items.append({
                    'index': i,
                    'uuid': file_uuid,
                    'pl_title': title,
                    'all_uuids': [u['uuid'] for u in uuids]
                })
    
    return items

def get_id3_title(filepath):
    """Extract title from ID3 tags - PRIORITY SOURCE"""
    if not HAS_MUTAGEN:
        return None
    try:
        tags = ID3(filepath)
        for tag in ['TIT2', 'TIT1', 'TALB']:
            if tag in tags:
                text = str(tags[tag].text[0])
                if text and len(text) >= 3:
                    return text
    except:
        pass
    return None

def find_matching_image(mp3_path, source_folder):
    if not mp3_path or not mp3_path.exists():
        return None
    base_name = mp3_path.stem
    source = Path(source_folder)
    for ext in ['.jpg', '.jpeg', '.JPG', '.JPEG']:
        img_path = source / f"{base_name}{ext}"
        if img_path.exists():
            return img_path
    return None

def get_unique_path(output_dir, base_name, extension):
    dst_path = output_dir / f"{base_name}{extension}"
    if not dst_path.exists():
        return dst_path
    counter = 1
    while True:
        dst_path = output_dir / f"{base_name}_{counter}{extension}"
        if not dst_path.exists():
            return dst_path
        counter += 1

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Merlin playlist renamer (FINAL v6.1 - preserves accents & apostrophes)")
    parser.add_argument("playlist", help="Path to playlist.bin")
    parser.add_argument("source_folder", help="Folder containing MP3 files")
    parser.add_argument("-o", "--output", help="Output folder for renamed copies")
    parser.add_argument("-e", "--export", action="store_true", help="Export to CSV")
    parser.add_argument("--no-images", action="store_true", help="Skip images")
    parser.add_argument("--id3-only", action="store_true", help="Use ID3 tags only")
    args = parser.parse_args()

    if not HAS_MUTAGEN:
        print("⚠️  mutagen not installed. Install: pip install mutagen\n")
    
    if not os.path.isfile(args.playlist):
        print(f"❌ playlist.bin not found: {args.playlist}")
        return
    if not os.path.isdir(args.source_folder):
        print(f"❌ Source folder not found: {args.source_folder}")
        return

    print(f"\n🔍 Parsing {args.playlist}...\n")
    items = read_merlin_playlist(args.playlist)
    
    if not items:
        print("⚠️  No valid entries found")
        return
    
    print(f"✅ Found {len(items)} valid entries\n")
    
    # Build mapping with ID3 PRIORITY
    print(f"🔍 Matching MP3 files (DRY RUN):\n")
    
    # FIX: Move special chars outside f-string to avoid backslash error
    header_note = "Title (preserves é è ê ë à â ä ù û ü ï î ô ö ç ')"
    print(f"{'UUID':<40} → {header_note:<55} {'MP3':<6}")
    print("-" * 105)
    
    mapping = []
    for item in items:
        uuid = item['uuid']
        src_mp3 = Path(args.source_folder) / f"{uuid}.mp3"
        mp3_exists = src_mp3.exists()
        
        id3_title = get_id3_title(str(src_mp3)) if mp3_exists and HAS_MUTAGEN else None
        pl_title = item['pl_title'] if not args.id3_only else None
        
        if id3_title:
            final_title = id3_title
            title_source = 'ID3'
        elif pl_title and not is_uuid_like(pl_title):
            final_title = pl_title
            title_source = 'PLAYLIST'
        else:
            final_title = uuid
            title_source = 'UUID'
        
        safe_title = sanitize_filename(final_title)
        img_path = None if args.no_images else find_matching_image(src_mp3, args.source_folder)
        
        title_display = f"{safe_title[:52]}..." if len(safe_title) > 55 else safe_title
        source_marker = f"[{title_source}]"
        
        print(f"{uuid:<40} → {title_display:<55} {source_marker:<6} {'✓' if mp3_exists else '✗':<6}")
        
        mapping.append({
            'uuid': uuid,
            'final_title': safe_title,
            'id3_title': id3_title,
            'pl_title': pl_title,
            'title_source': title_source,
            'mp3_src': src_mp3,
            'mp3_exists': mp3_exists,
            'img_src': img_path
        })
    
    # Summary
    mp3_found = sum(1 for m in mapping if m['mp3_exists'])
    img_found = sum(1 for m in mapping if m['img_src'])
    id3_count = sum(1 for m in mapping if m['title_source'] == 'ID3')
    pl_count = sum(1 for m in mapping if m['title_source'] == 'PLAYLIST')
    uuid_count = sum(1 for m in mapping if m['title_source'] == 'UUID')
    
    print(f"\n{'='*105}")
    print(f"📊 SUMMARY:")
    print(f"   Total entries:     {len(items)}")
    print(f"   MP3 files found:   {mp3_found}/{len(items)}")
    print(f"   Images found:      {img_found}/{len(items)}")
    print(f"\n   Title sources:")
    print(f"      🎵 From ID3:     {id3_count}")
    print(f"      📋 From Playlist: {pl_count}")
    print(f"      🔖 From UUID:    {uuid_count}")
    
    if args.export:
        with open("playlist_mapping.csv", "w", encoding="utf-8") as f:
            f.write("uuid,final_title,id3_title,playlist_title,title_source,mp3_exists,image_exists\n")
            for m in mapping:
                f.write(f'"{m["uuid"]}","{m["final_title"]}","{m["id3_title"] or ""}",'
                        f'"{m["pl_title"] or ""}","{m["title_source"]}",'
                        f'{m["mp3_exists"]},{m["img_src"] is not None}\n')
        print(f"\n✓ Exported to playlist_mapping.csv")
    
    if args.output:
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        confirm = input(f"\n⚠️  Copy to {output_dir}? (type 'yes'): ").strip().lower()
        if confirm != "yes":
            print("✅ Cancelled")
            return
        
        mp3_count = img_count = skipped = 0
        for m in mapping:
            if not m['mp3_exists']:
                skipped += 1
                continue
            
            mp3_dst = get_unique_path(output_dir, m['final_title'], '.mp3')
            shutil.copy2(m['mp3_src'], mp3_dst)
            mp3_count += 1
            print(f"✓ {m['uuid']}.mp3 → {mp3_dst.name}")
            
            if m['img_src']:
                img_dst = get_unique_path(output_dir, m['final_title'], m['img_src'].suffix.lower())
                shutil.copy2(m['img_src'], img_dst)
                img_count += 1
                print(f"  └─ {m['img_src'].name} → {img_dst.name}")
        
        print(f"\n🎉 Done!")
        print(f"   Output: {output_dir.resolve()}")
        print(f"   MP3: {mp3_count} | Images: {img_count} | Skipped: {skipped}")
    else:
        print(f"\n💡 To apply: python3 merlin_renamer.py playlist.bin ./mp3s -o ./renamed_safe")

if __name__ == "__main__":
    main()