import json
import asyncio
from django.conf import settings
from django.http import StreamingHttpResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from asgiref.sync import sync_to_async
from openai import AsyncOpenAI, BadRequestError

from ...models import Template, PurchasedTemplate, AiChatSession, AiChatMessage
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

            session_id = body.get("session_id")
            template_id = body.get("template_id")
            purchased_template_id = body.get("purchased_template_id")
            
            # 1. Resolve or Create Session
            session = None
            if session_id:
                try:
                    session = AiChatSession.objects.get(id=session_id, user=user)
                except (AiChatSession.DoesNotExist, ValueError, TypeError):
                    pass
            
            if not session:
                # Intelligent Naming for Tool Mode
                title = "New Chat"
                template_obj = None
                purchased_template_obj = None
                
                if template_id:
                    try:
                        template_obj = Template.objects.get(pk=template_id)
                        count = AiChatSession.objects.filter(user=user, template=template_obj).count()
                        title = f"{template_obj.name} {count + 1}"
                    except Template.DoesNotExist: pass
                elif purchased_template_id:
                    try:
                        purchased_template_obj = PurchasedTemplate.objects.get(pk=purchased_template_id, buyer=user)
                        count = AiChatSession.objects.filter(user=user, purchased_template=purchased_template_obj).count()
                        title = f"Edit: {purchased_template_obj.name} {count + 1}"
                    except PurchasedTemplate.DoesNotExist: pass
                
                session = AiChatSession.objects.create(
                    user=user,
                    title=title,
                    template=template_obj,
                    purchased_template=purchased_template_obj
                )

            # 2. Extract Fields and metadata
            # Use template/purchased template from session if not in body
            template_id = template_id or (session.template_id if session.template else None)
            purchased_template_id = purchased_template_id or (session.purchased_template_id if session.purchased_template else None)

            inline_fields = body.get("fields")
            fields = []
            tool_price = None

            if inline_fields:
                fields = list(inline_fields)
            elif template_id:
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

            return fields, tool_price, body, user, session

        fields, tool_price, body, user, session = await sync_to_async(_get_initial_data)()
        if fields is None:
            return StreamingHttpResponse(
                iter([f"data: {json.dumps({'type': 'error', 'message': 'Unauthorized'})}\n\n"]),
                status=401, content_type="text/event-stream"
            )

        def _get_catalog_summary():
            active_templates = Template.objects.filter(is_active=True).select_related("tool")
            lines = []
            for t in active_templates:
                tool_name = t.tool.name if t.tool else "Platform"
                kw = ", ".join(t.keywords[:5]) if t.keywords else ""
                lines.append(f'- "{t.name}" (ID: {t.id}) Tool: {tool_name} Tags: {kw}')
            return "\n".join(lines)

        catalog_str = await sync_to_async(_get_catalog_summary)()

        # Persistence: Save the new user message if content is provided
        messages = body.get("messages", [])
        if not messages and session:
            # Sync history from DB if frontend is empty (e.g. on fresh session load)
            def _load_history():
                db_msgs = session.messages.all()
                loaded = []
                for m in db_msgs:
                    if m.role in ['user', 'assistant']:
                        msg_obj = {"role": m.role, "content": m.content}
                        if m.metadata.get("attachmentUrl"):
                            msg_obj["attachmentUrl"] = m.metadata["attachmentUrl"]
                        loaded.append(msg_obj)
                return loaded
            messages = await sync_to_async(_load_history)()

        last_msg = messages[-1] if messages else None
        if last_msg and last_msg.get("role") == "user":
            await sync_to_async(AiChatMessage.objects.create)(
                session=session,
                role="user",
                content=last_msg.get("content", ""),
                metadata={"attachmentUrl": last_msg.get("attachmentUrl")} if last_msg.get("attachmentUrl") else {}
            )

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

        is_editor_mode = bool(session.template or session.purchased_template)
        system_prompt = build_system_prompt(
            fields, 
            tool_price=tool_price, 
            catalog=catalog_str,
            template_id=str(session.template.id) if session.template else None,
            purchased_template_id=str(session.purchased_template.id) if session.purchased_template else None
        )
        tools = _build_tools(fields, valid_field_ids, has_image, is_editor_mode=is_editor_mode)
        formatted_messages = _format_messages(messages, image_base64, fields)
        client = AsyncOpenAI(api_key=settings.AI_API_KEY, base_url=settings.AI_BASE_URL)

        def _resolve_image(field_id: str) -> str | None:
            val = current_values.get(field_id, "")
            if val and str(val).startswith("data:image"): return val
            return image_base64

        async def stream_generator():
            yield f"data: {json.dumps({'type': 'session_id', 'id': str(session.id)})}\n\n"
            
            tool_accumulator: dict[int, dict] = {}
            assistant_text_buffer = []
            assistant_metadata = {}

            try:
                try:
                    stream = await client.chat.completions.create(
                        model=settings.AI_MODEL,
                        messages=[{"role": "system", "content": system_prompt}, *formatted_messages],
                        tools=tools or None,
                        stream=True, temperature=0.4,
                        max_tokens=2048,
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
                    if delta.content:
                        assistant_text_buffer.append(delta.content)
                        yield f"data: {json.dumps({'type': 'text', 'delta': delta.content})}\n\n"
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in tool_accumulator:
                                tool_accumulator[idx] = {"id": "", "name": "", "arguments": ""}
                            if tc.id: tool_accumulator[idx]["id"] = tc.id
                            if tc.function:
                                if tc.function.name: tool_accumulator[idx]["name"] = tc.function.name
                                if tc.function.arguments: tool_accumulator[idx]["arguments"] += tc.function.arguments

                if tool_accumulator:
                    tool_messages: list[dict] = [
                        {"role": "system", "content": system_prompt},
                        *formatted_messages,
                        {
                            "role": "assistant", "content": "".join(assistant_text_buffer) or None,
                            "tool_calls": [
                                {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                                for tc in tool_accumulator.values()
                            ],
                        },
                    ]
                    
                    # Store assistant message with tool calls
                    assistant_msg_db = await sync_to_async(AiChatMessage.objects.create)(
                        session=session,
                        role="assistant",
                        content="".join(assistant_text_buffer) or None,
                        metadata={"tool_calls": list(tool_accumulator.values())}
                    )

                    for tc_data in tool_accumulator.values():
                        name = tc_data["name"]
                        try: args = json.loads(tc_data["arguments"])
                        except Exception: args = {}

                        status_labels = {
                            "remove_bg": "Removing background...",
                            "crop_image": "Cropping image...",
                            "analyze_document": "Analyzing document structure...",
                            "search_web": "Searching the web...",
                            "download_document": "Generating document file...",
                            "write_signature": "Generating signature...",
                        }
                        if name in status_labels:
                            yield f"data: {json.dumps({'type': 'status', 'label': status_labels[name]})}\n\n"
                            await asyncio.sleep(0.1)

                        result_content = await execute_tool(
                            name, args, tc_data["id"], valid_field_ids, 
                            user, _resolve_image, current_values, fields
                        )
                        for event in result_content["events"]:
                            yield f"data: {json.dumps(event)}\n\n"
                            # Collect metadata for assistant message (suggestions, cards, etc)
                            if event["type"] in ["tool_cards", "clarification", "template_loaded", "purchased", "document_ready", "field_suggestion"]:
                                if event["type"] not in assistant_metadata:
                                    assistant_metadata[event["type"]] = []
                                assistant_metadata[event["type"]].append(event)

                        tool_messages.append({
                            "role": "tool", "tool_call_id": tc_data["id"],
                            "name": name, "content": result_content["text"],
                        })
                        
                        # Save Tool result message
                        await sync_to_async(AiChatMessage.objects.create)(
                            session=session,
                            role="tool",
                            content=result_content["text"],
                            metadata={"tool_call_id": tc_data["id"], "name": name}
                        )

                    second_stream = await client.chat.completions.create(
                        model=settings.AI_MODEL, messages=tool_messages,
                        stream=True, temperature=0.4,
                        max_tokens=2048,
                    )
                    second_text_buffer = []
                    async for chunk2 in second_stream:
                        if chunk2.choices and chunk2.choices[0].delta.content:
                            txt = chunk2.choices[0].delta.content
                            second_text_buffer.append(txt)
                            yield f"data: {json.dumps({'type': 'text', 'delta': txt})}\n\n"
                    
                    # Save the final second response
                    await sync_to_async(AiChatMessage.objects.create)(
                        session=session,
                        role="assistant",
                        content="".join(second_text_buffer),
                        metadata=assistant_metadata
                    )

                else:
                    # No tools used, save the single assistant response
                    await sync_to_async(AiChatMessage.objects.create)(
                        session=session,
                        role="assistant",
                        content="".join(assistant_text_buffer),
                        metadata=assistant_metadata
                    )

                # TRIGGER AI TITLE GENERATION if this is a new Global chat (no template) and we have enough turns
                if not session.template and not session.purchased_template and session.title == "New Chat":
                    message_count = await sync_to_async(session.messages.count)()
                    if message_count >= 2:
                        try:
                            # Quick background call to summarize the title
                            summary_chain = [
                                {"role": "system", "content": "Generate a concise 3-5 word title for this chat based on the conversation topic. Respond with ONLY the title. No quotes."},
                                *formatted_messages,
                                {"role": "assistant", "content": "".join(assistant_text_buffer)}
                            ]
                            title_resp = await client.chat.completions.create(
                                model=settings.AI_MODEL,
                                messages=summary_chain,
                                max_tokens=20,
                            )
                            new_title = title_resp.choices[0].message.content.strip()
                            if new_title:
                                session.title = new_title[:100]
                                await sync_to_async(session.save)()
                                yield f"data: {json.dumps({'type': 'session_updated', 'title': session.title})}\n\n"
                        except Exception: pass

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
