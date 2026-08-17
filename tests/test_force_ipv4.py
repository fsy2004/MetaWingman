import socket
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "metawingman/scripts"))

from metawingman_core import network_security  # noqa: E402
from metawingman_core.network_security import force_ipv4_resolution  # noqa: E402


class ForceIpv4Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.original = socket.getaddrinfo
        self.original_internal = network_security._original_getaddrinfo

    def tearDown(self) -> None:
        socket.getaddrinfo = self.original
        network_security._original_getaddrinfo = self.original_internal

    def test_force_ipv4_filters_resolution_to_af_inet(self) -> None:
        network_security._original_getaddrinfo = lambda host, port, family=0, type=0, proto=0, flags=0: [
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2607:f220:41e:4290::110", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("193.62.193.80", 443)),
        ]
        force_ipv4_resolution()
        resolved = socket.getaddrinfo("example.org", 443)
        self.assertTrue(resolved)
        self.assertTrue(all(entry[0] == socket.AF_INET for entry in resolved))
        self.assertEqual(resolved[0][4][0], "193.62.193.80")


if __name__ == "__main__":
    unittest.main()
