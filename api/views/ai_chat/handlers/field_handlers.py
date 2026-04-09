async def handle_update_field(args, valid_field_ids):
    events = []
    field_id = args.get("field_id", "")
    value = args.get("value", "")
    if field_id in valid_field_ids:
        events.append({"type": "field_update", "id": field_id, "value": value})
        return {"events": events, "text": f"Field updated: {field_id} = {value[:80]}"}
    return {"events": events, "text": f"Field '{field_id}' not found or not writable."}

async def handle_batch_update_fields(args, valid_field_ids):
    events = []
    updates = args.get("updates", [])
    applied = []
    skipped = []
    for upd in updates:
        fid = upd.get("field_id", "")
        val = upd.get("value", "")
        if fid in valid_field_ids:
            events.append({"type": "field_update", "id": fid, "value": val})
            applied.append(fid)
        else:
            skipped.append(fid)
    summary = f"Batch updated {len(applied)} field(s)."
    if skipped:
        summary += f" Skipped (not writable): {', '.join(skipped)}."
    return {"events": events, "text": summary}
