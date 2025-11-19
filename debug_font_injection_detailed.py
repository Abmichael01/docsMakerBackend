#!/usr/bin/env python3
"""
Detailed debug script to test font injection step by step
Shows exactly where the injection process fails
"""
import os, sys, django, base64, traceback, re
sys.path.insert(0, '/var/www/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'serverConfig.settings')
django.setup()

from api.models import Font
from api.font_injector import inject_fonts_into_svg, _extract_font_aliases, _normalize_font_key, _get_font_candidates, _build_font_face

test_svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600">
  <defs>
    <style type="text/css"><![CDATA[
      text { font-family: "OCR B", sans-serif; font-size: 24px; }
    ]]></style>
  </defs>
  <text x="100" y="300">Hello OCR B Font</text>
</svg>'''

font = Font.objects.filter(name__icontains='OCR').first()

print('=' * 80)
print('DETAILED FONT INJECTION DEBUG')
print('=' * 80)
print()

# Step 1: Check font
print('[1] Font Check')
print(f'Font name: {font.name}')
print(f'Font file: {font.font_file}')
print(f'Font format: {font.get_font_format()}')
print()

# Step 2: Check alias extraction
print('[2] Alias Map Extraction')
alias_map = _extract_font_aliases(test_svg)
print(f'Alias map: {alias_map}')
print()

# Step 3: Check font candidates
print('[3] Font Candidates')
candidates = _get_font_candidates(font)
print(f'Font candidates: {candidates}')
print()

# Step 4: Test matching
print('[4] Font Matching Test')
css_family = None
for candidate in candidates:
    key = _normalize_font_key(candidate)
    print(f'  Candidate: "{candidate}" -> normalized: "{key}" -> in map: {key in alias_map}')
    if key and key in alias_map:
        css_family = alias_map[key]
        print(f'  ✓ Matched candidate "{candidate}" -> CSS family: "{css_family}"')
        break

if not css_family:
    font_key = _normalize_font_key(font.name)
    if font_key and font_key in alias_map:
        css_family = alias_map[font_key]
        print(f'  ✓ Direct match -> CSS family: "{css_family}"')

if not css_family:
    css_family = font.name
    print(f'  Using fallback: "{css_family}"')
print()

# Step 5: Check font file reading
print('[5] Font File Reading Test')
font_url = None
embed_base64 = True

try:
    if not font.font_file:
        print('  ✗ ERROR: font.font_file is None!')
    else:
        print(f'  font.font_file: {font.font_file}')
        print('  Opening font file...')
        font.font_file.open("rb")
        try:
            font_data = font.font_file.read()
            print(f'  ✓ Font data read: {len(font_data)} bytes')
            
            font_base64 = base64.b64encode(font_data).decode('utf-8')
            print(f'  ✓ Base64 encoded: {len(font_base64)} chars')
            
            font_format = font.get_font_format()
            print(f'  Font format: {font_format}')
            
            mime_type_map = {
                'truetype': 'application/font-truetype',
                'opentype': 'application/font-opentype',
                'woff': 'application/font-woff',
                'woff2': 'application/font-woff2',
            }
            mime_type = mime_type_map.get(font_format, 'application/font-truetype')
            print(f'  MIME type: {mime_type}')
            
            font_url = f"data:{mime_type};base64,{font_base64}"
            print(f'  ✓ font_url created: {len(font_url)} chars')
            print(f'  Starts with "data:": {font_url.startswith("data:")}')
            
        finally:
            font.font_file.close()
            print('  Font file closed')
except Exception as e:
    print(f'  ✗ ERROR reading font: {e}')
    traceback.print_exc()
print()

# Step 6: Build font face
print('[6] Font Face CSS Generation')
if css_family and font_url:
    font_format = font.get_font_format()
    font_face = _build_font_face(css_family, font_url, font_format)
    print(f'  ✓ Font face CSS generated: {len(font_face)} chars')
    print(f'  Preview (first 300 chars):')
    print(f'  {font_face[:300]}...')
    print()
else:
    print('  ✗ Cannot generate font face - missing css_family or font_url')
    print(f'    css_family: {css_family}')
    print(f'    font_url: {"set" if font_url else "None/empty"}')
    print()

# Step 7: Test actual injection
print('[7] Actual Injection Test')
result = inject_fonts_into_svg(test_svg, [font], embed_base64=True)
print(f'  Original length: {len(test_svg)}')
print(f'  Result length: {len(result)}')
print(f'  Length changed: {len(result) != len(test_svg)}')
print(f'  @font-face in result: {"@font-face" in result}')
print()

if "@font-face" in result:
    # Extract the font-face declaration
    font_face_match = re.search(r'@font-face\s*\{[^}]+\}', result, re.DOTALL)
    if font_face_match:
        print('  ✓ SUCCESS: @font-face found in result!')
        print(f'  Preview:')
        print(f'  {font_face_match.group(0)[:300]}...')
    else:
        print('  ⚠ @font-face string found but no valid declaration matched')
else:
    print('  ✗ FAILURE: Font was NOT injected')
    print()
    print('  Checking why inject_fonts_into_svg returned unchanged SVG...')
    print()
    
    # Check defs matching
    defs_pattern = re.compile(r'(<defs[^>]*>)(.*?)(</defs>)', re.IGNORECASE | re.DOTALL)
    defs_match = defs_pattern.search(test_svg)
    print(f'  <defs> section found: {defs_match is not None}')
    if defs_match:
        print(f'  <defs> content length: {len(defs_match.group(2))}')
        
        # Check style matching within defs
        style_pattern = re.compile(r'(<style[^>]*>)(<!\[CDATA\[)?(.*?)(\]\]>)?(</style>)', re.IGNORECASE | re.DOTALL)
        style_match = style_pattern.search(defs_match.group(2))
        print(f'  <style> block found in defs: {style_match is not None}')
        if style_match:
            print(f'  Style content length: {len(style_match.group(3))}')
            print(f'  Style content preview: {style_match.group(3)[:100]}...')
            # Check if @font-face already exists
            if '@font-face' in style_match.group(3):
                print('  ⚠ WARNING: @font-face already exists in style block!')
            
            # Check for existing font families
            existing_font_face_pattern = re.compile(r'font-family\s*:\s*["\']([^"\']+)["\']', re.IGNORECASE)
            existing_families = set()
            for match in existing_font_face_pattern.findall(style_match.group(3)):
                existing_families.add(_normalize_font_key(match))
            print(f'  Existing font families in @font-face: {existing_families}')
            
            font_key = _normalize_font_key("OCR B")
            print(f'  OCR B normalized key: "{font_key}"')
            print(f'  Already in existing families: {font_key in existing_families}')
    else:
        print('  No <defs> section - should create new one')

print()
print('=' * 80)
print('DEBUG COMPLETE')
print('=' * 80)
