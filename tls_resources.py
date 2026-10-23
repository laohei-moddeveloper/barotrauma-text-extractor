"""Discover resources required by the actual build interpreter, without weakening TLS."""
from pathlib import Path
import ssl

POLICY_NAME = 'codex-rejected-cas.pem'


def build_tls_policy(ssl_module=ssl):
    source = Path(ssl_module.__file__)
    policy = source.with_name(POLICY_NAME)
    if policy.is_file():
        return policy
    # A normal CPython installation does not require this additional resource.
    # A patched interpreter that explicitly reads it must not silently build a
    # broken EXE just because its resource has disappeared.
    if source.is_file() and POLICY_NAME in source.read_text(encoding='utf-8'):
        raise RuntimeError('Build interpreter requires a missing TLS policy resource: ' + POLICY_NAME)
    return None


if __name__ == '__main__':
    policy = build_tls_policy()
    # No policy contents, personal paths or credentials are emitted into logs.
    print(str(policy) if policy else '')
