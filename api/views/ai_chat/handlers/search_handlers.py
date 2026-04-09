import json
from asgiref.sync import sync_to_async
from ....models import Template

async def handle_search_web(args):
    events = []
    query = args.get("query", "")
    events.append({"type": "status", "label": f"Searching: {query}"})
    try:
        from duckduckgo_search import DDGS
        results = DDGS().text(query, max_results=5)
        res_text = "\n".join([f"- {r['title']}: {r['body']}" for r in results])
        return {"events": events, "text": res_text or "No results found."}
    except Exception as exc:
        return {"events": events, "text": f"Search failed: {exc}"}

async def handle_search_tools(args):
    events = []
    query = args.get("query", "")
    load_best = args.get("load_best_match", False)
    events.append({"type": "status", "label": f"Finding templates: {query}"})

    try:
        def _search(q):
            from django.db.models import Q
            q_lower = q.lower().strip()
            show_all_keywords = [
                "all", "everything", "browse", "available", "list", "catalog",
                "what do you have", "what else", "anything else", "other templates",
                "more templates", "show all", "full catalog",
            ]
            is_show_all = any(kw in q_lower for kw in show_all_keywords) or not q_lower

            if is_show_all:
                qs = Template.objects.filter(is_active=True).select_related("tool").order_by("-hot", "name")[:20]
                cards = []
                for tpl in qs:
                    cards.append({
                        "id": str(tpl.id),
                        "name": tpl.name,
                        "description": (tpl.tool.description or "")[:120] if tpl.tool else "",
                        "price": str(tpl.tool.price) if tpl.tool else "0",
                        "toolName": tpl.tool.name if tpl.tool else "General",
                        "banner": tpl.banner.url if tpl.banner else "",
                    })
                return cards, False

            terms = [t for t in q_lower.split() if len(t) > 1]
            if not terms:
                qs = Template.objects.filter(is_active=True).select_related("tool").order_by("-hot", "name")[:20]
                cards = []
                for tpl in qs:
                    cards.append({
                        "id": str(tpl.id),
                        "name": tpl.name,
                        "description": (tpl.tool.description or "")[:120] if tpl.tool else "",
                        "price": str(tpl.tool.price) if tpl.tool else "0",
                        "toolName": tpl.tool.name if tpl.tool else "General",
                        "banner": tpl.banner.url if tpl.banner else "",
                    })
                return cards, True

            broad_q = Q()
            for term in terms:
                broad_q |= (
                    Q(name__icontains=term)
                    | Q(tool__name__icontains=term)
                    | Q(tool__description__icontains=term)
                )
            candidates_qs = (
                Template.objects.filter(Q(is_active=True) & broad_q)
                .select_related("tool")
                .distinct()
            )
            kw_q = Q()
            for term in terms:
                kw_q |= Q(keywords__icontains=term)
            kw_candidates_qs = (
                Template.objects.filter(Q(is_active=True) & kw_q)
                .select_related("tool")
                .distinct()
            )
            seen_ids = set()
            candidates = []
            for tpl in list(candidates_qs) + list(kw_candidates_qs):
                if tpl.pk not in seen_ids:
                    seen_ids.add(tpl.pk)
                    candidates.append(tpl)

            is_fallback = False
            if not candidates:
                candidates = list(
                    Template.objects.filter(is_active=True)
                    .select_related("tool")
                    .order_by("-hot", "name")[:20]
                )
                is_fallback = True

            def _score(tpl):
                name_l = (tpl.name or "").lower()
                kw_raw = tpl.keywords
                if isinstance(kw_raw, list):
                    kw_l = " ".join(str(k) for k in kw_raw).lower()
                else:
                    kw_l = str(kw_raw or "").lower()
                tool_name_l = (tpl.tool.name or "").lower() if tpl.tool else ""
                tool_desc_l = (tpl.tool.description or "").lower() if tpl.tool else ""
                combined = f"{name_l} {kw_l} {tool_name_l} {tool_desc_l}"
                score = 0
                if q_lower == name_l:
                    score += 12  # Exact match wins decisively
                elif q_lower in name_l:
                    score += 8
                if all(t in name_l for t in terms):
                    score += 6
                if all(t in combined for t in terms):
                    score += 4
                matched = sum(1 for t in terms if t in combined)
                score += matched
                if tpl.hot:
                    score += 1
                return score

            scored = sorted(candidates, key=_score, reverse=True)[:20]
            cards = []
            for tpl in scored:
                cards.append({
                    "id": str(tpl.id),
                    "name": tpl.name,
                    "description": (tpl.tool.description or "")[:120] if tpl.tool else "",
                    "price": str(tpl.tool.price) if tpl.tool else "0",
                    "toolName": tpl.tool.name if tpl.tool else "General",
                    "banner": tpl.banner.url if tpl.banner else "",
                })
            return cards, is_fallback

        cards, is_fallback = await sync_to_async(_search)(query)

        if cards:
            if load_best:
                best = cards[0]
                events.append({
                    "type": "template_loaded",
                    "template": {
                        "id": best["id"],
                        "name": best["name"],
                        "toolName": best["toolName"],
                        "price": best["price"],
                        "banner": best["banner"],
                    },
                })
                return {
                    "events": events,
                    "text": f"Loaded **{best['name']}** into the editor.",
                }

            events.append({"type": "tool_cards", "cards": cards, "fallback": is_fallback, "query": query})
            lines = [f"- **{c['name']}** (ID:{c['id']}, ${c['price']})" for c in cards]
            prefix = "I found these templates:" if not is_fallback else "No direct matches. Here are popular options:"
            return {"events": events, "text": f"{prefix}\n" + "\n".join(lines)}
        return {"events": events, "text": "No templates found for that query."}
    except Exception as exc:
        return {"events": events, "text": f"Search failed: {exc}"}
