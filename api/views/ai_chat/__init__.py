import json
from django.conf import settings
from django.http import StreamingHttpResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from asgiref.sync import sync_to_async
from openai import AsyncOpenAI, BadRequestError

from ...models import Template, PurchasedTemplate
from ...prompts.ai_chat_system import build_system_prompt
from .utils import _is_writable, _build_tools, _format_messages
from .executor import execute_tool

@method_decorator(csrf_exempt, name="dispatch")
class AiChatView(View):
    async def post(self, request):
        def _get_initial_data():
            user = request.user
            if not user or not user.is_authenticated:
                from accounts.authentication import JWTAuthenticationFromCookies
                try:
                    result = JWTAuthenticationFromCookies().authenticate(request)
                    if result: user = result[0]
                except Exception: pass

            if not user or not user.is_authenticated:
                return None, None, None, None

            try:
                body = json.loads(request.body)
            except Exception:
                body = {}

            template_id = body.get("template_id")
            purchased_template_id = body.get("purchased_template_id")
            fields = []
            tool_price = None

            if template_id:
                try:
                    template = Template.objects.select_related("tool").get(pk=template_id)
                    fields = list(template.form_fields or [])
                    if template.tool: tool_price = template.tool.price
                except Template.DoesNotExist: pass
            elif purchased_template_id:
                try:
                    pt = PurchasedTemplate.objects.select_related("template__tool").get(
                        pk=purchased_template_id, buyer=user
                    )
                    fields = list(pt.form_fields or [])
                    if pt.template and pt.template.tool: tool_price = pt.template.tool.price
                except PurchasedTemplate.DoesNotExist: pass

            return fields, tool_price, body, user

        fields, tool_price, body, user = await sync_to_async(_get_initial_data)()
        if fields is None:
            return StreamingHttpResponse(
                iter([f"data: {json.dumps({'type': 'error', 'message': 'Unauthorized'})}\n\n"]),
                status=401, content_type="text/event-stream"
            )

        # Get all templates for catalog (cache-friendly if possible)
        def _get_catalog_summary():
            active_templates = Template.objects.filter(is_active=True).select_related("tool")
            # If too many templates, we might need to limit or just take the most relevant
            # But for dozens, listing name + tool + keywords is fine.
            lines = []
            for t in active_templates:
                tool_name = t.tool.name if t.tool else "Platform"
                kw = ", ".join(t.keywords[:5]) if t.keywords else ""
                lines.append(f'- "{t.name}" (ID: {t.id}) Tool: {tool_name} Tags: {kw}')
            return "\n".join(lines)

        catalog_str = await sync_to_async(_get_catalog_summary)()

        messages = body.get("messages", [])
        current_values = body.get("current_values", {})
        if current_values:
            for field in fields:
                fid = field.get("id")
                if fid and fid in current_values:
                    field["currentValue"] = current_values[fid]

        image_base64 = body.get("image_base64")
        if not image_base64:
            for msg in reversed(messages):
                if msg.get("attachmentUrl"):
                    image_base64 = msg["attachmentUrl"]
                    break

        valid_field_ids = [f["id"] for f in fields if f.get("id") and _is_writable(f)]
        has_image = bool(image_base64 or any(m.get("attachmentUrl") for m in messages))

        system_prompt = build_system_prompt(fields, tool_price=tool_price, catalog=catalog_str)
        tools = _build_tools(fields, valid_field_ids, has_image)
        formatted_messages = _format_messages(messages, image_base64, fields)
        client = AsyncOpenAI(api_key=settings.AI_API_KEY, base_url=settings.AI_BASE_URL)

        def _resolve_image(field_id: str) -> str | None:
            val = current_values.get(field_id, "")
            if val and str(val).startswith("data:image"): return val
            return image_base64

        async def stream_generator():
            tool_accumulator: dict[int, dict] = {}
            text_buffer: list[str] = []
            try:
                try:
                    stream = await client.chat.completions.create(
                        model=settings.AI_MODEL,
                        messages=[{"role": "system", "content": system_prompt}, *formatted_messages],
                        tools=tools or None,
                        stream=True, temperature=0.4,
                    )
                except BadRequestError as exc:
                    if "context_length_exceeded" in str(exc).lower() or "400" in str(exc):
                        yield f"data: {json.dumps({'type': 'text', 'delta': '*(trimmed history)* '})}\n\n"
                        stream = await client.chat.completions.create(
                            model=settings.AI_MODEL,
                            messages=[{"role": "system", "content": system_prompt}, formatted_messages[-1]],
                            tools=tools or None, stream=True, temperature=0.4,
                        )
                    else: raise

                async for chunk in stream:
                    if not chunk.choices: continue
                    delta = chunk.choices[0].delta
                    if delta.content: text_buffer.append(delta.content)
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in tool_accumulator:
                                tool_accumulator[idx] = {"id": "", "name": "", "arguments": ""}
                            if tc.id: tool_accumulator[idx]["id"] = tc.id
                            if tc.function:
                                if tc.function.name: tool_accumulator[idx]["name"] = tc.function.name
                                if tc.function.arguments: tool_accumulator[idx]["arguments"] += tc.function.arguments

                if not tool_accumulator:
                    for t in text_buffer:
                        yield f"data: {json.dumps({'type': 'text', 'delta': t})}\n\n"

                if tool_accumulator:
                    tool_messages: list[dict] = [
                        {"role": "system", "content": system_prompt},
                        *formatted_messages,
                        {
                            "role": "assistant", "content": None,
                            "tool_calls": [
                                {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                                for tc in tool_accumulator.values()
                            ],
                        },
                    ]

                    for tc_data in tool_accumulator.values():
                        name = tc_data["name"]
                        try: args = json.loads(tc_data["arguments"])
                        except Exception: args = {}

                        result_content = await execute_tool(
                            name, args, tc_data["id"], valid_field_ids, 
                            user, _resolve_image, current_values,
                        )
                        for event in result_content["events"]:
                            yield f"data: {json.dumps(event)}\n\n"

                        tool_messages.append({
                            "role": "tool", "tool_call_id": tc_data["id"],
                            "name": name, "content": result_content["text"],
                        })

                    second_stream = await client.chat.completions.create(
                        model=settings.AI_MODEL, messages=tool_messages,
                        stream=True, temperature=0.4,
                    )
                    async for chunk2 in second_stream:
                        if chunk2.choices and chunk2.choices[0].delta.content:
                            yield f"data: {json.dumps({'type': 'text', 'delta': chunk2.choices[0].delta.content})}\n\n"

                yield f"data: {json.dumps({'type': 'done'})}\n\n"
            except Exception as exc:
                import traceback
                traceback.print_exc()
                yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"

        response = StreamingHttpResponse(stream_generator(), content_type="text/event-stream")
        for k, v in [("Cache-Control", "no-cache, no-transform"), ("X-Accel-Buffering", "no"), ("Connection", "keep-alive"), ("X-Content-Type-Options", "nosniff"), ("Content-Encoding", "identity")]:
            response[k] = v
        return response
