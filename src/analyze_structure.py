#!/usr/bin/env python3
"""
Merlin Playlist Binary Structure Analyzer
Finds exact UUID and Title field positions
"""
import struct
import re

ENTRY_SIZE = 256

def analyze_entry_structure(filepath, num_entries=5):
    """Analyze first few entries to find field positions"""
    
    with open(filepath, 'rb') as f:
        for entry_idx in range(min(num_entries, 10)):
            f.seek(entry_idx * ENTRY_SIZE)
            entry = f.read(ENTRY_SIZE)
            
            print(f"\n{'='*80}")
            print(f"ENTRY #{entry_idx}")
            print('='*80)
            
            # Search for UUID pattern (36 char UUID with dashes)
            uuid_pattern = rb'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
            uuid_matches = list(re.finditer(uuid_pattern, entry))
            
            if uuid_matches:
                print(f"\n🎯 UUID FOUND:")
                for m in uuid_matches:
                    uuid = m.group().decode('ascii')
                    offset = m.start()
                    print(f"   Offset: 0x{offset:02X} ({offset}) → {uuid}")
                    
                    # Show bytes around UUID
                    start = max(0, offset - 8)
                    end = min(len(entry), offset + 44)
                    print(f"   Context: {entry[start:end]}")
            else:
                print(f"\n⚠️  No UUID pattern found in this entry")
            
            # Search for readable text (potential titles)
            print(f"\n📝 Readable text sequences:")
            text_offsets = []
            i = 0
            while i < len(entry):
                if 32 <= entry[i] < 127:
                    start = i
                    while i < len(entry) and 32 <= entry[i] < 127:
                        i += 1
                    text = entry[start:i].decode('ascii', errors='ignore')
                    if len(text) >= 4:
                        text_offsets.append((start, text))
                        print(f"   Offset 0x{start:02X}: '{text[:50]}'")
                else:
                    i += 1
            
            # Show hex dump of key areas
            print(f"\n🔍 Hex dump of key areas:")
            for area_start in [0x90, 0xA0, 0xB0, 0xC0, 0xD0, 0xE0, 0xF0]:
                area = entry[area_start:area_start+16]
                ascii_repr = ''.join(chr(b) if 32 <= b < 127 else '.' for b in area)
                print(f"   0x{area_start:02X}: {area.hex(' ')}  |{ascii_repr}|")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_structure.py playlist.bin")
        sys.exit(1)
    
    print("🔍 Analyzing playlist.bin structure...\n")
    analyze_entry_structure(sys.argv[1])