from tests.live.seed_test_accounts import parse_account, parse_test_accounts


def _account1_env():
    return {
        "NARUON_TEST_EMAIL1": "user@example.com",
        "NARUON_TEST_PASSWORD1": "s3cret",
        "NARUON_TEST_IMAP_ADDR1": "imap.example.com",
        "NARUON_TEST_POP3_ADDR1": "pop3.example.com",
        "NARUON_TEST_SMTP_ADDR1": "smtp.example.com",
        "NARUON_TEST_CALDAV_ADDR1": "https://dav.example.com/caldav/",
        "NARUON_TEST_CARDDAV_ADDR1": "https://dav.example.com/carddav/",
    }


def test_parses_single_account_with_inferred_ports():
    accounts = parse_test_accounts(_account1_env())
    assert len(accounts) == 1
    account = accounts[0]
    assert account.index == 1
    assert account.email == "user@example.com"
    assert account.password == "s3cret"
    assert account.imap.host == "imap.example.com"
    assert account.imap.port == 993
    assert account.pop3.port == 995
    assert account.smtp.port == 587
    assert account.caldav_url == "https://dav.example.com/caldav"
    assert account.carddav_url == "https://dav.example.com/carddav"
    assert account.carddav_needs_discovery is False
    assert account.user_id == "naruon-test-1"


def test_explicit_ports_are_preserved():
    env = _account1_env()
    env["NARUON_TEST_IMAP_ADDR1"] = "imap.example.com:1993"
    env["NARUON_TEST_SMTP_ADDR1"] = "smtp.example.com:2525"
    account = parse_test_accounts(env)[0]
    assert account.imap.port == 1993
    assert account.smtp.port == 2525


def test_blank_carddav_triggers_discovery():
    env = _account1_env()
    env["NARUON_TEST_CARDDAV_ADDR1"] = "   "
    account = parse_test_accounts(env)[0]
    assert account.carddav_url is None
    assert account.carddav_needs_discovery is True
    assert "carddav" in account.configured_protocols


def test_missing_carddav_key_triggers_discovery():
    env = _account1_env()
    del env["NARUON_TEST_CARDDAV_ADDR1"]
    account = parse_test_accounts(env)[0]
    assert account.carddav_needs_discovery is True


def test_bare_host_caldav_becomes_https_origin():
    env = _account1_env()
    env["NARUON_TEST_CALDAV_ADDR1"] = "dav.example.com"
    account = parse_test_accounts(env)[0]
    assert account.caldav_url == "https://dav.example.com"


def test_n_account_native_iteration_stops_at_first_gap():
    env = _account1_env()
    # Account 2 fully configured.
    env.update(
        {
            "NARUON_TEST_EMAIL2": "second@example.com",
            "NARUON_TEST_PASSWORD2": "pw2",
            "NARUON_TEST_IMAP_ADDR2": "imap2.example.com",
        }
    )
    accounts = parse_test_accounts(env)
    assert [a.index for a in accounts] == [1, 2]
    assert accounts[1].email == "second@example.com"
    assert accounts[1].imap.port == 993
    # No SMTP configured for account 2 -> endpoint is None.
    assert accounts[1].smtp is None


def test_no_accounts_returns_empty():
    assert parse_test_accounts({}) == []


def test_missing_email_returns_none_for_that_index():
    env = {"NARUON_TEST_PASSWORD1": "pw"}
    assert parse_account(env, 1) is None


def test_partial_mail_only_account():
    env = {
        "NARUON_TEST_EMAIL1": "user@example.com",
        "NARUON_TEST_PASSWORD1": "pw",
        "NARUON_TEST_IMAP_ADDR1": "imap.example.com",
    }
    account = parse_test_accounts(env)[0]
    assert account.imap is not None
    assert account.pop3 is None
    assert account.smtp is None
    assert account.caldav_url is None
    # No explicit CardDAV address -> discovery flagged.
    assert account.carddav_needs_discovery is True
    assert sorted(account.configured_protocols) == ["carddav", "imap"]
