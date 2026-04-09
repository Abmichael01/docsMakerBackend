from asgiref.sync import sync_to_async
from ....models import Template, PurchasedTemplate
from wallet.models import Wallet

async def handle_load_template(args):
    events = []
    template_id = args.get("template_id", "")
    try:
        def _load(tid):
            tpl = Template.objects.filter(pk=tid, is_active=True).select_related("tool").first()
            if not tpl: return None
            return {
                "id": str(tpl.id),
                "name": tpl.name,
                "toolName": tpl.tool.name if tpl.tool else "General",
                "price": str(tpl.tool.price) if tpl.tool else "0",
                "banner": tpl.banner.url if tpl.banner else "",
                "field_count": len(tpl.form_fields or []),
            }
        tpl_data = await sync_to_async(_load)(template_id)
        if tpl_data:
            events.append({"type": "template_loaded", "template": tpl_data})
            return {"events": events, "text": f"Loaded '{tpl_data['name']}' ({tpl_data['field_count']} fields)."}
        return {"events": events, "text": f"Template {template_id} not found."}
    except Exception as exc:
        return {"events": events, "text": f"Load failed: {exc}"}

async def handle_purchase_template(args, user):
    events = []
    template_id = args.get("template_id", "")
    form_fields = args.get("form_fields", [])
    try:
        def _purchase(tid, flds, u):
            tpl = Template.objects.select_related("tool").get(pk=tid)
            if not tpl.tool: return None, "No tool linked"
            wallet, _ = Wallet.objects.get_or_create(user=u)
            if wallet.balance < tpl.tool.price: return None, "Insufficient balance"
            wallet.balance -= tpl.tool.price
            wallet.save()
            pt = PurchasedTemplate.objects.create(
                buyer=u, template=tpl, form_fields=flds, price_paid=tpl.tool.price
            )
            return {
                "id": str(pt.id),
                "name": tpl.name,
                "price": str(tpl.tool.price),
                "new_balance": str(wallet.balance),
            }, None
        pt_data, error = await sync_to_async(_purchase)(template_id, form_fields, user)
        if error: return {"events": events, "text": f"Purchase failed: {error}"}
        events.append({"type": "purchased", "template": pt_data})
        return {"events": events, "text": f"Successfully purchased {pt_data['name']}!"}
    except Exception as exc:
        return {"events": events, "text": f"Purchase error: {exc}"}

async def handle_download_document(args, user):
    events = []
    pt_id = args.get("purchased_template_id", "")
    out_type = args.get("output_type", "pdf")
    try:
        def _get_pt(pid, u):
            return PurchasedTemplate.objects.filter(pk=pid, buyer=u).first()
        pt = await sync_to_async(_get_pt)(pt_id, user)
        if not pt: return {"events": events, "text": "Purchased document not found."}
        from ....utils.generation import generate_document_file
        file_url = await sync_to_async(generate_document_file)(pt, out_type)
        events.append({"type": "document_ready", "file": {"url": file_url, "type": out_type}})
        return {"events": events, "text": f"Your {out_type.upper()} is ready for download!"}
    except Exception as exc:
        return {"events": events, "text": f"Download failed: {exc}"}

async def handle_save_edits(args, user):
    events = []
    pt_id = args.get("purchased_template_id", "")
    form_fields = args.get("form_fields", [])
    try:
        def _save(pid, flds, u):
            pt = PurchasedTemplate.objects.filter(pk=pid, buyer=u).first()
            if not pt: return False
            pt.form_fields = flds
            pt.save()
            return True
        success = await sync_to_async(_save)(pt_id, form_fields, user)
        if success: return {"events": events, "text": "Edits saved successfully."}
        return {"events": events, "text": "Document not found."}
    except Exception as exc:
        return {"events": events, "text": f"Save failed: {exc}"}
