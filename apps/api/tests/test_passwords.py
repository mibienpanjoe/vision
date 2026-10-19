from app.core.passwords import hash_password, verify_password


def test_password_hashes_are_salted_and_do_not_accept_wrong_input():
    first = hash_password("a test passphrase, not a credential")
    second = hash_password("a test passphrase, not a credential")
    assert first != second
    assert "passphrase" not in first
    assert verify_password("a test passphrase, not a credential", first)
    assert not verify_password("different test password", first)
    assert not verify_password("different test password", "malformed")
