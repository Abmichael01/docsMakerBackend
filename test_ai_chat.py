#!/usr/bin/env python3
"""
AI Chat Behavior Test Harness
Tests the AI's responses to various prompts and evaluates behavior.
Run with: python test_ai_chat.py
"""
import os
import sys
import json
import time
import asyncio

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "serverConfig.settings")

import django
django.setup()

from django.test import RequestFactory, override_settings
from django.contrib.auth import get_user_model
from api.views.ai_chat import AiChatView
from api.models import Template, Tool

User = get_user_model()

# ─── Test Configuration ────────────────────────────────────────────────
BASE_URL = "http://localhost:19527"
MAX_STREAM_CHARS = 8000  # safety limit per test

# ─── Test Cases ────────────────────────────────────────────────────────
# Each case: {name, prompt, expects, not_expects, description}
# expects/not_expects are checked against the raw SSE events, not just text

TEST_CASES = [
    # === SEARCH-FIRST BEHAVIOR (these SHOULD trigger search_tools tool call) ===
    {
        "name": "search_first_flight",
        "prompt": "I need a flight itinerary",
        "expects_tool_call": "search_tools",  # AI must call search_tools
        "not_expect_tool_call": "suggest_options",  # Must NOT suggest before searching
        "description": "AI must search for flight templates first"
    },
    {
        "name": "search_first_card",
        "prompt": "show me card templates",
        "expects_tool_call": "search_tools",
        "not_expect_tool_call": "suggest_options",
        "description": "Should search for card templates"
    },
    {
        "name": "no_clarification_before_search",
        "prompt": "flight",
        "expects_tool_call": "search_tools",
        "not_expect_tool_call": "suggest_options",
        "description": "Single keyword must trigger search, NOT clarification question"
    },
    {
        "name": "vague_request",
        "prompt": "I need a travel document",
        "expects_tool_call": "search_tools",
        "not_expect_tool_call": "",  # suggest_options is OK after search
        "description": "Broad travel intent should search flight-related templates"
    },

    # === GENERAL CHAT (should NOT trigger search_tools) ===
    {
        "name": "general_question",
        "prompt": "What is SharpToolz?",
        "expects_tool_call": "",  # no tool call expected
        "not_expect_tool_call": "search_tools",
        "description": "General questions should NOT trigger search"
    },
    {
        "name": "pricing_question",
        "prompt": "How much does it cost?",
        "expects_tool_call": "",
        "not_expect_tool_call": "search_tools",
        "description": "Pricing questions should answer directly"
    },
    {
        "name": "features_question",
        "prompt": "What can I do on this platform?",
        "expects_tool_call": "",
        "not_expect_tool_call": "search_tools",
        "description": "Feature questions should NOT trigger search"
    },

    # === OUT OF SCOPE ===
    {
        "name": "out_of_scope",
        "prompt": "Write me a Python script",
        "expects_tool_call": "",
        "not_expect_tool_call": "search_tools",
        "description": "Should refuse out-of-scope requests"
    },

    # === TEMPLATE RESULTS QUALITY ===
    # Note: These test that search_tools is called AND returns cards
    # The actual templates in DB have typos ("Fligth Iteneray", "New Yourk")
    # so we test with broader terms the AI naturally uses
    {
        "name": "flight_search_returns_results",
        "prompt": "show me flight templates",
        "expects_tool_call": "search_tools",
        "expects_cards": True,
        "description": "Searching for 'flight' should return flight templates"
    },
    {
        "name": "cards_search_returns_results",
        "prompt": "show me flight templates",
        "expects_tool_call": "search_tools",
        "expects_cards": True,
        "description": "Searching for 'flight' should return flight templates"
    },
    {
        "name": "no_match_honest_response",
        "prompt": "I need a medical certificate",
        "expects_tool_call": "search_tools",
        "not_expect_tool_call": "suggest_options",
        "description": "When nothing matches, AI should search and show fallback templates"
    },
    {
        "name": "show_all_templates",
        "prompt": "show me all templates",
        "expects_tool_call": "search_tools",
        "expects_cards": True,
        "description": "'show all' should trigger show-all mode and return all templates"
    },
    {
        "name": "what_else_returns_results",
        "prompt": "what else do you have",
        "expects_tool_call": "search_tools",
        "expects_cards": True,
        "description": "'what else' should trigger show-all mode"
    },
    {
        "name": "use_template_triggers_load",
        "prompt": "use the flight itinerary template",
        "expects_tool_call": "search_tools",
        "description": "When user says 'use [template]', AI should search first then load it"
    },
]


async def collect_stream_response(view, request):
    """Collect SSE stream response into a single string."""
    response = await view.post(request)
    chunks = []
    async for chunk in response.streaming_content:
        text = chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
        chunks.append(text)
        if sum(len(c) for c in chunks) > MAX_STREAM_CHARS:
            break
    full = "".join(chunks)

    # Parse SSE events
    events = []
    for line in full.split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            try:
                event = json.loads(line[6:])
                events.append(event)
            except json.JSONDecodeError:
                pass

    return {
        "raw": full,
        "events": events,
        "tool_calls": [e for e in events if e.get("type") == "text"],
        "tool_card_events": [e for e in events if e.get("type") == "tool_cards"],
        "clarification_events": [e for e in events if e.get("type") == "clarification"],
        "full_text": " ".join(e.get("delta", "") for e in events if e.get("type") == "text"),
        "searched": any("search_tools" in str(e) for e in events),
        "suggested_options": any(e.get("type") == "clarification" for e in events),
        "_raw_events": [e for e in events],  # for debugging
    }


async def run_test(test_user, test_case):
    """Run a single test case and return (passed, details)."""
    factory = RequestFactory()

    # Build request body — no template_id/purchased_template_id = General Assistant mode
    body = json.dumps({
        "messages": [
            {"role": "user", "content": test_case["prompt"]}
        ],
        "current_values": {},
    }).encode("utf-8")

    request = factory.post("/api/ai-chat/", data=body, content_type="application/json")
    request.user = test_user
    request._body = body

    view = AiChatView()
    result = await collect_stream_response(view, request)

    # Evaluate
    passed = True
    issues = []

    full_text = result["full_text"].lower()
    raw_events = result["_raw_events"]

    # Check for specific tool calls in events
    called_tools = set()
    search_queries = []
    for e in raw_events:
        if e.get("type") == "status" and "Finding templates" in str(e.get("label", "")):
            called_tools.add("search_tools")
            # Extract the query from the status label
            label = e.get("label", "")
            if ":" in label:
                search_queries.append(label.split(":", 1)[1].strip())
        if e.get("type") == "clarification":
            called_tools.add("suggest_options")
        if e.get("type") == "tool_cards":
            called_tools.add("search_tools")

    # Check expects_tool_call
    expected_call = test_case.get("expects_tool_call", "")
    if expected_call and expected_call not in called_tools:
        passed = False
        issues.append(f"FAIL: Expected {expected_call} call but didn't find one. Called: {called_tools}")

    # Check not_expect_tool_call
    not_expected = test_case.get("not_expect_tool_call", "")
    if not_expected and not_expected in called_tools:
        passed = False
        issues.append(f"FAIL: {not_expected} was called but should NOT have been")

    # Check expects_cards
    if test_case.get("expects_cards"):
        card_events = result.get("tool_card_events", [])
        has_cards = any(e.get("cards") for e in card_events)
        if not has_cards:
            passed = False
            issues.append(f"FAIL: Expected template cards in response but got none")

    return passed, {
        "name": test_case["name"],
        "prompt": test_case["prompt"],
        "description": test_case["description"],
        "passed": passed,
        "issues": issues,
        "full_text_preview": result["full_text"][:500] if result["full_text"] else "(empty)",
        "called_tools": list(called_tools),
        "card_count": len(result.get("tool_card_events", [])[-1].get("cards", [])) if result.get("tool_card_events") else 0,
        "search_queries": search_queries,
    }


async def run_all_tests(test_user):
    """Run all tests asynchronously."""
    results = []
    passed_count = 0
    failed_count = 0

    for i, tc in enumerate(TEST_CASES, 1):
        print(f"[{i}/{len(TEST_CASES)}] {tc['name']}...", end=" ", flush=True)
        passed, detail = await run_test(test_user, tc)

        if passed:
            print(f"PASSED")
            passed_count += 1
        else:
            print(f"FAILED")
            failed_count += 1
            for issue in detail["issues"]:
                print(f"    {issue}")

        results.append(detail)
        time.sleep(1.5)  # rate limit friendly

    return results, passed_count, failed_count


def main():
    # Create/get test user
    User = get_user_model()
    test_user, _ = User.objects.get_or_create(
        username="ai_test_user",
        defaults={"email": "test@ai.com"}
    )

    print("=" * 70)
    print("  SHARP GUY AI CHAT — BEHAVIOR TEST SUITE")
    print("=" * 70)
    print(f"\nRunning {len(TEST_CASES)} test cases...\n")

    results, passed_count, failed_count = asyncio.run(run_all_tests(test_user))

    # Summary
    print("\n" + "=" * 70)
    print(f"  RESULTS: {passed_count} passed, {failed_count} failed, {len(TEST_CASES)} total")
    print("=" * 70)

    if failed_count > 0:
        print("\n── FAILED TESTS DETAIL ──\n")
        for r in results:
            if not r["passed"]:
                print(f"❌ {r['name']}")
                print(f"   Prompt: {r['prompt']}")
                print(f"   Issue: {'; '.join(r['issues'])}")
                print(f"   Called tools: {r.get('called_tools', [])}")
                print(f"   Search queries used: {r.get('search_queries', [])}")
                print(f"   Cards: {r.get('card_count', 0)}")
                print(f"   Response: {r['full_text_preview'][:300]}")
                print()
    else:
        print("\n✅ ALL TESTS PASSED!")

    # Save report
    report_path = os.path.join(os.path.dirname(__file__), "ai_test_report.json")
    with open(report_path, "w") as f:
        json.dump({
            "passed": passed_count,
            "failed": failed_count,
            "total": len(TEST_CASES),
            "results": results
        }, f, indent=2)
    print(f"Full report saved to: {report_path}")

    return failed_count == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
