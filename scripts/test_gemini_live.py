"""Quick smoke test for the Gemini provider.

Usage:
  # API Key (simplest — get one at https://aistudio.google.com/apikey)
  export GEMINI_API_KEY="AIzaSy..."
  uv run python scripts/test_gemini_live.py

  # OAuth2 ADC (requires GCP project)
  gcloud auth application-default login
  export GOOGLE_CLOUD_PROJECT="my-project"
  uv run python scripts/test_gemini_live.py --adc
"""

import asyncio
import sys

from llm_providers import ProviderRegistry, resolve_auth
from llm_providers.prompt import TextSystemPrompt
from llm_providers.protocol import ProviderOptions
from llm_providers.tools import ToolPolicy


async def main():
    use_adc = "--adc" in sys.argv
    auth_kind = "oauth2_adc" if use_adc else "api_key"

    # 1. Resolve auth
    auth = resolve_auth("gemini", auth_kind)
    print(f"✅ Auth resolved: {auth.kind}")

    # 2. Build the provider
    provider = ProviderRegistry.build("gemini", auth=auth)
    print(f"✅ Provider built: {provider.name} (backend: {type(provider._backend).__name__})")

    # 3. Query
    options = ProviderOptions(
        system_prompt=TextSystemPrompt(text="You are a helpful assistant. Reply in 1-2 sentences."),
        model="gemini-2.5-flash",
        max_turns=1,
        tool_policy=ToolPolicy(),
    )

    print("\n🚀 Querying Gemini (streaming)...\n")
    async for msg in provider.query("What is Python's GIL in one sentence?", options):
        if msg.is_final:
            print(f"\n\n✅ Final response:\n{msg.text}")
        else:
            print(msg.text, end="", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
