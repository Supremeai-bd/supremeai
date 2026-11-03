from unittest.mock import MagicMock, patch

import pytest

from tools.social.email_agent import EmailAgent


def test_gmail_oauth_fails_closed_instead_of_fake_success():
    """গ্যাপ ফিক্স রিগ্রেশন টেস্ট: Gmail OAuth কখনো fake True রিটার্ন করবে না,
    কারণ এখনো কোনো real consent/redirect ফ্লো ওয়্যার করা হয়নি।"""
    agent = EmailAgent()
    with pytest.raises(NotImplementedError):
        agent.connect_gmail_oauth("gmail", ["scope1"])
    assert agent.connected is False


def test_connect_imap_verifies_real_login_and_rejects_bad_credentials():
    """imaplib.IMAP4_SSL.login ব্যর্থ হলে connect_imap() অবশ্যই False রিটার্ন করবে এবং
    connected ফ্ল্যাগ True হবে না — আগে এখানে যাচাই ছাড়াই সবসময় True রিটার্ন হতো।"""
    import imaplib

    agent = EmailAgent()
    mock_imap = MagicMock()
    # বাংলা মন্তব্য: imap.login() এরর রেইজ করার জন্য সঠিক imaplib.IMAP4.error টাইপ ব্যবহার করা হলো।
    mock_imap.login.side_effect = imaplib.IMAP4.error("auth failed")
    mock_imap.__enter__.return_value = mock_imap
    mock_imap.__exit__.return_value = False

    with patch("tools.social.email_agent.imaplib.IMAP4_SSL", return_value=mock_imap):
        result = agent.connect_imap("imap.example.com", 993, "test@example.com", "wrong-password")

    assert result is False
    assert agent.connected is False


def test_connect_imap_success_stores_encrypted_credentials():
    # বাংলা মন্তব্য: credential এনক্রিপশন টেস্ট করার জন্য পরিবেশ ভ্যারিয়েবলে টেস্ট এনক্রিপশন কী সেট করা হলো।
    with patch.dict(
        "os.environ",
        {"SUPREMEAI_CREDENTIAL_ENC_KEY": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="},
    ):
        agent = EmailAgent()
        mock_imap = MagicMock()
        mock_imap.__enter__.return_value = mock_imap
        mock_imap.__exit__.return_value = False

        with patch("tools.social.email_agent.imaplib.IMAP4_SSL", return_value=mock_imap):
            result = agent.connect_imap(
                "imap.example.com", 993, "test@example.com", "correct-password"
            )

        assert result is True
        assert agent.connected is True
        assert agent.auth_method == "imap"
        # প্লেইনটেক্সট পাসওয়ার্ড কখনো সরাসরি সংরক্ষিত হবে না — শুধু এনক্রিপ্টেড ciphertext
        assert agent._imap_config["ciphertext"] != "correct-password"


def test_otp_extraction():
    agent = EmailAgent()
    body = "Your verification code is 482910."
    assert agent.extract_otp(body) == "482910"

    body_no_otp = "Welcome to SupremeAI!"
    assert agent.extract_otp(body_no_otp) == ""


def test_signup_flow_without_connection_fails_honestly():
    """গ্যাপ ফিক্স রিগ্রেশন টেস্ট: কানেকশন ছাড়া signup_flow() আর fake OTP দিয়ে
    'success' দাবি করবে না — স্পষ্টভাবে ব্যর্থ হবে।"""
    agent = EmailAgent()
    res = agent.signup_flow("example.com")
    assert res["status"] == "failed"
    assert "otp" not in res


def test_receive_otp_without_live_connection_returns_empty():
    agent = EmailAgent()
    assert agent.receive_otp("example.com") == ""
