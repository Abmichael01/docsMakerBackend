import xml.etree.ElementTree as ET


def parse_svg_to_form_fields(svg_text: str) -> list[dict]:
    root = ET.fromstring(svg_text)
    elements = root.findall(".//*[@id]")

    fields_map: dict[str, dict] = {}
    select_options_map: dict[str, list[dict]] = {}

    for el in elements:
        el_id = el.attrib.get("id", "")
        text_content = (el.text or "").strip()

        parts = el_id.split(".")
        base_id = parts[0]
        name = base_id.replace("_", " ").title()
        field_type = base_id  # default fallback
        max_value = None
        dependency = None

        # Handle select options
        if any(p.startswith("select_") for p in parts):
            option = {
                "value": el_id,
                "label": el_id.replace("_", " "),
                "svgElementId": el_id,
            }
            if base_id not in select_options_map:
                select_options_map[base_id] = []
            select_options_map[base_id].append(option)
            continue

        for part in parts[1:]:
            if part.startswith("max_"):
                try:
                    max_value = int(part.replace("max_", ""))
                except ValueError:
                    pass
            elif part.startswith("depends_"):
                dependency = part.replace("depends_", "")
            elif part in [
                "text", "textarea", "checkbox", "date", "upload",
                "number", "email", "tel", "gen", "password",
                "range", "color", "file", "status"
            ]:
                field_type = part

        default_value = False if field_type == "checkbox" else text_content

        fields_map[base_id] = {
            "id": base_id,
            "name": name,
            "type": field_type,
            "svgElementId": el_id,
            "defaultValue": default_value,
            "currentValue": default_value,
        }

        if max_value is not None:
            fields_map[base_id]["max"] = max_value
        if dependency:
            fields_map[base_id]["dependsOn"] = dependency

    # Merge select options into fields
    for field_id, options in select_options_map.items():
        fields_map[field_id] = {
            "id": field_id,
            "name": field_id.replace("_", " ").title(),
            "type": "text",  # Can be overridden in frontend
            "options": options,
            "defaultValue": options[0]["value"] if options else "",
            "currentValue": options[0]["value"] if options else "",
        }

    return list(fields_map.values())

    