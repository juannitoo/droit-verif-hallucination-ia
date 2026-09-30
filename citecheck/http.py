"""One way out to the network, without redirects, and with a ceiling on what comes back.

urllib follows redirects by default and copies every header to the new address, including
the ones carrying the user's keys (KeyId, Authorization), even to another host. The
databases we query never need a redirect: one is refused, so a key can only ever reach the
address written in the code.

A response is read up to MAX_RESPONSE bytes, whatever the caller asks for: a database in
trouble, or a proxy answering in its place, cannot fill the memory with one reply (audit of
30/09/2026). Past that, reading raises TooLarge, which every caller already turns into "the
database did not answer", never into a verdict.
"""
import urllib.request

MAX_RESPONSE = 64 * 1024 * 1024     # far above any real reply, even a whole collective
                                    # agreement from Légifrance


class TooLarge(Exception):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None          # urllib then raises HTTPError with the 3xx code


class _Capped:
    """The response, with read() unable to return more than `left` bytes in all."""

    def __init__(self, response, left):
        self._r, self._left = response, left

    def read(self, n=-1):
        want = self._left + 1 if n is None or n < 0 else min(n, self._left + 1)
        data = self._r.read(want)
        self._left -= len(data)
        if self._left < 0:
            raise TooLarge(f"réponse de plus de {MAX_RESPONSE // (1024 * 1024)} Mo")
        return data

    def __getattr__(self, name):          # headers, status, getheader...
        return getattr(self._r, name)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._r.close()


_opener = urllib.request.build_opener(_NoRedirect)


def urlopen(req, timeout):
    return _Capped(_opener.open(req, timeout=timeout), MAX_RESPONSE)
