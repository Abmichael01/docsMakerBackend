import os
import sys
import logging
import xml.etree.ElementTree as ET

# Setup logging to match the app
logger = logging.getLogger("api.svg_parser")
logging.basicConfig(level=logging.INFO)

# Add the current directory to sys.path so we can import api modules
sys.path.append(os.getcwd())

from api.svg_parser import fix_svg_element_ids, parse_svg_to_form_fields

def reproduce():
    svg_path = "/home/urkelcodes/Desktop/MyProjects/Clients/sharptoolz/templates/Alabama DL (1).svg"
    
    if not os.path.exists(svg_path):
        print(f"Error: File not found at {svg_path}")
        return

    print(f"Reading {svg_path}...")
    with open(svg_path, 'r', encoding='utf-8') as f:
        svg_text = f.read()

    print(f"File size: {len(svg_text)} bytes")
    
    print("Running fix_svg_element_ids...")
    fixed_svg, num_fixes = fix_svg_element_ids(svg_text)
    print(f"Fixed {num_fixes} IDs.")

    print("Attempting to parse SVG...")
    try:
        # We'll call the actual function that fails
        fields = parse_svg_to_form_fields(fixed_svg)
        print(f"Successfully parsed {len(fields)} form fields.")
    except Exception as e:
        print(f"Caught exception during parse_svg_to_form_fields: {e}")
        
    # Also try direct ET parsing to see the exact error location again
    print("\nAttempting direct ET.fromstring...")
    try:
        ET.fromstring(fixed_svg)
        print("ET.fromstring success!")
    except ET.ParseError as e:
        print(f"ET.ParseError: {e}")
        line, col = e.position
        print(f"Location: Line {line}, Column {col}")
        
        # Extract a window around the error
        lines = fixed_svg.splitlines()
        if line <= len(lines):
            error_line = lines[line-1]
            start = max(0, col - 50)
            end = col + 50
            window = error_line[start:end]
            print(f"Context around error: ...{window}...")
            print(" " * (min(col, 50) + 21) + "^")

if __name__ == "__main__":
    reproduce()
