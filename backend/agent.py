"""
DeepSeek Agent for Green Canopy.

Initialises a DeepSeek client via the standard openai library, loads the
tool definitions from agent_tools.py, and implements a standard tool-calling
Agent loop that:
  1. Sends the user message + tool definitions to DeepSeek
  2. If the model returns a tool call, executes it locally
  3. Feeds the tool result back into the conversation
  4. Repeats until the model produces a final text response

Usage:
    python -m backend.agent "I care about climate and clean water..."

Requires DEEPSEEK_API_KEY in the environment.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI

from backend.agent_tools import TOOL_DEFINITIONS, execute_tool

# ---------------------------------------------------------------------------
# DeepSeek client
# ---------------------------------------------------------------------------

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"  # DeepSeek-V4 is accessible via this model id


def _load_deepseek_key() -> str:
    """Return the DeepSeek API key from environment or local .env files.

    Checks in order:
      1. DEEPSEEK_API_KEY environment variable
      2. .env.local file (key=value format, one per line)
      3. .env file (same format)
    """
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key:
        return key

    # Try reading from .env.local or .env in the project root
    root = Path(__file__).resolve().parent.parent  # backend/ → repo root
    for env_file in (root / ".env.local", root / ".env"):
        if not env_file.is_file():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k == "DEEPSEEK_API_KEY" and v:
                return v

    raise RuntimeError(
        "DEEPSEEK_API_KEY is not set. You can set it via:\n"
        "  - Environment variable: $env:DEEPSEEK_API_KEY='sk-...' (PowerShell)\n"
        "  - .env.local file in the project root: DEEPSEEK_API_KEY=sk-...\n"
        "  - .env file in the project root: DEEPSEEK_API_KEY=sk-..."
    )


def _build_client() -> OpenAI:
    api_key = _load_deepseek_key()
    return OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a professional AI Assistant for Sustainability and Investment (Green Canopy). \
You MUST strictly generate all your responses, summaries, and tool-call explanations \
in English at all times, regardless of the user's input language. Never reply in any \
other language.

Your capabilities:
- Build investor profiles from questionnaire answers
- Calculate sustainability alignment scores for individual holdings
- Explain how alignment scores are derived (priority matching, ESG data, diversification credits)
- Convert portfolio weights into dollar and percentage allocations
- Generate portfolio narratives that summarise sector mix, priority coverage, and diversification
- Create fund snapshots from top holdings

Important rules:
1. You do NOT provide financial advice, predict returns, or recommend specific securities.
2. You do NOT invent ESG data or sustainability scores — all scores come from the tools.
3. You do NOT replace the deterministic portfolio optimiser — the optimiser runs separately.
4. When a tool returns data, explain it clearly to the user in plain English.
5. If the user asks something outside your tools' capabilities, be honest about the limitation.
6. Always mention that Green Canopy's scores are based on classification tags and publicly \
available data, not third-party ESG ratings.
7. Historical performance is descriptive and does not guarantee future results.
"""

# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

def run_agent(user_message: str, client: OpenAI | None = None) -> str:
    """Run the tool-calling agent loop for a single user message.

    Returns the final text response from the model.
    """
    if client is None:
        client = _build_client()

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    # The DeepSeek API supports tool calling with the same interface as OpenAI.
    # We allow up to 5 turns to prevent infinite loops.
    max_turns = 5
    for _ in range(max_turns):
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            temperature=0.3,  # Low temperature for deterministic, factual responses
        )

        choice = response.choices[0]
        message = choice.message

        # If the model produces a final text response, return it
        if message.content and not message.tool_calls:
            return message.content

        # If the model wants to call tools, execute them
        if message.tool_calls:
            # Append the assistant message (with tool_calls) to the conversation
            messages.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ],
            })

            # Execute each tool call and append results
            for tc in message.tool_calls:
                tool_name = tc.function.name
                try:
                    arguments = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    tool_result = json.dumps({"error": "Invalid JSON arguments"})
                else:
                    try:
                        tool_result = execute_tool(tool_name, arguments)
                    except Exception as exc:
                        tool_result = json.dumps({"error": str(exc)})

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_result,
                })

        # If the model replied with text but no tool calls and no content, break
        if not message.content and not message.tool_calls:
            return "I'm sorry, I wasn't able to process that request. Could you rephrase?"

    return "I've reached the maximum number of processing steps. Please try a more specific question."


# ---------------------------------------------------------------------------
# CLI entry point (for ad-hoc testing)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m backend.agent \"Your question here\"")
        sys.exit(1)

    user_input = " ".join(sys.argv[1:])
    try:
        result = run_agent(user_input)
        print(result)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)