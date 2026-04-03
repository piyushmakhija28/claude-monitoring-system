"""policy_framework/result.py - PolicyResult named tuple.

Standard return type for policy checks across the hook system.

Windows-safe: ASCII only, no Unicode characters.
"""

from collections import namedtuple

PolicyResult = namedtuple("PolicyResult", ["blocked", "message", "severity"], defaults=[False, "", "info"])
