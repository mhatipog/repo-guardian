# Private audio bridge via Repo Guardian

Repo Guardian's private issue controller can relay an MP3 that the standard ChatGPT GitHub connector cannot upload as a binary. It **never places the audio in Git commits or branches** and only accepts `mhatipog/web-operations` + `gratistools`.

The source is a private `RG:` issue plus owner-authored `RG_MEDIA_CHUNK` comments. On the OCI controller, chunks are reconstructed, SHA-256 checked, uploaded to the private GitHub `social-audio-inputs` release and the chunk comments are deleted. The controller reports `RG_DONE` with the `audioTrack` fields for the existing `social/calendar/*.json` format.

## Request schema

Create an issue in your **private** `mhatipog/repo-guardian-control` titled `RG: Stage GratisTools MP3` with exactly:

```json
{"version":1,"action":"stage_social_audio","repo":"mhatipog/web-operations","brand":"gratistools","sha256":"<64-character lowercase hex SHA256>","size_bytes":123456,"chunks":3}
```

The SHA, byte count and count of chunks must be actual values, not placeholders. Each comment is of the form:

```
RG_MEDIA_CHUNK 1/3
<base64 of first contiguous binary chunk>
```

The relay accepts 1–240 comments, each carrying at most 55,000 encoded characters, and total decoded audio at most 8 MiB. Order and author are verified. Comments that arrive later simply resume the issue; missing chunks do not cause failed publish attempts. The controller requires the *owner* as issue/comment author, not a bot.

Use 4-byte-aligned base64 boundaries: split the original bytes into chunks, encode **each individual chunk** as base64. Do not encode the full file first and then split in the middle of base64 quartets.

Once the owner-controlled upload has succeeded, the controller posts a small `RG_STAGED` checkpoint, deletes the original chunk comments and posts `RG_DONE` with a verified asset ID. Reconciliation is idempotent across restarts and chunk-deletion failures. Do not submit a calendar post until `RG_DONE` is present. The normal social scheduler subsequently posts the Reel and deletes the source MP3 and generated media once each planned platform has confirmed delivery.

## Safety and limitations

- No arbitrary URLs, URL fetches, shell commands, repo names, languages or public destinations are accepted from the request.
- No public GitHub release or content is created by the relay. The actual promotional post goes through the existing GratisTools social pipeline only.
- No media is sent to any third-party service beyond GitHub and the social networks.
- GitHub may retain deleted issue content in backups or audit systems. We can remove active comments/assets but cannot guarantee irreversible deletion from GitHub's infrastructure.
- The relay is an exceptional mechanism for when a binary-capable connector is unavailable. **The existing `stage.mjs` script is still simpler** for uploads made directly from the OCI runner or your own computer.
- Only the owner should authorize uploading and publishing media they have rights to use commercially.

## Publishing after staging

Copy the controller's `audioTrack` JSON into a usual GratisTools calendar entry:

```json
"audioTrack": {"assetId":123456,"sha256":"<actual digest>","startSeconds":0}
```

Use `format:"post+reel"` or another Reel-enabled format. Do not include generated voice/music in the same recipe. Existing scheduling, duplicates/receipts, retention and analytics continue unchanged.
