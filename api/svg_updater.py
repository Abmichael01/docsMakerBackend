import re
from typing import Any, Dict, List, Tuple

from bs4 import BeautifulSoup


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

    Returns tuple of (updated_svg, updated_field_values)
    """
    if not svg_content or not form_fields:
        return svg_content, form_fields

    soup = BeautifulSoup(svg_content, "xml")
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
                el = soup.find(id=svg_element_id)
                if not el:
                    continue
                option_value = str(option.get("value"))
                if option_value == str(value):
                    el.attrs.pop("display", None)
                    el["opacity"] = "1"
                    el["visibility"] = "visible"
                else:
                    el["opacity"] = "0"
                    el["visibility"] = "hidden"
                    el["display"] = "none"
            continue

        svg_element_id = field.get("svgElementId")
        if not svg_element_id:
            continue
        el = soup.find(id=svg_element_id)
        if not el:
            continue

        field_type = (field.get("type") or "text").lower()

        if field_type in {"upload", "file", "sign"}:
            if value and isinstance(value, str) and value.strip():
                el["xlink:href"] = value
        elif field_type == "hide":
            visible = _bool_from_value(value)
            if visible:
                el["opacity"] = "1"
                el["visibility"] = "visible"
                el.attrs.pop("display", None)
            else:
                el["opacity"] = "0"
                el["visibility"] = "hidden"
                el["display"] = "none"
        else:
            string_value = "" if value is None else str(value)
            el.string = string_value

    # Update stored values to reflect latest state
    for field in form_fields:
        field_id = field.get("id")
        if field_id in computed_values:
            field["currentValue"] = computed_values[field_id]

    return str(soup), form_fields

