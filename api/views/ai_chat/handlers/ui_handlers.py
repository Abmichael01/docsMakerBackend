async def handle_suggest_options(args):
    events = []
    question = args.get("question", "")
    options = args.get("options", [])
    events.append({
        "type": "clarification",
        "question": question,
        "options": options,
    })
    return {"events": events, "text": f"Suggested options for: {question}"}
