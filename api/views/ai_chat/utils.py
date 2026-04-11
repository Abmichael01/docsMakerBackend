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

def _build_tools(fields: list, valid_field_ids: list, has_image: bool, is_editor_mode: bool = False) -> list:
    """Construct the full OpenAI tools list for the current context."""
    tools = []

    # ── Single field update ───────────────────────────────────────────────────
    if is_editor_mode and valid_field_ids:
        tools.append({
            "type": "function",
            "function": {
                "name": "update_field",
                "description": (
                    "Update a single document field value. "
                    "Use this for direct user requests like 'Change X to Y' or 'Set field Z'. "
                    "Execute immediately if the value is clear."
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
                    "Update multiple document fields simultaneously. "
                    "Use this to apply comprehensive data sets (e.g. from an address or CV) "
                    "directly to the document."
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
        
        # ── Suggest field update ────────────────────────────────────────────────
        tools.append({
            "type": "function",
            "function": {
                "name": "suggest_field_updates",
                "description": (
                    "Propose document field updates to the user for approval. "
                    "Use for: complex logical changes, professional text rewrites, "
                    "or when the value is a 'best guess' that needs verification."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "rationale": {
                            "type": "string",
                            "description": "A short, user-friendly explanation of why these updates are recommended."
                        },
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
                    "required": ["rationale", "updates"],
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
                "MANDATORY: You must present the results to the user and never guess category names. "
                "Set load_best_match=true only if the user explicitly wants to switch to a DIFFERENT template. "
                "NEVER use this if the user is already in Editor Mode for a matching template."
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

    # ── Specialized document analysis ──────────────────────────────────────────
    if is_editor_mode:
        tools.append({
            "type": "function",
            "function": {
                "name": "analyze_document",
                "description": (
                    "Call this when the user asks for a review, check, or says 'looks good?'. "
                    "Also call proactively if you detect potential math or locale issues. "
                    "It verifies math, locale consistency, and professional quality."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        })

        # ── Locale defaults ───────────────────────────────────────────────────────
        tools.append({
            "type": "function",
            "function": {
                "name": "get_locale_defaults",
                "description": "Get industry-standard defaults for VAT, date format, and currency for a specific country.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "country": {
                            "type": "string", 
                            "description": "Country name (e.g. 'Nigeria', 'USA', 'UK')."
                        }
                    },
                    "required": ["country"],
                },
            },
        })

    # ── Get template details ──────────────────────────────────────────────────
    tools.append({
        "type": "function",
        "function": {
            "name": "get_template_details",
            "description": (
                "Fetch the exact list of required info (fields) for a specific template. "
                "Call this whenever the user asks 'What do I need?' or 'What info is required?' "
                "for a document. NEVER guess fields."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "template_id": {"type": "string", "description": "The UUID of the template."},
                },
                "required": ["template_id"],
            },
        },
    })

    # ── Load template ─────────────────────────────────────────────────────────
    tools.append({
        "type": "function",
        "function": {
            "name": "load_template",
            "description": (
                "Load a specific template by ID into the inline editor. "
                "MANDATORY: Never call this for the template you are currently editing in Editor Mode."
            ),
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
    if is_editor_mode:
        tools.append({
            "type": "function",
            "function": {
                "name": "purchase_template",
                "description": (
                    "Purchase a template the user has finished editing. "
                    "Use the 'Active Template ID' from the system prompt metadata. "
                    "Deducts price from wallet and enables download."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "template_id": {
                            "type": "string",
                            "description": "The UUID of the template to purchase (from Metadata)."
                        },
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
                "description": (
                    "Download a PURCHASED document as PDF or PNG. "
                    "ONLY call this if 'Purchased Document ID' exists in Metadata. "
                    "If not purchased yet, you MUST call purchase_template first."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "purchased_template_id": {
                            "type": "string",
                            "description": "The UUID of the purchased document (from Metadata)."
                        },
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
