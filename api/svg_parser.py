import xml.etree.ElementTree as ET
import logging
import re
from typing import Optional, Dict, List, Any, Tuple

logger = logging.getLogger(__name__)

# ============================================================================
# EXTENSION REGISTRY - Central configuration for all supported extensions
# ============================================================================

FIELD_TYPES = [
    "text", "textarea", "checkbox", "date", "upload",
    "number", "email", "tel", "gen", "password",
    "range", "color", "file", "status", "sign"
]

EXTENSION_PREFIXES = {
    "max_": "max_value",       # Character/number limit
    "depends_": "dependency",   # Field synchronization with extraction support
    "track_": "tracking_role",  # Tracking role mapping
    "select_": "select_option", # Dropdown option
    "link_": "link_url",        # External link
    "date_": "date_format",     # Date format specification (MM/DD/YYYY, MMM_DD, etc.)
    "gen_": "generation_rule",  # Generation rule (rn[12], rc[6], etc.)
}

FLAG_EXTENSIONS = [
    "editable",     # Editable after purchase
    "tracking_id",  # Mark as tracking ID field
    "hide_checked", # Hide field (visible by default)
    "hide_unchecked" # Hide field (hidden by default)
]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def fix_svg_element_ids(svg_content: str) -> Tuple[str, int]:
    """
    Fix invalid element IDs where extensions are in wrong order.

    Specifically fixes:
    - .upload.grayscale.depends_XXX → .depends_XXX.upload.grayscale
    - .file.grayscale.depends_XXX → .depends_XXX.file.grayscale
    - Any pattern where .depends_ is not first after base ID

    Returns:
        tuple: (fixed_svg_content, number_of_fixes_made)
    """
    print("[SVG-ID-Fixer] Starting ID fix scan...")
    fixes_info = [0]

    # Pattern to match element IDs with attributes
    # Matches: id="something.something" or id='something.something'
    id_pattern = r'(id\s*=\s*["\'])([^"\']+)(["\'])'

    def fix_id(match):
        prefix = match.group(1)
        element_id = match.group(2)
        suffix = match.group(3)

        # Skip if no dots (no extensions)
        if '.' not in element_id:
            return match.group(0)

        parts = element_id.split('.')
        base_id = parts[0]
        extensions = parts[1:]

        # Check if we have a depends_ extension (catch typos like depend_)
        raw_depends = next((e for e in extensions if e.startswith('depends_') or e.startswith('depend_')), None)
        
        if raw_depends:
            # Canonicalize to "depends_"
            if raw_depends.startswith('depend_') and not raw_depends.startswith('depends_'):
                depends_val = f"depends_{raw_depends[7:]}" # Fix typo
            else:
                depends_val = raw_depends

            # RULE: When depends_ is present, it REPLACES the field type.
            # We must remove .upload, .text, .file, .textarea, etc.
            # and any other modifiers that are forbidden with depends_ (except grayscale/track_)
            
            # Forbidden prefixes when depends_ is present
            forbidden_prefixes = ("text", "upload", "file", "textarea", "number", "email", "tel", "gen", "sign", "status")
            
            # Filter extensions: Keep only those that are NOT forbidden and NOT the depends itself (we'll re-insert it)
            # but preserve grayscale and track_
            fixed_extensions = []
            track_val = next((e for e in extensions if e.startswith('track_')), None)
            
            # We only keep grayscale and track_ when depends is present
            # (Plus any other safe modifiers we want to allow, but user said "only grayscale/track_ after depends")
            for ext in extensions:
                if ext == depends_val: continue
                if ext == track_val: continue
                
                # If it's grayscale or starts with grayscale_, keep it
                if ext == "grayscale" or ext.startswith("grayscale_"):
                    fixed_extensions.append(ext)
                # If it's NOT a forbidden type, we *might* keep it, but per DSL only a few are allowed.
                # To be safe and meet user request "upload can never be there", we strip all types.
                elif not any(ext.startswith(p) for p in forbidden_prefixes):
                    # We skip other modifiers for now to keep depends_ clean as per DSL
                    pass
            
            # Re-assemble: [depends, ...fixed..., track]
            final_extensions = [depends_val] + fixed_extensions
            if track_val:
                final_extensions.append(track_val)
                
            new_id = f"{base_id}.{'.'.join(final_extensions)}"
            
            if new_id != element_id:
                print(f"[SVG-ID-Fixer] Fixed: {element_id} → {new_id}")
                fixes_info[0] += 1
                return f'{prefix}{new_id}{suffix}'
            return match.group(0)

        # Legacy logic: If no depends_, just check for track_ position
        # (Though track position is usually handled by elements, we can add a fix here if needed)
        
        return match.group(0)

        return match.group(0)

    fixed_svg = re.sub(id_pattern, fix_id, svg_content)
    print(f"[SVG-ID-Fixer] Completed. Fixed {fixes_info[0]} IDs.")

    return fixed_svg, fixes_info[0]


def extract_link_url(element_id: str) -> tuple[str, Optional[str]]:
    """
    Extract link URL from element ID and return cleaned ID.
    Supports both legacy link_URL and new link_"URL" syntax.
    URLs are extracted BEFORE splitting by dots to preserve URL structure.
    
    Returns:
        tuple: (cleaned_element_id, url)
    """
    if ".link_\"" in str(element_id):
        # New syntax: .link_"URL"
        id_str = str(element_id)
        start = id_str.find(".link_\"")
        url_start = start + 7  # len(".link_\"")
        url_end = id_str.find("\"", url_start)
        
        if url_end != -1:
            url = id_str[url_start:url_end]
            # Remove link portion and join parts before and after
            cleaned_id = id_str[:start] + id_str[url_end + 1:]
            return cleaned_id, url

    if ".link_" not in str(element_id):
        return str(element_id), None
    
    id_str = str(element_id)
    link_start = id_str.index(".link_")
    url_start = link_start + 6  # 6 = len(".link_")
    url = id_str[url_start:]
    cleaned_id = id_str[:link_start]
    
    return cleaned_id, url


def is_element_visible(element: ET.Element) -> bool:
    """
    Check if an SVG element is visible based on its attributes.
    """
    opacity = element.attrib.get("opacity", "1")
    visibility = element.attrib.get("visibility", "visible")
    display = element.attrib.get("display", "")
    
    return not (opacity == "0" or visibility == "hidden" or display == "none")


def get_extension_value(part: str, prefix: str) -> str:
    """
    Extract value from an extension part.
    Example: get_extension_value("max_50", "max_") -> "50"
    """
    return part.replace(prefix, "")


# ============================================================================
# SVG ID VALIDATION — extracted to svg_validator.py for clean code
# ============================================================================
from .svg_validator import (
    VALID_TYPES,
    VALID_MODIFIER_PREFIXES as VALID_MODIFIERS,
    FLAG_EXTENSIONS as VALIDATOR_FLAG_EXTENSIONS,
    ALLOWED_AFTER,
    validate_svg_id,
    validate_track_position,
)



def get_field_name(base_id: str) -> str:
    """
    Convert base_id to human-readable name.
    Example: "customer_name" -> "Customer Name"
    """
    return base_id.replace("_", " ").title()


# ============================================================================
# SELECT FIELD HANDLING
# ============================================================================

def create_select_option(element_id: str, element: ET.Element, parts: List[str], option_text: str = "") -> Dict[str, Any]:
    """
    Create a select option dictionary from element data.
    """
    select_part = next(p for p in parts if p.startswith("select_"))
    # Technical value is the extension value (e.g., 'usa' from '.select_usa')
    value = get_extension_value(select_part, "select_")
    # Label is the element text (e.g., 'United States'), fallback to formatted key
    label = option_text.strip() or value.replace("_", " ").title()
    
    return {
        "value": value,
        "label": label,
        "svgElementId": element_id,
        "displayText": option_text.strip() or label
    }


def extract_select_modifiers(parts: List[str]) -> Dict[str, Any]:
    """
    Extract tracking role and editable flag from select option parts.
    """
    tracking_role = None
    editable = False
    
    track_part = next((p for p in parts if p.startswith("track_")), None)
    if track_part:
        tracking_role = get_extension_value(track_part, "track_")
    
    if "editable" in parts:
        editable = True
    
    return {
        "tracking_role": tracking_role,
        "editable": editable
    }


def create_select_field(base_id: str, element_id: str, editable: bool) -> Dict[str, Any]:
    """
    Create a new select field dictionary.
    """
    return {
        "id": base_id,
        "name": get_field_name(base_id),
        "type": "select",
        "svgElementId": element_id,
        "options": [],
        "defaultValue": "",
        "currentValue": "",
        "editable": editable,
    }


def update_select_field(field: Dict[str, Any], option: Dict[str, Any], 
                       is_visible: bool, modifiers: Dict[str, Any]):
    """
    Update select field with new option and modifiers.
    """
    curr_before = field.get("currentValue")
    # Set currentValue to visible option (the one shown in SVG)
    # Only set if not already set, so we don't default to the last visible option encountered
    if is_visible and not field.get("currentValue"):
        field["currentValue"] = option["value"]
        logger.info(f"[Select-Parser] Setting currentValue for {field['id']} to {option['value']} (visible: {is_visible}, before: '{curr_before}')")
    
    # Set defaultValue to first option if not set
    if not field.get("defaultValue") and field["options"]:
        field["defaultValue"] = field["options"][0]["value"]
        logger.info(f"[Select-Parser] Setting defaultValue for {field['id']} to {field['defaultValue']} (options_count: {len(field['options'])})")
    
    # Set tracking role if present
    if modifiers["tracking_role"]:
        field["trackingRole"] = modifiers["tracking_role"]
    
    # Set editable if any option has it
    if modifiers["editable"]:
        field["editable"] = True


# ============================================================================
# REGULAR FIELD HANDLING
# ============================================================================

def parse_field_extensions(parts: List[str]) -> Dict[str, Any]:
    """
    Parse all extensions from parts and return extracted values.
    """
    result = {
        "field_type": parts[0],  # Default to base_id
        "max_value": None,
        "dependency": None,
        "tracking_role": None,
        "date_format": None,
        "generation_rule": None,
        "editable": False,
        "is_tracking_id": False,
        "requires_grayscale": False,
        "grayscale_intensity": None,
    }
    
    for part in parts[1:]:
        # Handle prefixed extensions
        if part.startswith("max_"):
            # Check if this is a max_ with generation rule like max_(A[10])
            max_content = get_extension_value(part, "max_")
            if max_content.startswith("(") and max_content.endswith(")"):
                # This is a generation rule for padding, e.g., max_(A[10])
                result["max_generation"] = max_content
            else:
                try:
                    result["max_value"] = str(max_content)
                except ValueError:
                    pass
        
        elif part.startswith("depends_"):
            # Extract dependency with optional extraction pattern
            # e.g., "field_name[w1]" or "field_name[ch1-4]"
            result["dependency"] = get_extension_value(part, "depends_")
        
        elif part.startswith("track_"):
            # Only set if it's the last extension
            if parts.index(part) == len(parts) - 1:
                result["tracking_role"] = get_extension_value(part, "track_")
        
        elif part.startswith("date_"):
            # Extract date format (e.g., "MM/DD/YYYY" from "date_MM/DD/YYYY" or "MMM_DD" from "date_MMM_DD")
            # Keep underscores as-is; frontend will convert them to spaces
            date_format = get_extension_value(part, "date_")
            result["date_format"] = date_format
            # If date_FORMAT is specified, field type should be "date"
            if result["field_type"] == parts[0]:  # Only set if not already set by another extension
                result["field_type"] = "date"
        
        elif part.startswith("gen_"):
            # Extract generation rule
            # e.g., "gen_(rn[12])" or "gen_FL(rn[12])(rc[6])"
            result["generation_rule"] = get_extension_value(part, "gen_")
            # Set field type to gen if not already set
            if result["field_type"] == parts[0]:
                result["field_type"] = "gen"
        
        # Handle flag extensions
        elif part == "tracking_id":
            result["field_type"] = "gen"
            result["is_tracking_id"] = True
        
        elif part == "editable":
            result["editable"] = True

        if part == "grayscale":
            result["requires_grayscale"] = True
            result["grayscale_intensity"] = "100"

        elif part.startswith("grayscale_"):
            result["requires_grayscale"] = True
            intensity_raw = get_extension_value(part, "grayscale_")
            try:
                intensity_value = int(float(intensity_raw))
                result["grayscale_intensity"] = str(max(0, min(100, intensity_value)))
            except ValueError:
                logger.warning(
                    "Invalid grayscale intensity '%s' on element '%s'; defaulting to 100",
                    intensity_raw,
                    parts[0],
                )
                result["grayscale_intensity"] = "100"

        # Handle field type extensions
        elif part.startswith("hide") or part in FIELD_TYPES:
            result["field_type"] = "hide" if part.startswith("hide") else part
    
    if result["requires_grayscale"] and result["grayscale_intensity"] is None:
        result["grayscale_intensity"] = "100"

    return result


def get_default_value(field_type: str, text_content: str, parts: List[str]) -> Any:
    """
    Determine the default value based on field type.
    """
    if field_type == "checkbox":
        return False
    
    elif field_type == "hide":
        hide_part = next((p for p in parts if p.startswith("hide")), "hide")
        return hide_part == "hide_checked"
    
    else:
        return text_content


def create_regular_field(base_id: str, element_id: str, extensions: Dict[str, Any], 
                        default_value: Any, url: Optional[str], helper_text: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a regular (non-select) field dictionary.
    """
    field = {
        "id": base_id,
        "name": get_field_name(base_id),
        "type": extensions["field_type"],
        "svgElementId": element_id,
        "defaultValue": default_value,
        "currentValue": default_value,
        "isTrackingId": extensions["is_tracking_id"],
        "editable": extensions["editable"],
    }
    
    # Add optional properties
    if extensions["tracking_role"]:
        field["trackingRole"] = extensions["tracking_role"]
    
    if extensions["max_value"] is not None:
        field["max"] = extensions["max_value"]
    
    if extensions["dependency"]:
        field["dependsOn"] = extensions["dependency"]
    
    if extensions["date_format"]:
        field["dateFormat"] = extensions["date_format"]
    
    if extensions["generation_rule"]:
        field["generationRule"] = extensions["generation_rule"]
    
    if extensions.get("max_generation"):
        field["maxGeneration"] = extensions["max_generation"]
    
    if url:
        field["link"] = url
    
    if helper_text:
        field["helperText"] = helper_text

    if extensions.get("requires_grayscale"):
        field["requiresGrayscale"] = True
        field["grayscaleIntensity"] = extensions.get("grayscale_intensity", 100)
    
    return field


# ============================================================================
# ID-ONLY FIELD PARSER
# ============================================================================

def parse_field_from_id(element_id: str, text_content: str = "") -> Optional[Dict[str, Any]]:
    """
    Parse a field definition directly from an SVG element ID string.

    This does not require an ET.Element — all field metadata (type, generationRule,
    max, dependsOn, etc.) is encoded in the ID itself.

    text_content: preserved from the existing form_field's defaultValue so the
    user's text isn't lost when only the ID metadata changes.

    Returns a field dict on success, or None if the ID doesn't produce a valid field.
    """
    if not element_id:
        return None

    # Select option IDs need multi-element context — skip them here
    if any(p.startswith("select_") for p in element_id.split(".")):
        return None

    # Known explicit field types (mapped by parse_field_extensions via extension parts)
    KNOWN_FIELD_TYPES = {
        "text", "textarea", "select", "checkbox", "date", "upload",
        "file", "sign", "gen", "status", "hide", "number", "range",
        "color", "email", "tel", "url", "password",
    }

    try:
        # Extract link URL before splitting (URLs contain dots)
        cleaned_id, url = extract_link_url(element_id)

        parts = cleaned_id.split(".")
        if not parts or not parts[0]:
            return None

        if not validate_track_position(parts):
            return None

        extensions = parse_field_extensions(parts)

        # Normalize: if field_type was not set by any extension it defaults to parts[0].
        # In that case, treat the field as plain text (mirrors the full element parser).
        if extensions["field_type"] not in KNOWN_FIELD_TYPES:
            extensions["field_type"] = "text"

        default_value = get_default_value(extensions["field_type"], text_content, parts)

        return create_regular_field(
            base_id=parts[0],
            element_id=element_id,
            extensions=extensions,
            default_value=default_value,
            url=url,
            helper_text=None,
        )
    except Exception as e:
        logger.warning(f"[parse_field_from_id] Failed for id='{element_id}': {e}")
        return None


# ============================================================================
# MAIN PARSER FUNCTION
# ============================================================================

    
def process_element_to_field(element: ET.Element, fields_list: List[Dict[str, Any]], select_options_map: Dict[str, List[Dict[str, Any]]]):
    """
    Process a single SVG element and either update existing fields or add new ones.
    """
    # Prioritize data-name (preserves original naming with quotes/dots/slashes)
    original_element_id = element.attrib.get("data-name") or element.attrib.get("id", "")
    if not original_element_id:
        return

    # Robust text extraction: Handle multiline text (tspans)
    text_parts = []
    if element.text is not None and element.text.strip():
        text_parts.append(element.text.strip())
        
    for child in element:
        if child.text is not None and child.text.strip():
            text_parts.append(child.text.strip())
        if child.tail is not None and child.tail.strip():
            text_parts.append(child.tail.strip())
    
    text_content = "\n".join(text_parts)
    
    # 1. Validate ID against DSL
    is_valid, error = validate_svg_id(original_element_id)
    if not is_valid:
        logger.warning(f"Skipping element '{original_element_id}': {error}")
        return

    # Extract link URL before splitting (URLs contain dots)
    element_id, url = extract_link_url(original_element_id)
    
    # Split ID into parts
    parts = element_id.split(".")
    base_id = parts[0]
    
    # ====================================================================
    # HANDLE SELECT FIELDS
    # ====================================================================
    if any(p.startswith("select_") for p in parts):
        option = create_select_option(original_element_id, element, parts, text_content)
        modifiers = extract_select_modifiers(parts)
        
        # Create select field if first option
        if base_id not in select_options_map:
            select_options_map[base_id] = []
            field = create_select_field(base_id, original_element_id, modifiers["editable"])
            fields_list.append(field)
        
        # Add option to map
        select_options_map[base_id].append(option)
        
        # Update the field with option and modifiers
        for field in fields_list:
            if field["id"] == base_id:
                field["options"] = select_options_map[base_id]
                update_select_field(field, option, is_element_visible(element), modifiers)
                break
        
        return
    
    # ====================================================================
    # HANDLE REGULAR FIELDS
    # ====================================================================
    
    # Validate track_ position
    if not validate_track_position(parts):
        logger.warning(f"Skipping element {element_id}: track_ extension must be last")
        return
    
    # Parse all extensions
    extensions = parse_field_extensions(parts)

    if extensions.get("requires_grayscale") and extensions["field_type"] not in {"upload", "file"}:
        logger.warning(
            "Grayscale extension on non-upload field '%s' (element ID: %s)",
            base_id,
            original_element_id,
        )
    
    # Get default value
    default_value = get_default_value(extensions["field_type"], text_content, parts)
    
    # Extract helper text from data-helper attribute
    helper_text = element.attrib.get("data-helper", "")
    
    # Create field
    field = create_regular_field(base_id, original_element_id, extensions, default_value, url, helper_text)
    fields_list.append(field)



def parse_svg_to_form_fields(svg_text: str) -> List[Dict[str, Any]]:
    """
    Parse SVG text and convert elements with IDs into form field definitions.
    Elements with the same base_id are merged into a single field.
    """
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as e:
        logger.error(f"Failed to parse SVG: {e}")
        return []
    
    # Robust element discovery: Iterate through all nodes and manually check for ID/data-name attributes.
    # This is namespace-agnostic and works across different versions of xml.etree.
    elements = []
    for el in root.iter():
        if "id" in el.attrib or "data-name" in el.attrib:
            elements.append(el)
    
    # De-duplicate elements (some might have both)
    elements = list({id(el): el for el in elements}.values())
    
    fields_map: Dict[str, Dict[str, Any]] = {}
    select_options_map: Dict[str, List[Dict[str, Any]]] = {}
    
    for element in elements:
        # Temporary list to catch the new field from this element
        temp_list = []
        process_element_to_field(element, temp_list, select_options_map)
        
        if not temp_list:
            continue
            
        new_field = temp_list[0]
        base_id = new_field["id"]
        
        if base_id not in fields_map:
            fields_map[base_id] = new_field
        else:
            existing_field = fields_map[base_id]
            # Merge logic:
            # 1. Select type takes precedence
            if new_field["type"] == "select":
                # Transfer options and modifiers if moving from regular to select
                new_field["currentValue"] = existing_field.get("currentValue") or new_field.get("currentValue")
                new_field["touched"] = existing_field.get("touched") or new_field.get("touched")
                fields_map[base_id] = new_field
            elif existing_field["type"] == "select":
                # Keep select but maybe update current/default value if this new element is visible
                # update_select_field already handles some of this via select_options_map indirectly
                pass
            
            # Additional merging (editable, trackingRole, etc.)
            if new_field.get("editable"):
                existing_field["editable"] = True
            if new_field.get("trackingRole"):
                existing_field["trackingRole"] = new_field["trackingRole"]
    
    return list(fields_map.values())

