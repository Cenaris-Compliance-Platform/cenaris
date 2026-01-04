import os
import ssl

try:
    from requests.adapters import HTTPAdapter
except Exception:  # pragma: no cover
    HTTPAdapter = object  # type: ignore


class TLSv12HttpAdapter(HTTPAdapter):
    """Force TLS 1.2 for connections.

    Some networks/middleboxes (proxy, antivirus HTTPS scanning, TLS inspection)
    break TLS 1.3 handshakes and can cause SSLEOFError/UNEXPECTED_EOF.
    For Google OAuth endpoints, forcing TLS 1.2 is a pragmatic workaround.
    """

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        ctx = ssl.create_default_context()
        # Force TLSv1.2 only
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.maximum_version = ssl.TLSVersion.TLSv1_2
        pool_kwargs["ssl_context"] = ctx
        return super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)


def apply_google_tls12_workaround(remote_app) -> None:
    """Mount a TLS1.2-only adapter onto Authlib's requests session.

    Enabled by default (OAUTH_FORCE_TLS12=1). Set OAUTH_FORCE_TLS12=0 to disable.
    """
    flag = (os.environ.get("OAUTH_FORCE_TLS12") or "1").strip().lower()
    if flag in {"0", "false", "no", "off"}:
        return

    sess = getattr(remote_app, "session", None)
    if sess is None or not hasattr(sess, "mount"):
        return

    adapter = TLSv12HttpAdapter()

    # Only mount for Google endpoints (least invasive)
    sess.mount("https://accounts.google.com/", adapter)
    sess.mount("https://oauth2.googleapis.com/", adapter)
    sess.mount("https://www.googleapis.com/", adapter)
