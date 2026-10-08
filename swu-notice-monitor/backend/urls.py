"""URL syntax, page normalization and scheme-independent article identity."""
import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit, unquote

ASSET = re.compile(r'\.(?:pdf|docx?|xlsx?|pptx?|odt|ods|csv|zip|rar|7z|jpe?g|png|gif|svg|webp|mp4|mp3|css|js)$', re.I)


def validate_url_syntax(url):
    if not isinstance(url, str) or re.search(r'[\s<>"\x00-\x1f\x7f]', url):
        raise ValueError('链接包含空白、控制字符或 HTML 错误提示')
    p = urlsplit(url)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username is not None or p.password is not None:
        raise ValueError('链接必须是无认证信息的 HTTP/HTTPS URL')
    if p.port not in (None, 80 if p.scheme == 'http' else 443):
        raise ValueError('链接只支持标准 HTTP/HTTPS 端口')
    return p


def canonical_url(url):
    p = validate_url_syntax(url)
    host = p.hostname.lower()
    if ':' in host:
        host = f'[{host}]'
    query = urlencode(sorted((k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                             if not k.lower().startswith('utm_')))
    return urlunsplit((p.scheme.lower(), host, p.path or '/', query, ''))


def article_identity(url):
    p = urlsplit(canonical_url(url))
    return urlunsplit(('https', p.netloc, p.path, p.query, ''))


def is_attachment(url):
    try:
        p = urlsplit(url)
    except ValueError:
        return False
    return bool(ASSET.search(unquote(p.path)) or re.search(r'/(?:download|__local)(?:/|\.)', p.path, re.I)
                or any(ASSET.search(unquote(v)) for k, v in parse_qsl(p.query)
                       if k.lower() in ('file', 'filename', 'path', 'attachment')))


def resolve_page_link(base, href):
    if not href or href.startswith('#') or re.search(r'[\s<>"\x00-\x1f\x7f]', href):
        return None
    try:
        url = canonical_url(urljoin(base, href))
        p, origin = urlsplit(url), urlsplit(base)
        if p.hostname != origin.hostname or is_attachment(url):
            return None
        if origin.scheme == 'https' and p.scheme == 'http':
            url = urlunsplit(('https', p.netloc, p.path, p.query, ''))
        return url
    except ValueError:
        return None
