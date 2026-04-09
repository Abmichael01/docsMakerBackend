from .handlers.field_handlers import handle_update_field, handle_batch_update_fields
from .handlers.search_handlers import handle_search_web, handle_search_tools
from .handlers.template_handlers import (
    handle_load_template, handle_purchase_template,
    handle_download_document, handle_save_edits
)
from .handlers.media_handlers import handle_crop_image, handle_remove_bg
from .handlers.ui_handlers import handle_suggest_options
from .handlers.signature_handlers import handle_write_signature

async def execute_tool(
    name: str,
    args: dict,
    tool_call_id: str,
    valid_field_ids: list,
    user,
    resolve_image,
    current_values: dict,
) -> dict:
    """Route tool calls to specific handlers."""
    if name == "update_field":
        return await handle_update_field(args, valid_field_ids)
    
    if name == "batch_update_fields":
        return await handle_batch_update_fields(args, valid_field_ids)
    
    if name == "search_web":
        return await handle_search_web(args)
    
    if name == "search_tools":
        return await handle_search_tools(args)
    
    if name == "suggest_options":
        return await handle_suggest_options(args)
    
    if name == "load_template":
        return await handle_load_template(args)
    
    if name == "purchase_template":
        return await handle_purchase_template(args, user)
    
    if name == "download_document":
        return await handle_download_document(args, user)
    
    if name == "save_edits":
        return await handle_save_edits(args, user)
    
    if name == "crop_image":
        return await handle_crop_image(args, valid_field_ids, resolve_image)
    
    if name == "remove_bg":
        return await handle_remove_bg(args, valid_field_ids, resolve_image)

    if name == "write_signature":
        return await handle_write_signature(args, valid_field_ids)

    return {"events": [], "text": f"Tool '{name}' not implemented."}
