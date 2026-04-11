import base64 as b64_mod
from io import BytesIO
from django.conf import settings
from asgiref.sync import sync_to_async


async def handle_crop_image(args, valid_field_ids, resolve_image):
    events = []
    fid = args.get("field_id", "")
    cx = args.get("cx", 500)
    cy = args.get("cy", 500)
    nw = args.get("width", 400)
    nh = args.get("height", 500)

    if fid not in valid_field_ids:
        return {"events": events, "text": f"Field '{fid}' not found."}

    events.append({"type": "status", "label": "Cropping image…"})
    src = resolve_image(fid)
    if not src:
        return {"events": events, "text": "No image available for cropping."}

    try:
        from PIL import Image

        encoded = src.split(",", 1)[1] if "," in src else src
        img = Image.open(BytesIO(b64_mod.b64decode(encoded)))
        img_w, img_h = img.size

        # Try face detection first; fall back to AI-supplied coords
        detected = None
        try:
            from ....utils.face_utils import get_face_landmarks
            detected = get_face_landmarks(img)
        except Exception:
            pass

        if detected:
            cx, cy, nw, nh = detected

        center_x = (cx / 1000) * img_w
        center_y = (cy / 1000) * img_h
        w = int((nw / 1000) * img_w)
        h = int((nh / 1000) * img_h)
        x = max(0, min(int(center_x - w / 2), img_w - 1))
        y = max(0, min(int(center_y - h / 2), img_h - 1))
        w = max(1, min(w, img_w - x))
        h = max(1, min(h, img_h - y))

        cropped = img.crop((x, y, x + w, y + h))
        buf = BytesIO()
        fmt = img.format or "PNG"
        cropped.save(buf, format=fmt)
        b64_result = f"data:image/{fmt.lower()};base64,{b64_mod.b64encode(buf.getvalue()).decode()}"
        events.append({"type": "field_update", "id": fid, "value": b64_result})
        return {"events": events, "text": f"Image cropped at center ({cx},{cy}), size {nw}×{nh}."}
    except Exception as exc:
        return {"events": events, "text": f"Crop failed: {exc}"}


async def handle_remove_bg(args, valid_field_ids, resolve_image):
    events = []
    fid = args.get("field_id", "")

    if fid not in valid_field_ids:
        return {"events": events, "text": f"Field '{fid}' not found."}

    events.append({"type": "status", "label": "Removing background…"})
    src = resolve_image(fid)
    if not src:
        return {"events": events, "text": "No image available for background removal."}

    try:
        import requests

        encoded = src.split(",", 1)[1] if "," in src else src

        def _do_remove():
            resp = requests.post(
                "https://api.remove.bg/v1.0/removebg",
                data={"image_file_b64": encoded, "size": "auto"},
                headers={"X-Api-Key": settings.REMOVEBG_API_KEY},
                timeout=30,
            )
            if resp.status_code == 200:
                return resp.content
            raise Exception(resp.text)

        result_bytes = await sync_to_async(_do_remove)()
        res_b64 = f"data:image/png;base64,{b64_mod.b64encode(result_bytes).decode()}"
        events.append({"type": "field_update", "id": fid, "value": res_b64})
        return {"events": events, "text": "Background removed successfully."}
    except Exception as exc:
        return {"events": events, "text": f"Background removal failed: {exc}"}
