import base64
from unittest.mock import AsyncMock, patch

import httpx
import jwt
import pytest

from tools.sso_integrator import SSOIntegrator


class TestSSOIntegratorComprehensive:
    @pytest.fixture
    def saml_settings(self):
        return {
            "sp_entity_id": "https://supremeai.app/sp",
            "acs_url": "https://supremeai.app/acs",
            "sls_url": "https://supremeai.app/sls",
            "idp_entity_id": "https://idp.example.com",
            "idp_sso_url": "https://idp.example.com/sso",
            "idp_slo_url": "https://idp.example.com/slo",
            "oidc_domain": "auth.example.com",
            "oidc_tenant": "tenant-123",
            "oidc_client_id": "client_abc",
            "oidc_client_secret": "secret_xyz",
            "oidc_redirect_uri": "https://supremeai.app/oauth/callback",
        }

    @pytest.fixture
    def integrator(self, saml_settings):
        with patch.object(SSOIntegrator, "_load_onelogin", return_value=False):
            return SSOIntegrator(saml_settings)

    def test_init_and_properties(self, integrator):
        assert integrator.onelogin is False
        assert integrator.saml_settings["sp_entity_id"] == "https://supremeai.app/sp"

    def test_get_sso_and_logout_urls_fallback(self, integrator):
        assert integrator.get_sso_url() == "https://idp.example.com/sso"
        assert integrator.get_logout_url() == "https://idp.example.com/slo"

    def test_get_metadata_fallback(self, integrator):
        meta = integrator.get_metadata()
        assert meta["status"] == "fallback"
        assert meta["content_type"] == "application/xml"
        assert "EntityDescriptor" in meta["body"]
        assert "https://supremeai.app/sp" in meta["body"]

    def test_role_mapping(self, integrator):
        assert integrator.map_roles(["Admin"]) == ["owner"]
        assert integrator.map_roles(["Administrators"]) == ["owner"]
        assert integrator.map_roles(["Developers", "Editors"]) == ["editor", "editor"]
        assert integrator.map_roles(["Operators"]) == ["operator"]
        assert integrator.map_roles(["UnknownGroup"]) == ["viewer"]
        assert integrator.map_roles([]) == ["viewer"]

    @pytest.mark.asyncio
    async def test_fallback_parse_saml_response_success(self, integrator):
        xml_content = """<?xml version="1.0"?>
        <samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
                        xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">
            <saml:Assertion>
                <saml:Subject>
                    <saml:NameID>user-12345</saml:NameID>
                </saml:Subject>
                <saml:Conditions NotBefore="2020-01-01T00:00:00Z" NotOnOrAfter="2099-01-01T00:00:00Z">
                    <saml:AudienceRestriction>
                        <saml:Audience>https://supremeai.app/sp</saml:Audience>
                    </saml:AudienceRestriction>
                </saml:Conditions>
                <saml:AttributeStatement>
                    <saml:Attribute Name="email">
                        <saml:AttributeValue>user@example.com</saml:AttributeValue>
                    </saml:Attribute>
                    <saml:Attribute Name="groups">
                        <saml:AttributeValue>Developers</saml:AttributeValue>
                    </saml:Attribute>
                </saml:AttributeStatement>
            </saml:Assertion>
        </samlp:Response>"""

        b64_xml = base64.b64encode(xml_content.encode("utf-8")).decode("utf-8")
        res = await integrator.process_sso_response({"SAMLResponse": b64_xml})

        assert res["status"] == "success"
        assert res["user_id"] == "user-12345"
        assert res["email"] == "user@example.com"
        assert "editor" in res["roles"]

    @pytest.mark.asyncio
    async def test_fallback_parse_saml_response_missing_data(self, integrator):
        res = await integrator.process_sso_response({})
        assert res["status"] == "error"
        assert "Missing SAMLResponse" in res["message"]

    @pytest.mark.asyncio
    async def test_fallback_parse_saml_response_expired(self, integrator):
        xml_content = """<?xml version="1.0"?>
        <samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
                        xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">
            <saml:Assertion>
                <saml:Conditions NotOnOrAfter="2020-01-01T00:00:00Z" />
            </saml:Assertion>
        </samlp:Response>"""
        b64_xml = base64.b64encode(xml_content.encode("utf-8")).decode("utf-8")
        res = await integrator.process_sso_response({"SAMLResponse": b64_xml})
        assert res["status"] == "error"
        assert "expired" in res["message"]

    @pytest.mark.asyncio
    async def test_fallback_parse_saml_response_audience_mismatch(self, integrator):
        xml_content = """<?xml version="1.0"?>
        <samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
                        xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">
            <saml:Assertion>
                <saml:Conditions>
                    <saml:AudienceRestriction>
                        <saml:Audience>https://wrong.sp/sp</saml:Audience>
                    </saml:AudienceRestriction>
                </saml:Conditions>
            </saml:Assertion>
        </samlp:Response>"""
        b64_xml = base64.b64encode(xml_content.encode("utf-8")).decode("utf-8")
        res = await integrator.process_sso_response({"SAMLResponse": b64_xml})
        assert res["status"] == "error"
        assert "audience restriction mismatch" in res["message"]

    @pytest.mark.asyncio
    async def test_process_slo_response(self, integrator):
        slo_xml = """<?xml version="1.0"?>
        <samlp:LogoutResponse xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol">
            <samlp:Status>
                <samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/>
            </samlp:Status>
        </samlp:LogoutResponse>"""
        res = await integrator.process_slo_response({"SAMLResponse": slo_xml})
        assert res["status"] == "success"

        res_fail = await integrator.process_slo_response({})
        assert res_fail["status"] == "error"

    def test_validate_token_and_parse_saml(self, integrator):
        secret = "secret-1234567890"
        payload = {"sub": "test_user", "exp": 9999999999}
        token = jwt.encode(payload, secret, algorithm="HS256")

        decoded = integrator.validate_token(token, secret)
        assert decoded["sub"] == "test_user"

        invalid = integrator.validate_token("invalid-token", secret)
        assert "error" in invalid

    def test_oidc_auth_url(self, integrator):
        url = integrator.get_oidc_auth_url("okta", "client_1", "https://callback", "state_xyz")
        assert "auth.example.com" in url
        assert "client_id=client_1" in url

        url_google = integrator.get_oidc_auth_url(
            "google", "client_g", "https://callback", "state_g"
        )
        assert "accounts.google.com" in url_google

        with pytest.raises(ValueError):
            integrator.get_oidc_auth_url("unsupported_provider", "id", "uri", "state")

    @pytest.mark.asyncio
    async def test_exchange_oidc_code_and_process(self, integrator):
        fake_id_token = jwt.encode(
            {"sub": "google-user-1", "email": "user@google.com", "hd": "company.com"},
            "fake-secret",
            algorithm="HS256",
        )

        mock_resp = httpx.Response(
            200,
            json={
                "access_token": "mock_access_token",
                "id_token": fake_id_token,
                "token_type": "Bearer",
            },
            request=httpx.Request("POST", "https://oauth2.googleapis.com/token"),
        )

        # বাংলা মন্তব্য: SEC-HARDEN P5 এর পর id_token এর signature JWKS দিয়ে verify করা
        # হয় (fail-closed)। এই টেস্টে বাস্তব JWKS নেই, তাই verification স্তরটি মক করে
        # শুধু decoded claims রিটার্ন করানো হচ্ছে — সিকিউরিটি লজিক অপরিবর্তিত থাকছে।
        decoded_claims = jwt.decode(fake_id_token, options={"verify_signature": False})
        with (
            patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp),
            patch.object(
                integrator,
                "_verify_oidc_id_token",
                new=AsyncMock(return_value=(decoded_claims, None)),
            ),
        ):
            res = await integrator.process_oidc_response(
                provider="google", code="auth_code_123", state="state_123"
            )
            assert res["status"] == "success"
            assert res["user_id"] == "google-user-1"
            assert res["email"] == "user@google.com"
            assert "method" in res
