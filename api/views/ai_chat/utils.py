from ...models import Template, PurchasedTemplate
from ...prompts.ai_chat_system import build_system_prompt

# Maximum conversation turns sent to the model (controls token cost)
MAX_MESSAGES = 14

# Fields that should never be written by the AI
_READONLY_TYPE = {"gen", "status"}

def _is_writable(field: dict) -> bool:
    """Return True if the AI is allowed to update this field."""
    if field.get("type") in _READONLY_TYPE:
        return False
    fid = str(field.get("id", ""))
    if ".depends" in fid:
        return False
    if field.get("dependsOn"):
        return False
    return True

def _build_tools(fields: list, valid_field_ids: list, has_image: bool) -> list:
    """Construct the full OpenAI tools list for the current context."""
    tools = []

    # ── Single field update ───────────────────────────────────────────────────
    if valid_field_ids:
        tools.append({
            "type": "function",
            "function": {
                "name": "update_field",
                "description": (
                    "Update a single document field value. "
                    "Use batch_update_fields when changing 2 or more fields."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "field_id": {"type": "string", "enum": valid_field_ids},
                        "value": {"type": "string"},
                    },
                    "required": ["field_id", "value"],
                },
            },
        })

        # ── Batch field update ────────────────────────────────────────────────
        tools.append({
            "type": "function",
            "function": {
                "name": "batch_update_fields",
                "description": (
                    "Update multiple document fields in a single operation. "
                    "ALWAYS prefer this over multiple update_field calls. "
                    "Use for: magic fill, data extraction, consistency fixes, or any 2+ field update."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "updates": {
                            "type": "array",
                            "description": "Array of {field_id, value} objects.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "field_id": {"type": "string", "enum": valid_field_ids},
                                    "value": {"type": "string"},
                                },
                                "required": ["field_id", "value"],
                            },
                            "minItems": 1,
                        }
                    },
                    "required": ["updates"],
                },
            },
        })

    # ── Web search ────────────────────────────────────────────────────────────
    tools.append({
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "Search the web for real-world data needed to fill document fields: "
                "company addresses, registration numbers, VAT numbers, postal codes, "
                "country codes, industry-standard rates, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    })

    # ── Template search ───────────────────────────────────────────────────────
    tools.append({
        "type": "function",
        "function": {
            "name": "search_tools",
            "description": (
                "Search SharpToolz for available document templates. "
                "ALWAYS call this before asking the user clarifying questions. "
                "Set load_best_match=true when user wants to use/open/edit a template."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Broad search terms (e.g. 'invoice billing receipt payment').",
                    },
                    "load_best_match": {
                        "type": "boolean",
                        "description": "If true, also load the best matching template into the editor.",
                    },
                },
                "required": ["query"],
            },
        },
    })

    # ── Clarifying options UI ─────────────────────────────────────────────────
    tools.append({
        "type": "function",
        "function": {
            "name": "suggest_options",
            "description": (
                "Show the user clickable option buttons to narrow down a choice. "
                "Only use AFTER searching — options must come from actual search results."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "options": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string"},
                                "value": {"type": "string"},
                                "template_id": {"type": "string"},
                                "style": {"type": "string"},
                            },
                            "required": ["label", "value"],
                        },
                        "minItems": 2,
                        "maxItems": 6,
                    },
                },
                "required": ["question", "options"],
            },
        },
    })

    # ── Load template ─────────────────────────────────────────────────────────
    tools.append({
        "type": "function",
        "function": {
            "name": "load_template",
            "description": "Load a specific template by ID into the inline editor.",
            "parameters": {
                "type": "object",
                "properties": {
                    "template_id": {"type": "string"},
                },
                "required": ["template_id"],
            },
        },
    })

    # ── Purchase ──────────────────────────────────────────────────────────────
    tools.append({
        "type": "function",
        "function": {
            "name": "purchase_template",
            "description": (
                "Purchase a template the user has finished editing. "
                "Deducts price from wallet and enables download. "
                "Call after user confirms they want to finalize/download."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "template_id": {"type": "string"},
                    "form_fields": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "currentValue": {"type": "string"},
                            },
                            "required": ["id", "currentValue"],
                        },
                    },
                },
                "required": ["template_id", "form_fields"],
            },
        },
    })

    # ── Download ──────────────────────────────────────────────────────────────
    tools.append({
        "type": "function",
        "function": {
            "name": "download_document",
            "description": "Download a purchased document as PDF or PNG.",
            "parameters": {
                "type": "object",
                "properties": {
                    "purchased_template_id": {"type": "string"},
                    "output_type": {"type": "string", "enum": ["pdf", "png"]},
                },
                "required": ["purchased_template_id", "output_type"],
            },
        },
    })

    # ── Save edits ────────────────────────────────────────────────────────────
    tools.append({
        "type": "function",
        "function": {
            "name": "save_edits",
            "description": "Save field edits to a purchased template so changes persist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "purchased_template_id": {"type": "string"},
                    "form_fields": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "currentValue": {"type": "string"},
                            },
                            "required": ["id", "currentValue"],
                        },
                    },
                },
                "required": ["purchased_template_id", "form_fields"],
            },
        },
    })

    # ── Image tools (only when an image is present) ───────────────────────────
    if has_image and valid_field_ids:
        tools.append({
            "type": "function",
            "function": {
                "name": "crop_image",
                "description": (
                    "Crop an image field to a professional framing. "
                    "Use normalized 0–1000 coordinates. "
                    "For passport/ID: tight head-and-shoulders, cx≈500, cy≈300, width≈400, height≈500."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "field_id": {"type": "string", "enum": valid_field_ids},
                        "cx": {"type": "integer", "description": "Center X (0–1000)"},
                        "cy": {"type": "integer", "description": "Center Y (0–1000)"},
                        "width": {"type": "integer", "description": "Crop width (0–1000)"},
                        "height": {"type": "integer", "description": "Crop height (0–1000)"},
                    },
                    "required": ["field_id", "cx", "cy", "width", "height"],
                },
            },
        })
        tools.append({
            "type": "function",
            "function": {
                "name": "remove_bg",
                "description": (
                    "Remove the background from an image field. "
                    "Call BEFORE crop_image when a non-transparent background is detected."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "field_id": {"type": "string", "enum": valid_field_ids},
                    },
                    "required": ["field_id"],
                },
            },
        })
    
    # ── Signature tool ────────────────────────────────────────────────────────
    if valid_field_ids:
        # Check if any field is of type 'sign'
        has_sign_field = any(f.get("type") == "sign" for f in fields)
        if has_sign_field:
            tools.append({
                "type": "function",
                "function": {
                    "name": "write_signature",
                    "description": (
                        "Generate and insert a signature image into a 'sign' field. "
                        "Can generate a custom signature if a name is provided, "
                        "or use one of 9 preset styles."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "field_id": {"type": "string", "enum": valid_field_ids},
                            "full_name": {
                                "type": "string", 
                                "description": "The name to draw for a dynamic signature (e.g. 'John Doe')."
                            },
                            "style_index": {
                                "type": "integer", 
                                "minimum": 1, 
                                "maximum": 9,
                                "description": "An index from 1-9 to choose a preset signature style."
                            },
                        },
                        "required": ["field_id"],
                    },
                },
            })

    return tools

def _format_messages(msgs, image_base64, fields):
    """Format conversation history for LLM consumption."""
    formatted = []
    recent = msgs[-MAX_MESSAGES:]
    for i, msg in enumerate(recent):
        is_last = i == len(recent) - 1
        role = msg.get("role", "user")
        content = msg.get("content", "")
        attachment = msg.get("attachmentUrl")

        if is_last and role == "user" and image_base64:
            user_parts = [
                {"type": "text", "text": content + "\n\n(System: use detail:high for the image)"},
                {"type": "image_url", "image_url": {"url": image_base64, "detail": "high"}},
            ]
            # Inject golden reference images from existing fields
            refs_added = 0
            priority_fields = sorted(
                fields,
                key=lambda f: any(
                    kw in f.get("name", "").lower()
                    for kw in ["passport", "photo", "profile", "id"]
                ),
                reverse=True,
            )
            for field in priority_fields:
                if refs_added >= 2:
                    break
                if field.get("type") == "upload" and field.get("currentValue"):
                    val = field["currentValue"]
                    if str(val).startswith("data:image"):
                        user_parts.append({
                            "type": "text",
                            "text": f"Golden Reference — match this framing for {field.get('name')}:",
                        })
                        user_parts.append({
                            "type": "image_url",
                            "image_url": {"url": val, "detail": "low"},
                        })
                        refs_added += 1
            formatted.append({"role": "user", "content": user_parts})

        elif attachment and str(attachment).startswith("data:image"):
            # Older messages: strip base64, keep a text note
            formatted.append({
                "role": role,
                "content": content + "\n[An image was attached to this message]",
            })
        else:
            formatted.append({"role": role, "content": content})
    return formatted
