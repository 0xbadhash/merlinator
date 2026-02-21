#!/usr/bin/env python3
"""Debug script to analyze playlist.bin structure"""
import struct

def hex_dump(data, offset=0, length=256):
    """Print hex dump of binary data"""
    print(f"\n{'Offset':<10} {'Hex (16 bytes)':<50} {'ASCII'}")
    print("-" * 75)
    for i in range(0, min(length, len(data)), 16):
        chunk = data[i:i+16]
        hex_str = " ".join(f"{b:02x}" for b in chunk)
        ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        print(f"{offset+i:08x}   {hex_str:<48}   {ascii_str}")

def analyze_playlist(filepath):
    with open(filepath, 'rb') as f:
        data = f.read()
    
    print(f"📊 File size: {len(data)} bytes ({len(data)/1024:.1f} KB)")
    print(f"\n🔍 First 256 bytes:")
    hex_dump(data, 0, 256)
    
    print(f"\n🔍 Bytes 256-512:")
    hex_dump(data, 256, 256)
    
    # Try to find UUID patterns (look for hex digits and dashes)
    print(f"\n🔍 Searching for UUID patterns in first 2KB...")
    text = data[:2048].decode('utf-8', errors='ignore')
    import re
    uuids = re.findall(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', text, re.IGNORECASE)
    if uuids:
        print(f"✓ Found {len(uuids)} UUID-like strings:")
        for u in uuids[:10]:
            print(f"  - {u}")
    else:
        print("⚠ No UUID patterns found in plain text")
    
    # Try different entry sizes
    print(f"\n🔍 Testing entry sizes (looking for repeating patterns)...")
    for entry_size in [128, 138, 148, 158, 168, 178, 188, 198, 208, 256]:
        if len(data) >= entry_size * 3:
            e1 = data[0:entry_size]
            e2 = data[entry_size:entry_size*2]
            e3 = data[entry_size*2:entry_size*3]
            # Check if entries have similar structure (same byte patterns at same offsets)
            if e1[0:20] == e2[0:20] or e1[0:10] == e3[0:10]:
                print(f"⚠ Possible entry size: {entry_size} bytes (patterns match)")
    
    # Look for .mp3 references
    print(f"\n🔍 Searching for '.mp3' or file extensions...")
    if b'.mp3' in data[:2048]:
        idx = data[:2048].find(b'.mp3')
        print(f"✓ Found '.mp3' at offset {idx}")
        hex_dump(data, max(0, idx-32), 64)
    else:
        print("⚠ No '.mp3' found in first 2KB")
    
    # Look for the UUID from your output
    test_uuid = b'1c74e8f3-123e-4497-964b-6720f1817071'
    if test_uuid in data:
        idx = data.find(test_uuid)
        print(f"\n✓ Found your UUID '1c74e8f3...' at offset {idx} (0x{idx:x})")
        hex_dump(data, max(0, idx-64), 128)
    else:
        # Try without dashes
        test_uuid_nodash = b'1c74e8f3123e4497964b6720f1817071'
        if test_uuid_nodash in data:
            idx = data.find(test_uuid_nodash)
            print(f"\n✓ Found UUID (no dashes) at offset {idx} (0x{idx:x})")
            hex_dump(data, max(0, idx-64), 128)
        else:
            print(f"\n⚠ UUID '1c74e8f3...' not found in file")
            print("  The playlist.bin may store different/shorter IDs than filenames!")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 debug_playlist.py playlist.bin")
        sys.exit(1)
    analyze_playlist(sys.argv[1])