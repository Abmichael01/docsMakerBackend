"""
Test script to trace what happens when New York_DL1.svg is processed by the backend.
Simulates the full save flow to find where elements/IDs are stripped.

Run: cd backend && python -c "import django; django.setup()" && python scripts/test_gen_bug.py
Or:  cd backend && DJANGO_SETTINGS_MODULE=backend.settings python scripts/test_gen_bug.py
"""
import os, sys, re

# Django setup
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
import django
django.setup()

from api.svg_parser import fix_svg_element_ids, parse_svg_to_form_fields
from api.svg_utils import apply_svg_patches

SVG_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'templates', 'New York_DL1.svg')
SAVED_PATH = os.path.join(os.path.dirname(__file__), '..', 'media', 'templates', 'svgs', 'd5f65614-2fd1-4101-b896-f13ca1157826.svg')

def count_ids(svg_text: str) -> list:
    """Extract all id= values from SVG text."""
    return re.findall(r'\bid\s*=\s*["\']([^"\']+)["\']', svg_text)

def count_data_ids(svg_text: str) -> list:
    """Extract all data-internal-id= values from SVG text."""
    return re.findall(r'data-internal-id\s*=\s*["\']([^"\']+)["\']', svg_text)

def count_gen_ids(ids: list) -> list:
    return [i for i in ids if '.gen' in i]

def count_elements_by_tag(svg_text: str) -> dict:
    """Count SVG elements by tag."""
    tags = re.findall(r'<(\w+)[\s/>]', svg_text)
    counts = {}
    for t in tags:
        counts[t] = counts.get(t, 0) + 1
    return counts

print("=" * 80)
print("TEST: New York_DL1.svg Backend Processing")
print("=" * 80)

# Step 0: Read original SVG
with open(SVG_PATH, 'r', errors='replace') as f:
    original_svg = f.read()

ids_before = count_ids(original_svg)
gen_ids = count_gen_ids(ids_before)
data_ids = count_data_ids(original_svg)

print(f"\n--- STEP 0: Original SVG ---")
print(f"  Size: {len(original_svg):,} bytes")
print(f"  Total IDs: {len(ids_before)}")
print(f"  .gen IDs: {len(gen_ids)}")
print(f"  data-internal-id attrs: {len(data_ids)}")
print(f"  All IDs: {ids_before[:10]}{'...' if len(ids_before) > 10 else ''}")

# Step 1: fix_svg_element_ids (what backend does on upload)
print(f"\n--- STEP 1: fix_svg_element_ids() ---")
fixed_svg, fixes_made = fix_svg_element_ids(original_svg)
ids_after_fix = count_ids(fixed_svg)
print(f"  Fixes made: {fixes_made}")
print(f"  Total IDs after fix: {len(ids_after_fix)}")
print(f"  IDs lost: {len(ids_before) - len(ids_after_fix)}")
if len(ids_after_fix) != len(ids_before):
    lost = set(ids_before) - set(ids_after_fix)
    gained = set(ids_after_fix) - set(ids_before)
    print(f"  Lost IDs: {lost}")
    print(f"  Gained IDs: {gained}")

# Step 2: parse_svg_to_form_fields
print(f"\n--- STEP 2: parse_svg_to_form_fields() ---")
form_fields = parse_svg_to_form_fields(fixed_svg)
print(f"  Form fields generated: {len(form_fields)}")
for f in form_fields[:5]:
    print(f"    - {f.get('id')}: type={f.get('type')}, svgElementId={f.get('svgElementId')}")
if len(form_fields) > 5:
    print(f"    ... and {len(form_fields) - 5} more")

# Step 3: Check the saved SVG (current state in media folder)
if os.path.exists(SAVED_PATH):
    print(f"\n--- STEP 3: Currently Saved SVG (media folder) ---")
    with open(SAVED_PATH, 'r', errors='replace') as f:
        saved_svg = f.read()
    saved_ids = count_ids(saved_svg)
    saved_data_ids = count_data_ids(saved_svg)
    print(f"  Size: {len(saved_svg):,} bytes")
    print(f"  Total IDs: {len(saved_ids)}")
    print(f"  data-internal-id attrs: {len(saved_data_ids)}")
    print(f"  All IDs: {saved_ids}")
    if saved_data_ids:
        print(f"  data-internal-ids: {saved_data_ids[:5]}{'...' if len(saved_data_ids) > 5 else ''}")
else:
    print(f"\n--- STEP 3: No saved SVG found at {SAVED_PATH} ---")

# Step 4: Simulate the full flow — fix IDs then check regex behavior
print(f"\n--- STEP 4: Regex deep dive ---")
# Check if fix_svg_element_ids regex can match data-internal-id
id_pattern = r'(id\s*=\s*["\'])([^"\']+)(["\'])'
test_line = 'data-internal-id="Picture1.upload.grayscale.depends_Picture" id="Picture1.upload.grayscale.depends_Picture"'
matches = list(re.finditer(id_pattern, test_line))
print(f"  Test line: {test_line}")
print(f"  Regex matches ({len(matches)}):")
for m in matches:
    print(f"    Match at {m.start()}: full='{m.group(0)}' value='{m.group(2)}'")
    # Show what substring of the attribute name this is inside
    before = test_line[:m.start()]
    if before.endswith('data-internal-'):
        print(f"    ⚠️  THIS IS INSIDE data-internal-id (false positive!)")

# Step 5: Check what fix_svg_element_ids does to a line with data-internal-id
print(f"\n--- STEP 5: Does fix_svg_element_ids corrupt data-internal-id? ---")
test_svg = '<svg><image data-internal-id="Picture1.upload.grayscale.depends_Picture" id="Picture1.upload.grayscale.depends_Picture"/></svg>'
fixed_test, n = fix_svg_element_ids(test_svg)
print(f"  Before: {test_svg}")
print(f"  After:  {fixed_test}")
print(f"  Fixes:  {n}")

# Check if data-internal-id was also modified
orig_data_id = re.search(r'data-internal-id="([^"]+)"', test_svg)
fixed_data_id = re.search(r'data-internal-id="([^"]+)"', fixed_test)
if orig_data_id and fixed_data_id:
    if orig_data_id.group(1) != fixed_data_id.group(1):
        print(f"  ⚠️  BUG: data-internal-id WAS MODIFIED!")
        print(f"     Original: {orig_data_id.group(1)}")
        print(f"     Fixed:    {fixed_data_id.group(1)}")
    else:
        print(f"  ✓ data-internal-id unchanged")

print(f"\n{'=' * 80}")
print("TEST COMPLETE")
print("=" * 80)
