from urllib.parse import urljoin, urlencode


def build_primo_public_url(host, path='primo-explore/fulldisplay', params=None, use_https=True):
    """
    Build a public Primo URL.

    Args:
        host (str): Hostname or full origin, e.g. "library.example.edu" or "https://library.example.edu"
        path (str): Path after the host (default: 'primo-explore/fulldisplay').
        params (dict): Query parameters to include (e.g. {'docid': 'TN_lbor_i12345', 'vid': '01CARLI_US'}).
        use_https (bool): If True and `host` lacks a scheme, add 'https://'.

    Returns:
        str: Full public URL for the Primo resource.
    """
    if not host:
        raise ValueError("host is required")
    host = host.strip()
    if not host.startswith('http://') and not host.startswith('https://'):
        scheme = 'https://' if use_https else 'http://'
        host = scheme + host
    base = host.rstrip('/') + '/'
    url = urljoin(base, path.lstrip('/'))
    if params:
        return url + '?' + urlencode(params, doseq=True)
    return url


if __name__ == '__main__':
    host = 'library.example.edu'
    params = {
        'docid': 'TN_lbor_i12345',
        'vid': '01CARLI_US',
        'tab': 'default_tab'
    }
    print(build_primo_public_url(host, params=params))
from urllib.parse import urljoin, urlencode


def build_primo_public_url(host, path='primo-explore/fulldisplay', params=None, use_https=True):
    """
    Build a public Primo URL.

    Args:
        host (str): Hostname or full origin, e.g. "library.example.edu" or "https://library.example.edu"
        path (str): Path after the host (default: 'primo-explore/fulldisplay').
        params (dict): Query parameters to include (e.g. {'docid': 'TN_lbor_i12345', 'vid': '01CARLI_US'}).
        use_https (bool): If True and `host` lacks a scheme, add 'https://'.

    Returns:
        str: Full public URL for the Primo resource.
    """
    if not host:
        raise ValueError("host is required")
    host = host.strip()
    if not host.startswith('http://') and not host.startswith('https://'):
        scheme = 'https://' if use_https else 'http://'
        host = scheme + host
    base = host.rstrip('/') + '/'
    url = urljoin(base, path.lstrip('/'))
    if params:
        return url + '?' + urlencode(params, doseq=True)
    return url


if __name__ == '__main__':
    host = 'library.example.edu'
    params = {
        'docid': 'TN_lbor_i12345',
        'vid': '01CARLI_US',
        'tab': 'default_tab'
    }
    print(build_primo_public_url(host, params=params))
