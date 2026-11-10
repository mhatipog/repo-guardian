"""Private, finite-size MP3 relay over Repo Guardian issue comments.

The original audio never enters Git history. Caller-owned chunks are deleted
after the verified private release upload. Only the fixed, private web-operations
destination is supported. GitHub can retain backups beyond our control.
"""
import base64
import binascii
import hashlib
import re
import urllib.error
import urllib.parse
import urllib.request

MAX_BYTES = 8 * 1024 * 1024
MAX_CHUNKS = 240
MAX_ENCODED_CHUNK = 55000
SHA = re.compile(r"^[0-9a-f]{64}$")
CHUNK = re.compile(r"^RG_MEDIA_CHUNK ([1-9][0-9]*)/([1-9][0-9]*)\\n([A-Za-z0-9+/=\\r\\n]+)$")
BRANDS = frozenset(("gratistools",))
TAG = "social-audio-inputs"


class MediaRefused(Exception):
    pass


class MediaPending(Exception):
    pass


def validate(value, owner):
    if set(value) != {"version", "action", "repo", "brand", "sha256", "size_bytes", "chunks"}:
        raise MediaRefused("Unexpected media staging fields")
    if value["repo"] != owner + "/web-operations" or value["brand"] not in BRANDS:
        raise MediaRefused("Audio staging is limited to private web-operations/GratisTools")
    if not isinstance(value["sha256"], str) or not SHA.fullmatch(value["sha256"]):
        raise MediaRefused("Expected exact lowercase SHA-256 of the MP3")
    if type(value["size_bytes"]) is not int or not 1024 <= value["size_bytes"] <= MAX_BYTES:
        raise MediaRefused("Media size must be 1 KiB to 8 MiB")
    if type(value["chunks"]) is not int or not 1 <= value["chunks"] <= MAX_CHUNKS:
        raise MediaRefused("Media requires 1 to 240 private issue comments")
    return value


def assemble(value, comments, owner):
    parts, ids = {}, {}
    for comment in comments:
        body = comment.get("body") or ""
        if not body.startswith("RG_MEDIA_CHUNK "):
            continue
        if comment.get("user", {}).get("login", "").lower() != owner.lower():
            raise MediaRefused("A media chunk was authored by someone other than the owner")
        match = CHUNK.fullmatch(body)
        if not match:
            raise MediaRefused("Malformed base64 media comment")
        index, count, payload = match.groups()
        index, count = int(index), int(count)
        if count != value["chunks"] or index > count or index in parts or len(payload) > MAX_ENCODED_CHUNK:
            raise MediaRefused("Wrong, duplicate or oversized media chunk")
        if not isinstance(comment.get("id"), int):
            raise MediaRefused("Missing GitHub comment ID for deletion")
        parts[index] = payload
        ids[index] = comment["id"]
    if len(parts) != value["chunks"]:
        raise MediaPending("Media chunks are still arriving")
    result = bytearray()
    for i in range(1, value["chunks"] + 1):
        if i not in parts:
            raise MediaPending("Media chunks are still arriving")
        try:
            piece = base64.b64decode(parts[i], validate=True)
        except binascii.Error as e:
            raise MediaRefused("Invalid base64 media payload") from e
        result.extend(piece)
        if len(result) > MAX_BYTES:
            raise MediaRefused("Audio payload exceeds 8 MiB")
    data = bytes(result)
    if len(data) != value["size_bytes"] or hashlib.sha256(data).hexdigest() != value["sha256"]:
        raise MediaRefused("Staged bytes differ from SHA-256 or byte count")
    if not (data.startswith(b"ID3") or
            (len(data) > 2 and data[0] == 0xff and data[1] & 0xe0 == 0xe0)):
        raise MediaRefused("Staged content does not look like MPEG audio")
    return data, [ids[i] for i in range(1, value["chunks"] + 1)]


def binary_upload(token, repo, release_id, filename, data):
    # Fixed GitHub-owned upload host, no URL/host from an issue body.
    url = ("https://uploads.github.com/repos/" + repo + "/releases/" +
           str(release_id) + "/assets?name=" + urllib.parse.quote(filename, safe=""))
    request = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "Content-Type": "audio/mpeg",
                 "X-GitHub-Api-Version": "2022-11-28",
                 "User-Agent": "repo-guardian-media/1"})
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            import json
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        raise MediaRefused("GitHub audio upload failed: HTTP " + str(e.code)) from None


def stage(value, data, admin, token, owner, uploader=binary_upload):
    validate(value, owner)
    if not token:
        raise MediaRefused("Owner token missing for temporary private media upload")
    repo = value["repo"]
    before = admin("GET", "/repos/" + repo)
    if before.get("private") is not True or before.get("fork") or before.get("archived") or before.get("full_name", "").lower() != repo.lower():
        raise MediaRefused("Target identity is not the expected private, non-fork repository")
    release_path = "/repos/" + repo + "/releases"
    try:
        release = admin("GET", release_path + "/tags/" + TAG)
    except Exception as e:
        if "HTTP 404:" not in str(e):
            raise
        release = admin("POST", release_path, {
            "tag_name": TAG, "target_commitish": before.get("default_branch", "main"),
            "name": "Temporary social audio inputs",
            "body": "Private staging. Inputs are deleted once scheduled publications are confirmed.",
            "prerelease": True, "make_latest": "false"})
    if release.get("tag_name") != TAG or release.get("draft") or not isinstance(release.get("id"), int):
        raise MediaRefused("Unexpected private media release")
    filename = value["brand"] + "-" + value["sha256"] + ".mp3"
    assets = []
    for page in range(1, 11):
        batch = admin("GET", release_path + "/" + str(release["id"]) +
                      "/assets?per_page=100&page=" + str(page))
        if not isinstance(batch, list):
            raise MediaRefused("Cannot inspect release media assets")
        assets.extend(batch)
        if len(batch) < 100:
            break
    previous = [a for a in assets if a.get("name") == filename]
    if len(previous) > 1:
        raise MediaRefused("Duplicated audio assets in private release")
    asset = previous[0] if previous else uploader(token, repo, release["id"], filename, data)
    aid = asset.get("id")
    if type(aid) is not int:
        raise MediaRefused("Audio upload did not return an asset ID")
    verified = admin("GET", release_path + "/assets/" + str(aid))
    if verified.get("id") != aid or verified.get("name") != filename or verified.get("size") != len(data) or verified.get("state") != "uploaded":
        raise MediaRefused("GitHub release asset is not verified")
    return {"assetId": aid, "sha256": value["sha256"], "startSeconds": 0}


def verify_staged(value, staged, admin, owner):
    validate(value, owner)
    if (not isinstance(staged, dict) or type(staged.get("assetId")) is not int
            or staged.get("sha256") != value["sha256"]):
        raise MediaRefused("Staged checkpoint does not match issue command")
    asset = admin("GET", "/repos/" + value["repo"] + "/releases/assets/" + str(staged["assetId"]))
    if asset.get("id") != staged["assetId"] or asset.get("size") != value["size_bytes"] or asset.get("name") != value["brand"] + "-" + value["sha256"] + ".mp3":
        raise MediaRefused("Checkpoint media asset was altered or deleted")
    return staged
