# Debug Tricks

## MCP Endpoint for AI-Assisted Debugging

Next.js provides a `/_next/mcp` endpoint during development for AI-assisted debugging via MCP (Model Context Protocol). Available automatically in Next.js 16+.

**Important**: Check your terminal output for the actual dev server port — don't assume port 3000.

The endpoint accepts JSON-RPC 2.0 requests via HTTP POST. Available tools:

| Tool | Description |
|------|-------------|
| `get_errors` | Retrieves current build and runtime errors with source maps |
| `get_routes` | Scans the filesystem to discover all application routes |
| `get_project_metadata` | Returns the project path and dev server URL |
| `get_page_metadata` | Runtime metadata about page renders (requires active browser session) |
| `get_logs` | Locates the Next.js development log file |
| `get_server_action_by_id` | Finds a specific Server Action by its identifier |

## Targeted Route Rebuilding (Next.js 16+)

Use `--debug-build-paths` to rebuild specific routes instead of the entire app:

```bash
next build --debug-build-paths "/dashboard"
next build --debug-build-paths "/blog/[slug]"
```

Useful for:
- Verifying fixes to specific pages
- Debugging static generation for particular routes
- Resolving build errors faster
