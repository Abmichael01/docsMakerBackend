from api.svg_parser import parse_svg_to_form_fields

# Test SVG with mixed field types in specific order
test_svg = '''
<svg>
    <text id="Company_Name.text">Sample Company</text>
    <text id="Country.select_USA">USA</text>
    <text id="Reference_Code.gen.max_8">ABC123</text>
    <text id="Country.select_Canada">Canada</text>
    <text id="City.depends_Country">New York</text>
    <text id="Tracking_ID.gen.max_12.link_https://example.com/track">TRK123456789</text>
</svg>
'''

print("Testing SVG parser...")
result = parse_svg_to_form_fields(test_svg)
print(f"Found {len(result)} fields")

print("=== SVG Parser Test Results ===")
for i, field in enumerate(result, 1):
    print(f"{i}. {field['id']} ({field['type']})")
    if field['type'] == 'select':
        print(f"   Options: {[opt['label'] for opt in field['options']]}")
    if 'link' in field:
        print(f"   Link: {field['link']}")
    if 'dependsOn' in field:
        print(f"   Depends on: {field['dependsOn']}")
    if 'max' in field:
        print(f"   Max: {field['max']}")
    print()
