# Spec: Gemini OAuth2, Universal Orchestrator, and Agnostic Hooks

**Status:** Retroactive Documentation (Implemented 2026-05-10)  
**Topic:** Model-Agnostic Runtime Architecture and Gemini Security  

## Overview
This specification details the transition from a Claude-centric runtime to a model-agnostic architecture. It introduces a Universal Orchestrator to centralize tool/hook execution and implements Gemini support via Vertex AI with strict OAuth2/ADC enforcement (G1 standard).

## Architecture

### 1. Agnostic Hook System (`hsb.runtime.hooks`)
The original `HookMatcher` was tied to the Anthropic SDK. We introduced a native `HookMatcher` that uses generic callback signatures:
- **Events:** `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PreCompact`.
- **Matching:** Regex-based tool name matching.
- **Portability:** Runtimes like `ClaudeRuntime` translate these agnostic hooks to their native equivalents, while other runtimes (Gemini/Codex) will eventually consume them via the Orchestrator.

### 2. Universal Orchestrator (`hsb.runtime.orchestrator`)
A new layer sitting above `Runtime` implementations.
- **Purpose:** Centralize the tool execution loop and hook lifecycle management.
- **Future-proofing:** Enables dynamic model routing (e.g., sending simple tasks to Gemini Flash and complex ones to Claude Opus).

### 3. Gemini Vertex AI Integration
Refactored `GeminiRuntime` to align with the project's "Zero Keys" philosophy:
- **Backend:** Switched from Google AI Studio to Google Cloud Vertex AI.
- **Auth:** Application Default Credentials (ADC) via OAuth2. Rejects `GEMINI_API_KEY`.
- **Infrastructure:** Integrated with Docker volumes for multi-org credential isolation.

## Security Constraints (G1 Enforcement)
- **Claude:** `CLAUDE_CODE_OAUTH_TOKEN` required; `ANTHROPIC_API_KEY` forbidden.
- **Gemini:** `GOOGLE_CLOUD_PROJECT` + ADC required; `GEMINI_API_KEY` forbidden.
- **Codex:** `CODEX_HOME` + OAuth required; `OPENAI_API_KEY` forbidden.

## Implementation Details
- `scripts/auth-gemini.sh`: Wraps `gcloud auth application-default login`.
- `src/hsb/runtime/gemini_guards.py`: Validates ADC and Project ID presence.
- `src/hsb/agents/_sdk_options.py`: Wraps every resolved runtime in the `UniversalOrchestrator`.
