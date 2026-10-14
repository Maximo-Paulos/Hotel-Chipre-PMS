"""Hash de secretos de corta vida con HMAC-SHA256 (hallazgo N8 del informe).

Hoy `hash_password` (Argon2id, ~59 ms de CPU) protege códigos de 6 dígitos, códigos de
recuperación MFA y tokens de aprobación temporal. Argon2 sirve contra el descifrado *offline*
de contraseñas elegidas por personas; un código de 6 dígitos solo tiene 10^6 valores, así que
lo que protege un volcado de la base es un secreto del servidor (*pepper*), no el costo del hash.
HMAC con un pepper que NO está en la base da la misma garantía por < 0,1 ms.

Compatibilidad: los hashes nuevos llevan el prefijo ``hmac-sha256$``; los existentes (Argon2,
prefijo ``$argon2``) se siguen verificando con `verify_password` hasta que venzan (15 min para
códigos de correo) o se usen (códigos de recuperación: re-hashear al consumirlos).

Uso:  python docs/audits/perf-2026-10-13/solutions/otp_hmac.py   (autoprueba)
"""
from __future__ import annotations

import hashlib
import hmac
import time

PREFIX = "hmac-sha256$"


def derive_pepper(integrations_encryption_key: str) -> bytes:
    """Deriva el pepper de la clave Fernet existente: no agrega una variable de entorno nueva."""
    return hashlib.sha256(b"otp-pepper:v1:" + integrations_encryption_key.encode()).digest()


def hash_code(pepper: bytes, purpose: str, subject: str, code: str) -> str:
    # El propósito y el sujeto van dentro del mensaje: un código de "reset" no vale para "verify"
    # ni para otro correo, aunque coincida el valor.
    message = f"{purpose}\x1f{subject.strip().lower()}\x1f{code}".encode()
    return PREFIX + hmac.new(pepper, message, hashlib.sha256).hexdigest()


def verify_code(pepper: bytes, purpose: str, subject: str, code: str, stored: str, legacy_verify=None) -> bool:
    if stored.startswith(PREFIX):
        return hmac.compare_digest(hash_code(pepper, purpose, subject, code), stored)
    # Hash heredado (Argon2): delegar en la verificación vigente durante la transición.
    return bool(legacy_verify and legacy_verify(code, stored))


if __name__ == "__main__":
    pepper = derive_pepper("clave-fernet-de-prueba")
    h = hash_code(pepper, "password_reset", "Ana@Hotel.com", "483920")
    assert verify_code(pepper, "password_reset", "ana@hotel.com ", "483920", h)
    assert not verify_code(pepper, "password_reset", "ana@hotel.com", "483921", h)
    assert not verify_code(pepper, "email_verify", "ana@hotel.com", "483920", h), "el propósito debe importar"
    assert not verify_code(pepper, "password_reset", "otra@hotel.com", "483920", h), "el sujeto debe importar"
    assert not verify_code(derive_pepper("otra-clave"), "password_reset", "ana@hotel.com", "483920", h)
    assert verify_code(pepper, "x", "y", "123456", "$argon2id$legacy", legacy_verify=lambda c, s: c == "123456")
    t = time.perf_counter()
    for _ in range(20000):
        verify_code(pepper, "password_reset", "ana@hotel.com", "483920", h)
    print(f"ok · {(time.perf_counter() - t) / 20000 * 1e6:.1f} µs por verificación (Argon2id medido: ~59.000 µs)")
