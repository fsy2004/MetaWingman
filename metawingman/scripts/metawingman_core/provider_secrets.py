"""Resolve provider secrets from environment variables or the Windows Credential Manager."""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes


DEEPSEEK_CREDENTIAL_TARGET = "MetaWingman/DeepSeek"
CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2


class ProviderSecretError(ValueError):
    """Raised when a provider secret cannot be stored or resolved safely."""


if sys.platform == "win32":
    class _CredentialW(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
            ("LastWritten", wintypes.FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]


def _advapi32() -> ctypes.WinDLL:
    if sys.platform != "win32":
        raise ProviderSecretError("Windows Credential Manager is unavailable on this platform")
    library = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
    library.CredWriteW.argtypes = [ctypes.POINTER(_CredentialW), wintypes.DWORD]
    library.CredWriteW.restype = wintypes.BOOL
    library.CredReadW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.POINTER(_CredentialW)),
    ]
    library.CredReadW.restype = wintypes.BOOL
    library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    library.CredDeleteW.restype = wintypes.BOOL
    library.CredFree.argtypes = [ctypes.c_void_p]
    library.CredFree.restype = None
    return library


def store_windows_credential(target: str, secret: str) -> None:
    """Store a UTF-16 generic credential without placing the secret in a project file."""
    if not target.strip() or not secret.strip():
        raise ProviderSecretError("credential target and secret must be non-empty")
    blob = secret.encode("utf-16-le")
    if len(blob) > 2560:
        raise ProviderSecretError("credential is too large for Windows Credential Manager")
    buffer = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
    credential = _CredentialW()
    credential.Type = CRED_TYPE_GENERIC
    credential.TargetName = target
    credential.CredentialBlobSize = len(blob)
    credential.CredentialBlob = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
    credential.Persist = CRED_PERSIST_LOCAL_MACHINE
    credential.UserName = "api-key"
    library = _advapi32()
    if not library.CredWriteW(ctypes.byref(credential), 0):
        error = ctypes.get_last_error()
        raise ProviderSecretError(f"CredWriteW failed with Windows error {error}")


def read_windows_credential(target: str) -> str | None:
    """Read a generic credential; return None when the target does not exist."""
    library = _advapi32()
    pointer = ctypes.POINTER(_CredentialW)()
    if not library.CredReadW(target, CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)):
        error = ctypes.get_last_error()
        if error == 1168:
            return None
        raise ProviderSecretError(f"CredReadW failed with Windows error {error}")
    try:
        credential = pointer.contents
        blob = ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
        return blob.decode("utf-16-le")
    finally:
        library.CredFree(pointer)


def delete_windows_credential(target: str) -> bool:
    """Delete a generic credential; return False when it was already absent."""
    library = _advapi32()
    if library.CredDeleteW(target, CRED_TYPE_GENERIC, 0):
        return True
    error = ctypes.get_last_error()
    if error == 1168:
        return False
    raise ProviderSecretError(f"CredDeleteW failed with Windows error {error}")


def resolve_provider_secret(
    environment_variable: str,
    credential_target: str | None = None,
) -> tuple[str, str]:
    """Return a provider secret and a non-secret description of its source."""
    value = os.environ.get(environment_variable, "").strip()
    if value:
        return value, f"environment:{environment_variable}"
    if credential_target and sys.platform == "win32":
        value = read_windows_credential(credential_target)
        if value:
            return value, f"windows_credential:{credential_target}"
    raise ProviderSecretError(
        f"provider secret unavailable; set {environment_variable} or configure {credential_target}"
    )
