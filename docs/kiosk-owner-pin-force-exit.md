# Owner PIN validation for native kiosk force exit

Implemented 8 October 2026. Local implementation; deploy the dashboard service before integrating against production. This is an API authorization check, not a Windows executable or a remote process-kill endpoint.

## Request

```http
POST https://hfg-dashboard.onrender.com/api/kiosk/owner-pin/validate
Authorization: Bearer <ACTIVE_PC_LINK_SESSION_TOKEN>
Content-Type: application/json

{
  "pin": "4837",
  "action": "force_exit"
}
```

PIN is a string, preserving leading zeros. Four to six ASCII digits are accepted for existing owner PIN compatibility. New PINs saved through Owner Security are four digits. Use the existing linked-PC token, not a gamer JWT or dashboard owner/staff JWT. The server derives cafe and PC identity from the active link; no vendor/console/owner ID must be supplied.

The owner PIN is the cafe's `vendor_pins` value, changed through Settings → Owner Security. Team member PINs from `vendor_staff` cannot authorize this operation. The same cafe owner PIN can authorize its linked PCs; another cafe's PIN cannot.

## Success: HTTP 200

Illustrative values only:

```json
{
  "status": "success",
  "authorized": true,
  "action": "force_exit",
  "authorization_id": "768a0e91-f736-427d-92db-93c226135a0c",
  "vendor_id": 41,
  "console_id": 269,
  "link_id": 12,
  "owner": {
    "id": "owner-41",
    "role": "owner",
    "name": "Cafe Owner"
  },
  "server_time": "2026-10-08T12:00:00+00:00",
  "expires_at": "2026-10-08T12:01:00+00:00",
  "expires_in_seconds": 60
}
```

No PIN or password is returned. Owner identifies the cafe owner represented by the PIN; a shared PIN does not establish which individual physically entered it. Responses are private/no-store.

`authorization_id` is a support/log correlation reference, not a JWT, transferable credential or consumable server ticket. This operation has no follow-up consume endpoint. The native client uses the fresh response immediately and never caches permission for later exits. The 60-second deadline applies to acting on that response; after it expires, validate again. Validate the returned PC/cafe against the linked device before closing.

## Error responses

```json
{"status":"error","code":"invalid_owner_pin"}
```

| HTTP | Code | Native client behavior |
| --- | --- | --- |
| 400 | invalid_json | Send JSON object |
| 400 | invalid_pin_format | Require PIN string with 4–6 ASCII digits |
| 400 | invalid_action | Use force_exit or admin_settings |
| 401 | token_required / invalid_session_token | Relink or recover active PC token |
| 401 | invalid_owner_pin | Keep kiosk running; permit another attempt within limits |
| 403 | kiosk_token_required | Dashboard JWTs cannot invoke this device endpoint |
| 429 | rate_limited | Wait; production response includes Retry-After: 60 |

At most 10 validation attempts per console per minute and 60 per IP per minute using the existing persistent kiosk limiter. Success and failure both count, and counters survive failed transactions. The limiter is shared with existing kiosk-protected operations. Requires the existing kiosk runtime migration/table `kiosk_rate_limits`; no new migration is introduced.

A revoked/unlinked PC token fails before owner validation. Connection failures, HTTP errors or malformed responses never authorize exit. Do not reveal whether another cafe uses a submitted PIN.

## Native integration sequence

1. Owner opens an intentional “Exit kiosk” control; do not interrupt gameplay with a spontaneous prompt.
2. Show masked PIN input. Never log the PIN, request JSON or Authorization header. Clear the input after completion/cancel.
3. Submit HTTPS POST using the active linked-PC token.
4. Require HTTP 200, authorized true, action force_exit, matching PC/cafe, and unexpired authorization.
5. Stop the kiosk application's watchdog/relaunch behavior according to the native team's exit implementation, then close the kiosk application. The backend cannot implement or guarantee the Windows process shutdown.
6. Show a passive error and keep kiosk protections running on failed validation. Do not create an offline PIN cache or use a saved success response.

No WebSocket emit is required or implemented for owner PIN validation. Do not invent a force_exit socket event or broadcast the PIN/response to other PCs.

## Gaming session and money

**This API does not stop play, release slots, unlink the PC, waive money or settle debt.** Closing the kiosk application and ending a gaming session are separate actions. If the owner also chooses to stop an enrolled session, call the existing authenticated `/api/kiosk/session/stop` with its runtime_id, mode now and idempotency key, obtain confirmation, then exit. Use the final settlement protocol for outstanding charges. Never treat force-exit permission as payment confirmation.

Exiting stops heartbeat unless another native component continues it. For enrolled sessions, the server refuses further extensions after the existing offline threshold and preserves only already authorized play through its reserved boundary. Warn the owner about that consequence before intentional exit.

## Curl example

```bash
curl --request POST "$DASHBOARD_BASE_URL/api/kiosk/owner-pin/validate" \
  --header "Authorization: Bearer $PC_LINK_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{"pin":"4837","action":"force_exit"}'
```

Example PIN is fictional. Avoid entering a real PIN into shared shell history or debug recordings. Native production code should use a masked UI and an HTTP client.

## Backend verification

Tests cover correct owner authorization, wrong-cafe PIN rejection, missing link token, unsupported action, rate limiting, no PIN in response, private cache headers, and no console release/session side effect. Existing kiosk transaction tests are also run. Real Windows exit/watchdog behavior must be verified by the kiosk team after service deployment.

## Admin settings authorization (9 October 2026)

Use the same endpoint and active PC link token, with this body:

```json
{"pin":"4837","action":"admin_settings"}
```

Success has the same schema above, with `action:"admin_settings"`. Only open the native admin settings after a fresh HTTP 200 with authorized true, matching PC/cafe and the requested action. The 60-second response deadline authorizes entry, not an indefinite admin session. Settings panel timeout/lock-on-close must be implemented by the native kiosk team. Validate again when reopening it. An admin_settings response does not authorize force_exit, and a force_exit response does not authorize settings entry.

This validation does not grant dashboard API permissions, change device configuration on the server, or replace authentication/authorization for other backend endpoints. There is no offline permission cache or WebSocket validation action. Both supported actions share the existing rate limiter.
