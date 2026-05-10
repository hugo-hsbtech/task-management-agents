# Plan: Gemini OAuth2 and Agnostic Architecture

**Status:** Retroactive Documentation (Completed 2026-05-10)

## Phase 1: Agnostic Hook Abstraction
- [x] Create `hsb.runtime.hooks.HookMatcher`.
- [x] Update `protocol.py` to use agnostic hook types.
- [x] Refactor `src/hsb/agents/hooks.py` to use the new `HookMatcher`.
- [x] Implement hook translation in `src/hsb/runtime/claude.py`.

## Phase 2: Universal Orchestrator & Multi-Runtime Support
- [x] Implement `hsb.runtime.orchestrator.UniversalOrchestrator`.
- [x] Update `src/hsb/agents/_sdk_options.py` to wrap runtimes in the Orchestrator.
- [x] Fix `langfuse` import compatibility across all runtimes.

## Phase 3: Gemini OAuth2 & Vertex AI
- [x] Create `src/hsb/runtime/gemini_guards.py` for G1 compliance.
- [x] Refactor `src/hsb/runtime/gemini.py` to use Vertex AI with ADC.
- [x] Add `scripts/auth-gemini.sh` and `make auth-gemini` target.
- [x] Update `docker-compose.yml` with `hsb-gcloud-auth` volume.
- [x] Update `GET-STARTED.md` and `.env.example`.

## Phase 4: Verification
- [x] Add `tests/runtime/test_gemini_guards.py`.
- [x] Update `tests/runtime/test_resolve_runtime.py` to assert `UniversalOrchestrator` wrapping.
- [x] Verify `ClaudeRuntime` hook regression.
- [x] All runtime tests passing.
