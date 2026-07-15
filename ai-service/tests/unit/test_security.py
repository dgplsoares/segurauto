"""Fase 4a — primitivos de segurança (DEC-ORB-037), sem infra."""
from app.shared.security import gen_otp, new_session_token, otp_hash, otp_matches, token_pk


def test_gen_otp_is_5_digits():
    for _ in range(30):
        code = gen_otp(5)
        assert len(code) == 5 and code.isdigit()


def test_otp_hash_deterministic_and_scoped_to_email():
    h = otp_hash("ana@example.com", "12345")
    assert otp_hash("ana@example.com", "12345") == h  # determinístico (mesmo pepper)
    assert otp_matches("ana@example.com", "12345", h)
    assert not otp_matches("ana@example.com", "54321", h)      # código errado
    assert not otp_matches("outro@example.com", "12345", h)    # e-mail faz parte do HMAC


def test_session_token_opaque_and_hashed():
    t1, t2 = new_session_token(), new_session_token()
    assert t1 != t2 and len(t1) > 20
    assert len(token_pk(t1)) == 64  # sha256 hex — guardado no banco, nunca o token cru
    assert token_pk(t1) == token_pk(t1)
