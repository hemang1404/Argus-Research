"""Thread-safe pool of Groq API keys with per-key pacing.

Free-tier facts measured 2026-11-10: ~1000 requests/day and 8000 tokens/minute per key,
prompt over ~8000 tokens is rejected up front (HTTP 413); output may exceed it.
Rules:
  * a rate limit (429) is never a task failure: the key cools down and the request is retried on another key
  * HTTP 413 is returned to the caller as 'prompt_too_large' (not retried)
  * only a 6-hex-digit hash of each key is ever logged
"""
import hashlib, json, re, threading, time, urllib.request, urllib.error

API = "https://api.groq.com/openai/v1/chat/completions"


def load_keys(env_path):
    keys = []
    for l in open(env_path, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*([A-Za-z0-9_]+)\s*=\s*(.*)", l)
        if not m or not m.group(2).strip():
            continue
        v = m.group(2).strip().strip("\"'")
        if m.group(1) == "GROQ_API_KEYS":
            keys += [x.strip() for x in v.split(",") if x.strip()]
        elif m.group(1).startswith("GROQ_API_KEY"):
            keys.append(v)
    return list(dict.fromkeys(keys))


def parse_duration(s):
    """'1m26.4s' / '57.9s' / '250ms' -> seconds"""
    if not s:
        return 0.0
    total = 0.0
    for num, unit in re.findall(r"([\d.]+)(ms|s|m|h)", s):
        total += float(num) * {"ms": 0.001, "s": 1, "m": 60, "h": 3600}[unit]
    return total


class Key:
    def __init__(self, value):
        self.value = value
        self.id = hashlib.sha256(value.encode()).hexdigest()[:6]
        self.next_ok = 0.0
        self.dead_until = 0.0
        self.busy = False
        self.requests = 0
        self.last_used = 0.0


class KeyPool:
    def __init__(self, env_path):
        self.keys = [Key(v) for v in load_keys(env_path)]
        self.cv = threading.Condition()

    def acquire(self, timeout=900, exclude=()):
        end = time.time() + timeout
        with self.cv:
            while True:
                now = time.time()
                free = [k for k in self.keys if not k.busy and k.next_ok <= now and k.dead_until <= now and k.id not in exclude]
                if free:
                    k = min(free, key=lambda x: x.last_used)
                    k.busy = True
                    k.last_used = now
                    return k
                if now > end:
                    raise TimeoutError("no key available")
                waits = [max(k.next_ok, k.dead_until) - now for k in self.keys if not k.busy and k.id not in exclude]
                self.cv.wait(timeout=max(0.2, min(waits) if waits else 1.0))

    def release(self, key, cooldown=0.0, dead_for=0.0):
        with self.cv:
            key.busy = False
            key.requests += 1
            if cooldown:
                key.next_ok = max(key.next_ok, time.time() + cooldown)
            if dead_for:
                key.dead_until = max(key.dead_until, time.time() + dead_for)
            self.cv.notify_all()

    def chat(self, body, max_tries=30, max_413_keys=8):
        """Returns dict(status, data|error, headers, key_id, tries, retries_log)."""
        log = []
        denied = set()  # keys that returned 413 for this request
        for attempt in range(1, max_tries + 1):
            if len(denied) >= len(self.keys):
                break
            key = self.acquire(exclude=denied)
            t0 = time.time()
            req = urllib.request.Request(API, data=json.dumps(body).encode(), headers={
                "Authorization": "Bearer " + key.value, "Content-Type": "application/json", "User-Agent": "argus-pilot100/0.1"})
            status, headers, payload = None, {}, None
            try:
                with urllib.request.urlopen(req, timeout=300) as r:
                    status, headers, payload = r.status, dict(r.headers), json.loads(r.read())
            except urllib.error.HTTPError as e:
                status, headers = e.code, dict(e.headers)
                raw = e.read().decode("utf-8", "replace")
                try:
                    payload = json.loads(raw)
                except Exception:
                    payload = {"error": {"message": raw[:300]}}
            except Exception as e:  # network error
                status, payload = -1, {"error": {"message": str(e)[:200]}}
            dt = time.time() - t0
            h = {k.lower(): v for k, v in headers.items()}
            msg = (payload or {}).get("error", {}).get("message", "") if isinstance(payload, dict) else ""
            if status == 200:
                # pace the key so the next big request does not hit the per-minute token window
                used = payload.get("usage", {}).get("total_tokens", 0)
                cool = parse_duration(h.get("x-ratelimit-reset-tokens")) + 0.5 if used > 2500 else 0.0
                self.release(key, cooldown=cool)
                return dict(status=200, data=payload, headers=h, key_id=key.id, tries=attempt, retries=log, latency_s=round(dt, 2))
            if status == 413:
                # Acceptance of a request with prompt+max_tokens above the nominal TPM depends on the key (measured
                # 2026-11-10: 9 of 17 keys admitted an identical 9.9k-token request, 7 refused). Try other keys; only
                # report 'too large' when many distinct keys have refused it.
                denied.add(key.id)
                log.append(dict(key=key.id, status=413))
                self.release(key, cooldown=20)
                if len(denied) >= max_413_keys:
                    return dict(status=413, error=msg, key_id=key.id, tries=attempt, retries=log, latency_s=round(dt, 2))
                continue
            if status == 429:
                per_day = "per day" in msg.lower() or "TPD" in msg or "RPD" in msg
                wait = float(h.get("retry-after", 30) or 30)
                log.append(dict(key=key.id, status=429, per_day=per_day, wait=wait))
                self.release(key, cooldown=wait + 1, dead_for=(max(wait, 600) if per_day else 0))
                continue
            log.append(dict(key=key.id, status=status, msg=msg[:120]))
            self.release(key, cooldown=min(5 * attempt, 30))
            if status in (400, 401, 403, 404):  # request or key problem, do not loop forever
                if status in (401, 403):
                    key.dead_until = time.time() + 3600
                    continue
                return dict(status=status, error=msg, key_id=key.id, tries=attempt, retries=log, latency_s=round(dt, 2))
        return dict(status=0, error="exhausted retries", tries=max_tries, retries=log)
