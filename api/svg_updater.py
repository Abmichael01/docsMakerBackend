import re
import hashlib
import json
from typing import Any, Dict, List, Tuple

from lxml import etree
from django.core.cache import cache


def _extract_from_dependency(depends_on: str, field_values: Dict[str, Any]) -> str:
    """
    Mirror frontend dependency extraction logic.
    Supports:
      - field_name
      - field_name[w1], field_name[w2]
      - field_name[ch1], field_name[ch1,2,5], field_name[ch1-4]
    """
    match = re.match(r"^(.+)\[(w|ch)(.+)\]$", depends_on)
    if match:
        field_name = match.group(1)
        extract_type = match.group(2)
        extract_pattern = match.group(3)
        field_value = field_values.get(field_name, "")
        if isinstance(field_value, str) and (
            field_value.startswith("data:image/") or field_value.startswith("blob:")
        ):
            return field_value
        string_value = str(field_value or "")
        if extract_type == "w":
            return _extract_word(string_value, extract_pattern)
        if extract_type == "ch":
            return _extract_chars(string_value, extract_pattern)
    field_value = field_values.get(depends_on, "")
    if isinstance(field_value, str) and (
        field_value.startswith("data:image/") or field_value.startswith("blob:")
    ):
        return field_value
    return str(field_value or "")


def _extract_word(text: str, pattern: str) -> str:
    words = text.strip().split()
    try:
        index = int(pattern) - 1
    except ValueError:
        return ""
    return words[index] if 0 <= index < len(words) else ""


def _extract_chars(text: str, pattern: str) -> str:
    if "," in pattern:
        indices = []
        for part in pattern.split(","):
            try:
                indices.append(int(part.strip()) - 1)
            except ValueError:
                continue
        return "".join(text[i] for i in indices if 0 <= i < len(text))
    if "-" in pattern:
        try:
            start, end = [int(x.strip()) for x in pattern.split("-")]
        except ValueError:
            return ""
        return text[start - 1 : end]
    try:
        index = int(pattern) - 1
    except ValueError:
        return ""
    return text[index] if 0 <= index < len(text) else ""


def _bool_from_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    value_str = str(value).strip().lower()
    return value_str in {"true", "1", "yes", "y"}


def update_svg_from_field_updates(
    svg_content: str, form_fields: List[Dict[str, Any]], field_updates: List[Dict[str, Any]]
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Apply field updates to SVG content by mirroring frontend updateSvgFromFormData logic.
    Uses caching to avoid reprocessing the same SVG with the same field updates.

    Returns tuple of (updated_svg, updated_field_values)
    """
    if not svg_content or not form_fields:
        return svg_content, form_fields

    # Create cache key from SVG hash and field updates
    # This allows us to cache processed results for identical inputs
    svg_hash = hashlib.md5(svg_content.encode('utf-8')).hexdigest()
    field_updates_str = json.dumps(field_updates or [], sort_keys=True)
    cache_key = f"svg_update_{svg_hash}_{hashlib.md5(field_updates_str.encode('utf-8')).hexdigest()}"
    
    # Try to get from cache (cache for 1 hour)
    cached_result = cache.get(cache_key)
    if cached_result:
        return cached_result[0], cached_result[1]

    # Use lxml for much faster parsing of large SVGs (10-100x faster than BeautifulSoup)
    try:
        # Parse SVG with lxml (much faster for large files)
        parser = etree.XMLParser(recover=True, huge_tree=True)
        root = etree.fromstring(svg_content.encode('utf-8'), parser=parser)
    except Exception:
        # Fallback to original content if parsing fails
        return svg_content, form_fields

    # Build namespace map for xlink
    nsmap = {'xlink': 'http://www.w3.org/1999/xlink'}
    
    field_map = {field.get("id"): field for field in form_fields}
    field_values: Dict[str, Any] = {}

    # Initialize with current or default values
    for field in form_fields:
        field_values[field.get("id")] = field.get("currentValue") or field.get("defaultValue") or ""

    # Apply incoming updates
    for update in field_updates or []:
        field_id = update.get("id")
        if field_id in field_map:
            field_values[field_id] = update.get("value", "")

    # Apply dependency extraction pass
    computed_values: Dict[str, Any] = {}
    for field in form_fields:
        field_id = field.get("id")
        depends_on = field.get("dependsOn")
        if depends_on:
            computed_values[field_id] = _extract_from_dependency(depends_on, field_values)
        else:
            computed_values[field_id] = field_values.get(field_id, "")

    # Build a lookup map for faster element finding (O(1) instead of O(n))
    element_map = {}
    for elem in root.iter():
        elem_id = elem.get("id")
        if elem_id:
            element_map[elem_id] = elem

    # Update SVG elements based on computed values
    for field in form_fields:
        field_id = field.get("id")
        value = computed_values.get(field_id, "")

        # Select fields
        options = field.get("options")
        if options:
            for option in options:
                svg_element_id = option.get("svgElementId")
                if not svg_element_id:
                    continue
                el = element_map.get(svg_element_id)
                if not el:
                    continue
                option_value = str(option.get("value"))
                if option_value == str(value):
                    el.attrib.pop("display", None)
                    el.set("opacity", "1")
                    el.set("visibility", "visible")
                else:
                    el.set("opacity", "0")
                    el.set("visibility", "hidden")
                    el.set("display", "none")
            continue

        svg_element_id = field.get("svgElementId")
        if not svg_element_id:
            continue
        el = element_map.get(svg_element_id)
        if not el:
            continue

        field_type = (field.get("type") or "text").lower()

        if field_type in {"upload", "file", "sign"}:
            if value and isinstance(value, str) and value.strip():
                el.set("{http://www.w3.org/1999/xlink}href", value)
        elif field_type == "hide":
            visible = _bool_from_value(value)
            if visible:
                el.set("opacity", "1")
                el.set("visibility", "visible")
                el.attrib.pop("display", None)
            else:
                el.set("opacity", "0")
                el.set("visibility", "hidden")
                el.set("display", "none")
        else:
            string_value = "" if value is None else str(value)
            # For lxml, set text content (this replaces existing text)
            # Remove all children first to ensure clean text replacement
            for child in list(el):
                el.remove(child)
            el.text = string_value

    # Update stored values to reflect latest state
    for field in form_fields:
        field_id = field.get("id")
        if field_id in computed_values:
            field["currentValue"] = computed_values[field_id]

    # Convert back to string (lxml is faster at serialization too)
    result = (etree.tostring(root, encoding='unicode', pretty_print=False), form_fields)
    
    # Cache the result for 1 hour (3600 seconds)
    # Only cache if SVG is reasonably sized (< 5MB) to avoid memory issues
    if len(svg_content) < 5 * 1024 * 1024:  # 5MB limit
        cache.set(cache_key, result, 3600)
    
    return result

