import pytest

from api.porter.objections import (
    PorterObjectionHandler,
    PorterObjectionType,
    classify_porter_objection,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Not interested.", PorterObjectionType.NOT_INTERESTED),
        ("Call me later tomorrow.", PorterObjectionType.CALL_ME_LATER),
        ("Send me information.", PorterObjectionType.SEND_INFO),
        ("We already have funding.", PorterObjectionType.ALREADY_HAVE_FUNDING),
        ("What are your rates?", PorterObjectionType.RATES),
        ("How fast can you fund?", PorterObjectionType.FUNDING_SPEED),
        ("Is this a loan?", PorterObjectionType.IS_THIS_A_LOAN),
        ("Is this factoring?", PorterObjectionType.IS_THIS_FACTORING),
        ("Who are you?", PorterObjectionType.WHO_ARE_YOU),
        ("How did you get my number?", PorterObjectionType.HOW_GOT_NUMBER),
        ("Can you email me?", PorterObjectionType.CAN_EMAIL_ME),
        ("Do not call me again.", PorterObjectionType.ANGRY_RESPONSE),
        ("She is not available.", PorterObjectionType.GATEKEEPER),
        ("Please leave a message after the tone.", PorterObjectionType.VOICEMAIL),
    ],
)
def test_each_required_objection_maps_to_expected_handler(text, expected):
    assert classify_porter_objection(text) == expected


def test_rate_question_remains_safe():
    result = PorterObjectionHandler().handle("What are your rates?")

    assert result.response_text == "Rates depend on qualification and review."
    assert "%" not in result.response_text


def test_funding_speed_answer_is_conservative():
    result = PorterObjectionHandler().handle("How fast can you fund?")

    assert "depends" in result.response_text.lower()
    assert "guarantee" not in result.response_text.lower()


def test_angry_response_terminates_respectfully():
    result = PorterObjectionHandler().handle("Do not call me again.")

    assert result.should_end_conversation is True
    assert result.disposition.value == "not_interested"


def test_gatekeeper_does_not_disclose_sensitive_lead_data():
    result = PorterObjectionHandler().handle("She is not available.")

    assert result.disposition.value == "gatekeeper"
    assert "funding need" not in result.response_text.lower()
    assert "lead score" not in result.response_text.lower()


def test_voicemail_does_not_claim_approval_or_rates():
    result = PorterObjectionHandler().handle("Leave a message after the tone.")

    assert result.disposition.value == "voicemail"
    assert "approved" not in result.response_text.lower()
    assert "rate" not in result.response_text.lower()


def test_send_info_does_not_send_email():
    result = PorterObjectionHandler().handle("Can you email me?")

    assert result.disposition.value == "send_info"
    assert result.send_info_requested is True
    assert "will not send email" in result.response_text.lower()
