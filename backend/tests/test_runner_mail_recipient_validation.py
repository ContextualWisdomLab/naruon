import pytest

from runner.local_mail_adapters import LocalMailAccountConfig, LocalMailAdapters


@pytest.mark.asyncio
async def test_local_smtp_adapter_rejects_recipient_reinterpreted_by_message_parser(
    monkeypatch,
):
    async def fail_send_email(message_params, smtp_config):
        raise AssertionError("invalid recipient must fail before SMTP send")

    monkeypatch.setattr("runner.local_mail_adapters.send_email", fail_send_email)
    adapters = LocalMailAdapters(
        [
            LocalMailAccountConfig(
                account="mailbox-1",
                user_id="user-1",
                organization_id="org-1",
                smtp_server="smtp.example.com",
                smtp_port=587,
                smtp_username="sender@example.com",
                smtp_password="smtp-secret",
            )
        ]
    )

    result = await adapters.send_smtp(
        {
            "account": "mailbox-1",
            "to": "user@example.com> AUTH=<attacker@example.com",
            "subject": "Runner send",
            "body": "body",
        }
    )

    assert result == {
        "status": "error",
        "error": "invalid_payload",
        "error_code": "invalid_payload",
        "provider_write_executed": False,
    }


@pytest.mark.asyncio
async def test_local_smtp_adapter_normalizes_recipient_domain_before_send(monkeypatch):
    sent_recipients = []

    async def fake_send_email(message_params, smtp_config):
        sent_recipients.append(message_params.to_address)
        return {"status": "sent", "simulated": False}

    monkeypatch.setattr("runner.local_mail_adapters.send_email", fake_send_email)
    adapters = LocalMailAdapters(
        [
            LocalMailAccountConfig(
                account="mailbox-1",
                user_id="user-1",
                organization_id="org-1",
                smtp_server="smtp.example.com",
                smtp_port=587,
                smtp_username="sender@example.com",
                smtp_password="smtp-secret",
            )
        ]
    )

    result = await adapters.send_smtp(
        {
            "account": "mailbox-1",
            "to": "recipient@EXAMPLE.COM",
            "subject": "Runner send",
            "body": "body",
        }
    )

    assert result == {
        "status": "success",
        "provider_write_executed": True,
        "provider_status": "sent",
    }
    assert sent_recipients == ["recipient@example.com"]
