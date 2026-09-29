"""One way out to the network, without redirects.

urllib follows redirects by default and copies every header to the new address, including
the ones carrying the user's keys (KeyId, Authorization), even to another host. The
databases we query never need a redirect: one is refused, so a key can only ever reach the
address written in the code.
"""
import urllib.request


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None          # urllib then raises HTTPError with the 3xx code


_opener = urllib.request.build_opener(_NoRedirect)


def urlopen(req, timeout):
    return _opener.open(req, timeout=timeout)
