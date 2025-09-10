import xml.etree.ElementTree as ET


def parse_svg_to_form_fields(svg_text: str) -> list[dict]:
    root = ET.fromstring(svg_text)
    elements = root.findall(".//*[@id]")

    fields_list = []  # Use list to maintain order
    select_options_map = {}  # Track select options for each field

    for el in elements:
        el_id = el.attrib.get("id", "")
        text_content = (el.text or "").strip()

        parts = el_id.split(".")
        base_id = parts[0]
        name = base_id.replace("_", " ").title()
        field_type = base_id  # default fallback
        max_value = None
        dependency = None
        url = None

        # Check for link before processing parts
        if "link_" in el_id:
            link_start = el_id.find("link_")
            url = el_id[link_start + 5:]  # 5 is length of "link_"

        # Handle select options
        select_part = next((p for p in parts if p.startswith("select_")), None)
        if select_part:
            label = select_part[len("select_"):].replace("_", " ")
            option = {
                "value": el_id,
                "label": label,
                "svgElementId": el_id,
            }
            
            # If this is the first select option for this field, create the field
            if base_id not in select_options_map:
                select_options_map[base_id] = []
                # Create the select field in its original position
                field = {
                    "id": base_id,
                    "name": name,
                    "type": "select",
                    "svgElementId": el_id,  # Use the first select element's ID
                    "options": [],
                    "defaultValue": "",
                    "currentValue": "",
                }
                fields_list.append(field)
            
            select_options_map[base_id].append(option)
            # Update the field's options
            for field in fields_list:
                if field["id"] == base_id:
                    field["options"] = select_options_map[base_id]
                    if not field["defaultValue"] and select_options_map[base_id]:
                        field["defaultValue"] = select_options_map[base_id][0]["value"]
                        field["currentValue"] = select_options_map[base_id][0]["value"]
                    break
            continue

        # Process field type and other properties for non-select fields
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
                "range", "color", "file", "status", "sign"
            ]:
                field_type = part

        default_value = False if field_type == "checkbox" else text_content

        field = {
            "id": base_id,
            "name": name,
            "type": field_type,
            "svgElementId": el_id,
            "defaultValue": default_value,
            "currentValue": default_value,
        }

        if max_value is not None:
            field["max"] = max_value
        if dependency:
            field["dependsOn"] = dependency
        if url:
            field["link"] = url

        fields_list.append(field)

    return fields_list 
