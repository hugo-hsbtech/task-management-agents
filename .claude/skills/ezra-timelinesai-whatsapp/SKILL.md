---
name: ezra-timelinesai-whatsapp
description: "[NOT APPLICABLE — Ezra-specific reference; do not invoke in this project] TimelinesAI API patterns for WhatsApp automation in Ezra. Use when building n8n workflows, agents, or services that interact with WhatsApp via TimelinesAI. Covers: posting to communities, reading messages, file uploads, webhooks, sub-group readability, and known limitations. Triggers on: 'TimelinesAI', 'WhatsApp API', 'WhatsApp automation', 'post to community', 'WhatsApp webhook', 'community announcement'."
version: 1.0.0
tags: [whatsapp, timelinesai, automation, community, n8n]
---

# TimelinesAI WhatsApp Integration

Patterns and findings for automating WhatsApp via TimelinesAI's API. Based on production testing against WhatsApp Communities.

## Important

TimelinesAI uses the **WhatsApp Web protocol** (QR code sync), not the Meta Cloud API. This means:
- No Meta Business Verification required
- Works with personal WhatsApp and WhatsApp Business App
- Some WhatsApp features are not accessible via the API (see Limitations)
- Chat IDs are **per TimelinesAI account** — the same WhatsApp group has a different chat ID depending on which phone is connected

## API Reference

### Base URL

```
https://app.timelines.ai/integrations/api
```

### Authentication

Bearer token in the `Authorization` header:

```
Authorization: Bearer <token>
```

Token is generated in TimelinesAI dashboard: Settings > API Access.

### Core Endpoints

#### List Chats (paginated)

```
GET /chats?page=1&per_page=50
```

Returns all chats visible to the connected WhatsApp account: 1:1 chats, groups, community announcements, and sub-groups. Paginated — iterate until empty page.

Each chat includes: `id`, `name`, `jid`, `is_group`, `group_members`, `last_message_timestamp`, `is_allowed_to_message`.

#### Get Chat Details

```
GET /chats/{chat_id}
```

Returns chat metadata including `group_members` array with `name`, `phone`, `role` (Owner/Admin/Member), and `chat_id` for each member.

#### Send Text Message

```
POST /chats/{chat_id}/messages
Content-Type: application/json

{"text": "Your message here"}
```

Works for: 1:1 chats, groups, community announcement channels, sub-groups.

Returns: `{"status": "ok", "data": {"message_uid": "..."}}`

**Delivery delay:** Messages sent via API may take 1-5 minutes to appear in WhatsApp. This is normal for the Web protocol — not real-time.

#### Send Message by Phone Number

```
POST /messages
Content-Type: application/json

{"phone": "+44...", "text": "Your message"}
```

For sending to a contact by phone number (creates 1:1 chat if needed).

#### Upload File with Message

```
POST /files_upload
Content-Type: multipart/form-data

file: <binary file data>
chat_id: <chat_id>
text: <optional caption>
```

**Critical:** This endpoint only accepts **binary file uploads** via multipart form data. It does NOT accept URLs. If you have a URL, download the file first, then upload the binary.

```bash
# Correct — binary upload
curl -X POST /files_upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@/path/to/file.pdf" \
  -F "chat_id=12345" \
  -F "text=Caption here"

# WRONG — URL upload (silently accepted but not delivered)
curl -X POST /files_upload \
  -H "Content-Type: application/json" \
  -d '{"url": "https://...", "chat_id": 12345}'  # Returns 405
```

#### Get Messages

```
GET /chats/{chat_id}/messages?per_page=10
```

Returns messages with: `uid`, `text`, `sender_phone`, `sender_name`, `timestamp`, `from_me`, `origin` (synced from WhatsApp / Public API), `has_attachment`, `attachment_url`, `reactions`.

#### Get Reactions

```
GET /messages/{message_uid}/reactions
```

Returns: `{"users": [...], "reactions": {"emoji": count}, "total": N}`

Each user entry includes: `name`, `phone`, `reaction` (emoji), `current` (boolean).

**Note:** Only works on 1:1 chats and regular groups. Returns empty for community announcements (see Limitations).

### Webhooks

#### List Webhooks

```
GET /webhooks
```

#### Create Webhook

```
POST /webhooks
Content-Type: application/json

{
  "url": "https://your-endpoint.com/webhook",
  "event_type": "message:received:new"
}
```

#### Available Event Types

| Event | Description |
|-------|-------------|
| `message:new` | All messages (incoming + outgoing) |
| `message:received:new` | Incoming messages only |
| `message:sent:new` | Outgoing messages only |
| `chat:created` | New chat appears |
| `chat:received:created` | Contact initiates conversation |
| `chat:sent:created` | You start a conversation |
| `chat:assigned` | Chat assigned to team member |
| `chat:unassigned` | Chat unassigned |

**No dedicated reaction event exists.** Reactions are only included as a field in message payloads.

#### Delete Webhook

```
DELETE /webhooks/{webhook_id}
```

### WhatsApp Accounts

```
GET /whatsapp_accounts
```

Returns connected accounts with: `id`, `phone`, `status` (active/disconnected), `owner_name`, `connected_on`.

## WhatsApp Community Patterns

### Community Structure in TimelinesAI

A WhatsApp Community creates **two separate chats** in TimelinesAI:

1. **Community meta-group** — the community container. Usually 1 member (owner). `is_allowed_to_message` may be true but posting here doesn't reach members as announcements.
2. **Announcement channel** — where admins post. Multiple members visible. `is_allowed_to_message: true`. **This is the one you want.**

**How to identify the announcement channel:**
- Search for the community name — two entries appear
- The one with **more members** and `is_allowed_to_message: true` is the announcement channel
- The one with **fewer members** (often just the owner) is the meta-group
- Verify by checking `group_members` — announcement channel lists all admins + members

### Chat ID is Per-Account

The same WhatsApp community has a **different chat ID** depending on which TimelinesAI account is connected. If multiple team members connect their phones, each gets unique chat IDs for the same chats.

Always discover the chat ID from the specific TimelinesAI account that will be used for automation.

### Posting to Announcements

```
POST /chats/{announcement_chat_id}/messages
{"text": "Your announcement"}
```

Works. Message appears for all community members. Delivery takes 1-5 minutes.

### Reading Sub-group Messages

Community sub-groups appear as regular group chats in TimelinesAI. They are fully readable:
- Messages: sender name, phone, text, timestamp
- Members: name, phone, role
- Reactions: full data (name, phone, emoji) — unlike announcement channels

### Detecting New Members

Poll `GET /chats/{announcement_chat_id}` and check the `group_members` array. Compare against previous snapshot to detect joins/leaves.

No dedicated "member joined community" webhook event exists.

### Interest Detection via wa.me Links

Since reactions and polls are invisible on announcements (see Limitations), use wa.me links as the CTA:

```
https://wa.me/{phone}?text=Interested%20in%20{deal_name}
```

When a member taps this link:
1. WhatsApp opens a 1:1 chat with the specified phone number
2. The message is pre-filled with the URL-decoded text
3. Member taps Send
4. TimelinesAI `message:received:new` webhook fires
5. The incoming message contains the sender's phone + the pre-filled text (identifying which post they responded to)

This is the **only automated engagement tracking mechanism** for community announcements.

## Limitations (Confirmed by Testing)

### Community Announcements — What Doesn't Work

| Feature | Status | Details |
|---------|--------|---------|
| **Emoji reactions** | Not readable | `GET /messages/{uid}/reactions` always returns `total: 0` for announcement messages |
| **Polls — sending** | Not supported | Poll payload fields are silently ignored — sent as plain text |
| **Polls — reading** | Not supported | Polls posted manually in WhatsApp are invisible in the API message list |
| **Group creation** | Not supported | No endpoint exists. `POST /groups`, `/group`, `/chats/create`, `/create-group` all return 404 |
| **View/read receipts** | Not available | WhatsApp doesn't expose this for community announcements |

### What Works Everywhere

| Feature | 1:1 Chats | Groups | Announcement Channel | Sub-groups |
|---------|-----------|--------|---------------------|------------|
| Send text | Yes | Yes | Yes | Yes |
| Send files | Yes | Yes | Yes | Yes |
| Read messages | Yes | Yes | Yes | Yes |
| Read reactions | Yes | Yes | **No** | Yes |
| Read members | — | Yes | Yes | Yes |
| Webhooks | Yes | Yes | Yes | Yes |
| Polls | No | No | No | No |
| Create group | No | No | No | No |

### Advanced Privacy

WhatsApp's "Advanced privacy" setting (prevents chat exports) does **not** block API posting or reading. Tested and confirmed.

### Delivery Delay

Messages sent via API take 1-5 minutes to appear in WhatsApp. This is inherent to the Web protocol sync. Not a bug — expected behavior.

## n8n Integration Patterns

### HTTP Header Auth Credential

Create in n8n:
- **Name:** `Authorization`
- **Value:** `Bearer <TimelinesAI token>`

### Posting Workflow

```
Webhook (POST) → HTTP Request (POST /chats/{id}/messages) → Respond
```

Use n8n environment variables for `ANNOUNCEMENT_CHAT_ID` to switch between test and production communities.

URL expression: `=https://app.timelines.ai/integrations/api/chats/{{ $env.ANNOUNCEMENT_CHAT_ID }}/messages`

### Webhook Receiving Workflow

```
Webhook (POST, receives TimelinesAI events) → Filter (from_me != true) → Process → Notify
```

Register the n8n webhook URL in TimelinesAI:
```
POST /webhooks
{"url": "https://your-n8n.app.n8n.cloud/webhook/...", "event_type": "message:received:new"}
```

### File Upload Workflow (if needed)

TimelinesAI requires binary uploads. In n8n:
1. **HTTP Request** node to download file (responseFormat: file)
2. **HTTP Request** node to upload binary to `/files_upload` with `sendBinaryData: true`

Cannot send file URLs directly to TimelinesAI.

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| Message accepted (200) but not appearing in WhatsApp | Normal delivery delay | Wait 1-5 minutes |
| `405 Not Allowed` on file upload | Using JSON instead of multipart, or wrong endpoint | Use `POST /files_upload` with multipart form data and binary file |
| Reactions always return 0 | Reading from community announcement channel | This is a limitation — reactions only work on 1:1/group chats |
| Polls sent as plain text | API doesn't support poll creation | Create polls manually in WhatsApp |
| Chat ID not found | Wrong TimelinesAI account | Chat IDs are per-account. Search from the account that will be used for automation. |
| Webhook not firing | Webhook registered but n8n not listening | For test mode: click "Listen for test event" in n8n first. For production: activate the workflow. |
| `errors_counter` increasing on webhook | n8n endpoint unreachable or returning errors | Check n8n workflow is active and webhook URL is correct |
