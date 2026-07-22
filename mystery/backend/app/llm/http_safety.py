"""Shared HTTP opener for requests to a client-supplied LLM endpoint.

`/api/llm-settings/*` and every real chat-completion call take a
user-supplied base_url and make the SERVER issue an HTTP request to it.
`_reject_ssrf_target` in main.py only validates the host the caller
literally supplied — with urllib's default opener (which auto-follows
redirects), a base_url on an allowed host can 307/302 the request anywhere,
including a blocked/metadata address, and the response is reflected straight
back to the caller. A legitimate self-hosted OpenAI-compatible endpoint has
no reason to redirect a chat-completions/models/tags request, so refusing to
follow any redirect closes that off without needing to re-validate a
resolved IP on every hop.
"""

import urllib.request


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def urlopen_no_redirect(req_or_url, timeout=None):
    """Like urllib.request.urlopen, but raises HTTPError instead of
    following a 3xx redirect."""
    return _opener.open(req_or_url, timeout=timeout)
