"""Cloudflare Worker entry point for the in-progress hosting migration.

This scaffold deliberately does not acknowledge Telegram updates yet. The
existing aiogram handlers still run through long polling, and acknowledging an
update before porting those handlers would silently discard user messages.
"""

from urllib.parse import urlparse

from workers import Response, WorkerEntrypoint

from cloudflare_core import verify_webhook_secret


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        path = urlparse(request.url).path

        if request.method == "GET" and path == "/health":
            return Response.json({"status": "scaffold_only"})

        if request.method == "POST" and path == "/telegram/webhook":
            expected = getattr(self.env, "TELEGRAM_WEBHOOK_SECRET", "")
            provided = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if not verify_webhook_secret(expected, provided):
                return Response("Unauthorized", status=401)

            # Keep Telegram retrying until command/callback/inline handlers are
            # fully migrated. Never return success for an update we discard.
            return Response.json(
                {"status": "not_ready", "detail": "Telegram handlers are not migrated"},
                {"status": 503},
            )

        return Response("Not found", status=404)
