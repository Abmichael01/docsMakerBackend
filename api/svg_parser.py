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

        # Check for link in parts instead of directly in el_id
        link_part = next((p for p in parts if p.startswith("link_")), None)
        if link_part:
            url = link_part[5:]  # 5 is length of "link_"

        # Handle select options
        select_part = next((p for p in parts if p.startswith("select_")), None)
        if select_part:
            # Preserve original case in the label by replacing underscores with spaces
            label = select_part[len("select_"):].replace("_", " ")
            # Get the actual text content from the SVG element for the value
            # This preserves the original case in the select options
            option_text = (el.text or "").strip()
            
            option = {
                "value": el_id,
                "label": label,
                "svgElementId": el_id,
                "displayText": option_text or label  # Use element text if available, otherwise use label
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
        tracking_role = None  # Initialize tracking role
        
        # Check if track_ extension is present and validate it's the last extension
        track_part_index = None
        for i, part in enumerate(parts[1:], 1):
            if part.startswith("track_"):
                track_part_index = i
                break
        
        # If track_ extension exists, it must be the last extension
        if track_part_index is not None and track_part_index != len(parts) - 1:
            # Skip processing this element if track_ is not the last extension
            continue
        
        for part in parts[1:]:
            if part.startswith("max_"):
                try:
                    max_value = int(part.replace("max_", ""))
                except ValueError:
                    pass
            elif part.startswith("depends_"):
                dependency = part.replace("depends_", "")
            elif part == "tracking_id":
                field_type = "gen"  # Tracking IDs are typically generated
                # We'll mark this field as a tracking ID later
            elif part.startswith("track_"):
                # Extract the tracking role (e.g., "name" from "track_name")
                # Only process if this is the last extension
                if parts.index(part) == len(parts) - 1:
                    tracking_role = part[6:]  # 6 is length of "track_"
            elif part.startswith("hide") or part in [
                "text", "textarea", "checkbox", "date", "upload",
                "number", "email", "tel", "gen", "password",
                "range", "color", "file", "status", "sign"
            ]:
                field_type = "hide" if part.startswith("hide") else part

        # Handle default values for different field types
        if field_type == "checkbox":
            default_value = False
        elif field_type == "hide":
            # For hide fields, determine default state based on part name
            # hide_checked = visible by default, hide_unchecked = hidden by default
            hide_part = next((p for p in parts if p.startswith("hide")), "hide")
            
            # Default is false (hidden) unless explicitly marked as checked
            default_value = hide_part == "hide_checked"  # True if checked (visible)
        else:
            default_value = text_content

        field = {
            "id": base_id,
            "name": name,
            "type": field_type,
            "svgElementId": el_id,
            "defaultValue": default_value,
            "currentValue": default_value,
            "isTrackingId": "tracking_id" in parts,
        }
        
        # Add tracking role if present
        if tracking_role:
            field["trackingRole"] = tracking_role

        if max_value is not None:
            field["max"] = max_value
        if dependency:
            field["dependsOn"] = dependency
        if url:
            field["link"] = url

        fields_list.append(field)
    
    return fields_list
