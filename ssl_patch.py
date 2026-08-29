"""SSL Certificate Store Patch for Windows.

Fixes OpenSSL `ssl.SSLError: [ASN1: NOT_ENOUGH_DATA]` error caused by corrupted
or incomplete certificates in the Windows Certificate Store when calling
`ssl.create_default_context()`.
"""
import ssl

try:
    import certifi
    _cafile = certifi.where()
except ImportError:
    _cafile = None

_orig_load_windows_store_certs = getattr(ssl.SSLContext, '_load_windows_store_certs', None)

def _safe_load_windows_store_certs(self, storename, purpose):
    """Safely load Windows store certs, skipping corrupted items or using certifi fallback."""
    try:
        if _orig_load_windows_store_certs:
            _orig_load_windows_store_certs(self, storename, purpose)
    except Exception:
        certs_loaded = False
        try:
            for store in ("ROOT", "CA"):
                for cert, encoding, trust in ssl.enum_certificates(store):
                    try:
                        self.load_verify_locations(cadata=cert)
                        certs_loaded = True
                    except Exception:
                        pass
        except Exception:
            pass
        if not certs_loaded and _cafile:
            try:
                self.load_verify_locations(cafile=_cafile)
            except Exception:
                pass

def apply_ssl_patch():
    """Apply the SSL patch if not already applied."""
    if _orig_load_windows_store_certs and ssl.SSLContext._load_windows_store_certs != _safe_load_windows_store_certs:
        ssl.SSLContext._load_windows_store_certs = _safe_load_windows_store_certs

# Auto-apply when module is imported
apply_ssl_patch()
