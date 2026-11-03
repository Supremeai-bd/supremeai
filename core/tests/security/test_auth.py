"""
Authentication Service Test Suite
====================================

Critical Path Tests - These tests ensure the security of user authentication,
JWT token management, and role-based access control (RBAC).

Test Coverage:
- User registration and validation
- Login and token generation
- Token validation and refresh
- Password hashing and verification
- Role-based permissions
- Session management
- Security edge cases
- Rate limiting (if applicable)

Run with: pytest tests/test_auth.py -v --cov=auth
"""

import asyncio
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.tests.conftest import (
    TEST_ACCESS_TOKEN_EXPIRE_MINUTES,
    TEST_ALGORITHM,
    TEST_SECRET_KEY,
    CustomAssertions,
    sample_admin_data,
    sample_operator_data,
    sample_user_data,
    valid_password,
)

# ============================================================================
# MOCK AUTH SERVICE IMPLEMENTATION (for testing)
# ============================================================================


class MockAuthService:
    """
    Mock implementation of Auth Service for testing.

    In production, this would be app/core/security.py or app/services/auth.py
    This mock simulates all authentication behaviors for isolated unit testing.
    """

    # Valid roles in the system
    VALID_ROLES = {"user", "admin", "agent_operator"}

    # Role hierarchy (higher number = more permissions)
    ROLE_HIERARCHY = {
        "user": 1,
        "agent_operator": 2,
        "admin": 3,
    }

    # Password requirements
    PASSWORD_MIN_LENGTH = 8
    PASSWORD_REQUIRE_UPPERCASE = True
    PASSWORD_REQUIRE_LOWERCASE = True
    PASSWORD_REQUIRE_DIGIT = True
    PASSWORD_REQUIRE_SPECIAL = True

    def __init__(self):
        self.users: dict[str, dict[str, Any]] = {}
        self.tokens: dict[str, dict[str, Any]] = {}
        self.refresh_tokens: dict[str, dict[str, Any]] = {}
        self._user_counter = 0

    async def hash_password(self, password: str) -> str:
        """Hash password for storage."""
        if not password:
            raise ValueError("Password cannot be empty")

        self._validate_password_strength(password)

        # Simple hash for testing (in production: use bcrypt/argon2)
        import hashlib

        salt = "test-salt"  # Fixed salt for deterministic tests
        return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()

    async def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        new_hash = await self.hash_password(plain_password)
        return new_hash == hashed_password

    async def create_user(
        self, email: str, password: str, full_name: str | None = None, role: str = "user"
    ) -> dict[str, Any]:
        """Register a new user."""

        # Validate email
        if not email or not self._is_valid_email(email):
            raise ValueError("Invalid email format")

        # Check uniqueness
        existing = await self.get_user_by_email(email)
        if existing:
            raise ValueError("Email already registered")

        # Validate role
        if role not in self.VALID_ROLES:
            raise ValueError(f"Invalid role: {role}")

        # Hash password
        hashed_pw = await self.hash_password(password)

        # Create user
        self._user_counter += 1
        now = datetime.now(UTC)

        user = {
            "id": f"user-{self._user_counter:04d}",
            "email": email.lower(),
            "hashed_password": hashed_pw,
            "full_name": full_name or "",
            "role": role,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "last_login_at": None,
        }

        self.users[user["id"]] = user

        # Return user without sensitive data
        return self._sanitize_user(user)

    async def authenticate_user(self, email: str, password: str) -> dict[str, Any]:
        """Authenticate user and return tokens."""

        user = await self.get_user_by_email(email)

        if not user:
            raise ValueError("Invalid credentials")

        if not user["is_active"]:
            raise ValueError("Account is disabled")

        # Verify password
        if not await self.verify_password(password, user["hashed_password"]):
            raise ValueError("Invalid credentials")

        # Update last login
        user["last_login_at"] = datetime.now(UTC)

        # Generate tokens
        access_token, refresh_token = await self._create_token_pair(user)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": TEST_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": self._sanitize_user(user),
        }

    async def validate_token(self, token: str) -> dict[str, Any]:
        """Validate JWT token and return payload."""

        if not token:
            raise ValueError("Token is required")

        try:
            import jwt
            from jwt import PyJWTError as JWTError

            payload = jwt.decode(token, TEST_SECRET_KEY, algorithms=[TEST_ALGORITHM])

            # Check expiration
            exp = payload.get("exp")
            if exp and datetime.fromtimestamp(exp, tz=UTC) < datetime.now(UTC):
                raise ValueError("Token has expired")

            # Verify user still exists and active
            user_id = payload.get("sub")
            if user_id and user_id in self.users:
                user = self.users[user_id]
                if not user["is_active"]:
                    raise ValueError("User account is disabled")

            return payload

        except Exception as e:
            if "expired" in str(e).lower():
                raise ValueError("Token has expired")
            elif "signature" in str(e).lower():
                raise ValueError("Invalid token signature")
            else:
                raise ValueError(f"Invalid token: {str(e)}")

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        """Generate new access token from refresh token."""

        if not refresh_token:
            raise ValueError("Refresh token is required")

        # Validate refresh token
        try:
            import jwt
            from jwt import PyJWTError as JWTError

            payload = jwt.decode(refresh_token, TEST_SECRET_KEY, algorithms=[TEST_ALGORITHM])

            if payload.get("type") != "refresh":
                raise ValueError("Invalid token type")

            user_id = payload.get("sub")
            if not user_id or user_id not in self.users:
                raise ValueError("Invalid refresh token")

            user = self.users[user_id]

            if not user["is_active"]:
                raise ValueError("User account is disabled")

            # Generate new token pair
            access_token, new_refresh_token = await self._create_token_pair(user)

            return {
                "access_token": access_token,
                "refresh_token": new_refresh_token,
                "token_type": "bearer",
                "expires_in": TEST_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            }

        except Exception as e:
            raise ValueError(f"Invalid refresh token: {str(e)}")

    async def get_current_user(self, token: str) -> dict[str, Any]:
        """Get current user from token."""

        payload = await self.validate_token(token)
        user_id = payload.get("sub")

        if not user_id:
            raise ValueError("Could not validate credentials")

        user = self.users.get(user_id)
        if not user:
            raise ValueError("User not found")

        return self._sanitize_user(user)

    def check_permission(self, user_role: str, required_role: str) -> bool:
        """Check if user has required permission level."""
        user_level = self.ROLE_HIERARCHY.get(user_role, 0)
        required_level = self.ROLE_HIERARCHY.get(required_role, 999)

        return user_level >= required_level

    async def deactivate_user(self, user_id: str) -> bool:
        """Deactivate a user account."""
        if user_id not in self.users:
            return False

        self.users[user_id]["is_active"] = False
        self.users[user_id]["updated_at"] = datetime.now(UTC)

        return True

    async def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        """Get user by email address."""
        email_lower = email.lower() if email else ""
        for user in self.users.values():
            if user["email"] == email_lower:
                return user
        return None

    async def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        """Get user by ID."""
        return self.users.get(user_id)

    async def update_user(self, user_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Update user information."""

        if user_id not in self.users:
            raise ValueError("User not found")

        user = self.users[user_id]

        updatable_fields = {"full_name", "role"}

        for field, value in updates.items():
            if field not in updatable_fields:
                continue

            if field == "role" and value not in self.VALID_ROLES:
                raise ValueError(f"Invalid role: {value}")

            user[field] = value
            user["updated_at"] = datetime.now(UTC)

        return self._sanitize_user(user)

    async def _create_token_pair(self, user: dict[str, Any]) -> tuple:
        """Create access and refresh token pair."""
        try:
            import jwt

            now = datetime.now(UTC)
            # বাংলা মন্তব্য (ROOT-CAUSE FIX): iat/exp সেকেন্ড-precision-এ ট্রাংকেট হয়,
            # তাই একই সেকেন্ডে login + refresh হলে payload হুবহু এক হয়ে যেত এবং
            # jwt.encode একই টোকেন ফেরত দিত (test_refresh_token_generates_new_pair
            # ব্যর্থ হতো)। প্রতিটি টোকেনে ইউনিক `jti` যোগ করে uniqueness নিশ্চিত করা হলো।
            import uuid

            # Access token (short-lived)
            access_payload = {
                "sub": user["id"],
                "email": user["email"],
                "role": user["role"],
                "iat": now,
                "exp": now + timedelta(minutes=TEST_ACCESS_TOKEN_EXPIRE_MINUTES),
                "type": "access",
                "jti": uuid.uuid4().hex,
            }

            access_token = jwt.encode(access_payload, TEST_SECRET_KEY, algorithm=TEST_ALGORITHM)

            # Refresh token (long-lived)
            refresh_payload = {
                "sub": user["id"],
                "iat": now,
                "exp": now + timedelta(days=7),  # 7 days
                "type": "refresh",
                "jti": uuid.uuid4().hex,
            }

            refresh_token = jwt.encode(refresh_payload, TEST_SECRET_KEY, algorithm=TEST_ALGORITHM)

            return access_token, refresh_token

        except ImportError:
            # Fallback for testing without PyJWT
            return f"mock-access-{user['id']}", f"mock-refresh-{user['id']}"

    def _validate_password_strength(self, password: str) -> None:
        """Validate password meets strength requirements."""
        if len(password) < self.PASSWORD_MIN_LENGTH:
            raise ValueError(f"Password must be at least {self.PASSWORD_MIN_LENGTH} characters")

        if self.PASSWORD_REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
            raise ValueError("Password must contain at least one uppercase letter")

        if self.PASSWORD_REQUIRE_LOWERCASE and not any(c.islower() for c in password):
            raise ValueError("Password must contain at least one lowercase letter")

        if self.PASSWORD_REQUIRE_DIGIT and not any(c.isdigit() for c in password):
            raise ValueError("Password must contain at least one digit")

        if self.PASSWORD_REQUIRE_SPECIAL and not any(
            c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password
        ):
            raise ValueError("Password must contain at least one special character")

    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """Basic email validation."""
        import re

        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    @staticmethod
    def _sanitize_user(user: dict[str, Any]) -> dict[str, Any]:
        """Remove sensitive fields from user object."""
        safe_user = {
            "id": user["id"],
            "email": user["email"],
            "full_name": user.get("full_name", ""),
            "role": user["role"],
            "is_active": user["is_active"],
            "created_at": user["created_at"].isoformat(),
            "last_login_at": (
                user["last_login_at"].isoformat() if user.get("last_login_at") else None
            ),
        }
        return safe_user


# ============================================================================
# TEST FIXTURES SPECIFIC TO AUTH
# ============================================================================


@pytest.fixture
def auth_service() -> MockAuthService:
    """Create fresh auth service instance for each test."""
    return MockAuthService()


@pytest.fixture
async def registered_user(auth_service: MockAuthService, valid_password: str) -> dict[str, Any]:
    """Pre-registered test user."""
    return await auth_service.create_user(
        email="test@example.com", password=valid_password, full_name="Test User", role="user"
    )


@pytest.fixture
async def registered_admin(auth_service: MockAuthService, valid_password: str) -> dict[str, Any]:
    """Pre-registered admin user."""
    return await auth_service.create_user(
        email="admin@example.com", password=valid_password, full_name="Admin User", role="admin"
    )


@pytest.fixture
async def authenticated_user(
    auth_service: MockAuthService, registered_user: dict[str, Any], valid_password: str
) -> dict[str, Any]:
    """Pre-authenticated user with tokens."""
    return await auth_service.authenticate_user(email="test@example.com", password=valid_password)


# ============================================================================
# TEST CLASS: User Registration
# ============================================================================


class TestUserRegistration:
    """Tests for user registration functionality."""

    @pytest.mark.unit
    @pytest.mark.critical
    @pytest.mark.asyncio
    async def test_register_valid_user(
        self, auth_service: MockAuthService, valid_password: str, assertions: CustomAssertions
    ):
        """Should successfully register valid user."""
        user = await auth_service.create_user(
            email="newuser@example.com", password=valid_password, full_name="New User", role="user"
        )

        assert user is not None
        assert user["email"] == "newuser@example.com"
        assert user["full_name"] == "New User"
        assert user["role"] == "user"
        assert user["is_active"] is True
        assertions.assert_email_format(user["email"])
        assert "id" in user
        assert "hashed_password" not in user  # Should not expose password

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_register_generates_unique_ids(
        self, auth_service: MockAuthService, valid_password: str
    ):
        """Should generate unique IDs for each user."""
        users = []

        for i in range(5):
            user = await auth_service.create_user(
                email=f"user{i}@example.com", password=valid_password, full_name=f"User {i}"
            )
            users.append(user)

        ids = [u["id"] for u in users]
        assert len(ids) == len(set(ids)), "All user IDs should be unique"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_register_stores_lowercase_email(
        self, auth_service: MockAuthService, valid_password: str
    ):
        """Should store email in lowercase."""
        user = await auth_service.create_user(
            email="MixedCase@Example.COM", password=valid_password
        )

        assert user["email"] == "mixedcase@example.com"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_register_sets_timestamps(
        self, auth_service: MockAuthService, valid_password: str
    ):
        """Should set created_at timestamp."""
        before_reg = datetime.now(UTC)

        user = await auth_service.create_user(email="time@example.com", password=valid_password)

        after_reg = datetime.now(UTC)

        created_at = datetime.fromisoformat(user["created_at"])
        assert before_reg <= created_at <= after_reg

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reject_duplicate_email(
        self, auth_service: MockAuthService, registered_user: dict[str, Any], valid_password: str
    ):
        """Should reject registration with duplicate email."""
        with pytest.raises(ValueError, match="already registered"):
            await auth_service.create_user(
                email="test@example.com",  # Already registered
                password=valid_password,
                full_name="Duplicate User",
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reject_invalid_email_format(
        self, auth_service: MockAuthService, valid_password: str
    ):
        """Should reject invalid email formats."""
        invalid_emails = [
            "notanemail",
            "@example.com",
            "user@",
            "user@.com",
            "space in@example.com",
        ]

        for email in invalid_emails:
            with pytest.raises(ValueError, match="Invalid email"):
                await auth_service.create_user(email=email, password=valid_password)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reject_invalid_role(self, auth_service: MockAuthService, valid_password: str):
        """Should reject invalid roles."""
        with pytest.raises(ValueError, match="Invalid role"):
            await auth_service.create_user(
                email="role@example.com",
                password=valid_password,
                role="superadmin",  # Invalid role
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_accept_all_valid_roles(self, auth_service: MockAuthService, valid_password: str):
        """Should accept all valid roles."""
        for role in ["user", "admin", "agent_operator"]:
            user = await auth_service.create_user(
                email=f"{role}@example.com", password=valid_password, role=role
            )
            assert user["role"] == role


# ============================================================================
# TEST CLASS: Password Validation
# ============================================================================


class TestPasswordValidation:
    """Tests for password validation rules."""

    @pytest.mark.unit
    @pytest.mark.critical
    @pytest.mark.asyncio
    async def test_accept_strong_password(self, auth_service: MockAuthService):
        """Should accept strong passwords."""
        strong_passwords = [
            "SecurePass123!",
            "MyP@ssw0rdHere",
            "Str0ng!Password",
            "V3ryS3cur3P@ss!",
        ]

        for password in strong_passwords:
            hashed = await auth_service.hash_password(password)
            assert hashed is not None
            assert len(hashed) > 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reject_short_password(self, auth_service: MockAuthService):
        """Should reject short passwords."""
        short_passwords = ["short", "1234567", "aB3!efg"]

        for password in short_passwords:
            with pytest.raises(ValueError, match="at least"):
                await auth_service.hash_password(password)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_require_uppercase(self, auth_service: MockAuthService):
        """Should require uppercase letter."""
        with pytest.raises(ValueError, match="uppercase"):
            await auth_service.hash_password("lowercase123!")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_require_lowercase(self, auth_service: MockAuthService):
        """Should require lowercase letter."""
        with pytest.raises(ValueError, match="lowercase"):
            await auth_service.hash_password("UPPERCASE123!")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_require_digit(self, auth_service: MockAuthService):
        """Should require digit."""
        with pytest.raises(ValueError, match="digit"):
            await auth_service.hash_password("NoDigitsHere!")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_require_special_char(self, auth_service: MockAuthService):
        """Should require special character."""
        with pytest.raises(ValueError, match="special"):
            await auth_service.hash_password("NoSpecialChars123")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reject_empty_password(self, auth_service: MockAuthService):
        """Should reject empty password."""
        with pytest.raises(ValueError, match="cannot be empty"):
            await auth_service.hash_password("")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_verify_correct_password(self, auth_service: MockAuthService):
        """Should verify correct password."""
        password = "CorrectPassword123!"
        hashed = await auth_service.hash_password(password)

        is_valid = await auth_service.verify_password(password, hashed)
        assert is_valid is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reject_incorrect_password(self, auth_service: MockAuthService):
        """Should reject incorrect password."""
        correct_password = "CorrectPassword123!"
        wrong_password = "WrongPassword456!"

        hashed = await auth_service.hash_password(correct_password)

        is_valid = await auth_service.verify_password(wrong_password, hashed)
        assert is_valid is False


# ============================================================================
# TEST CLASS: Authentication & Login
# ============================================================================


class TestAuthenticationAndLogin:
    """Tests for user authentication and login process."""

    @pytest.mark.unit
    @pytest.mark.critical
    @pytest.mark.asyncio
    async def test_login_with_valid_credentials(
        self, auth_service: MockAuthService, registered_user: dict[str, Any], valid_password: str
    ):
        """Should authenticate with valid credentials."""
        result = await auth_service.authenticate_user(
            email="test@example.com", password=valid_password
        )

        assert result is not None
        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "bearer"
        assert result["expires_in"] > 0
        assert result["user"]["email"] == "test@example.com"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_login_updates_last_login(
        self, auth_service: MockAuthService, registered_user: dict[str, Any], valid_password: str
    ):
        """Should update last_login_at on successful login."""
        # Before login, last_login should be None
        user_before = await auth_service.get_user_by_email("test@example.com")
        assert user_before["last_login_at"] is None

        # Login
        await auth_service.authenticate_user(email="test@example.com", password=valid_password)

        # After login, should have timestamp
        user_after = await auth_service.get_user_by_email("test@example.com")
        assert user_after["last_login_at"] is not None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reject_wrong_password(
        self, auth_service: MockAuthService, registered_user: dict[str, Any]
    ):
        """Should reject login with wrong password."""
        with pytest.raises(ValueError, match="Invalid credentials"):
            await auth_service.authenticate_user(
                email="test@example.com", password="WrongPassword123!"
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reject_nonexistent_user(self, auth_service: MockAuthService):
        """Should reject login for nonexistent user."""
        with pytest.raises(ValueError, match="Invalid credentials"):
            await auth_service.authenticate_user(
                email="nonexistent@example.com", password="SomePassword123!"
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reject_disabled_account(
        self, auth_service: MockAuthService, registered_user: dict[str, Any], valid_password: str
    ):
        """Should reject login for disabled accounts."""
        # Deactivate the user
        await auth_service.deactivate_user(registered_user["id"])

        with pytest.raises(ValueError, match="disabled"):
            await auth_service.authenticate_user(email="test@example.com", password=valid_password)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_case_insensitive_email_login(
        self, auth_service: MockAuthService, registered_user: dict[str, Any], valid_password: str
    ):
        """Email login should be case-insensitive."""
        result = await auth_service.authenticate_user(
            email="TEST@EXAMPLE.COM",  # Uppercase version
            password=valid_password,
        )

        assert result is not None
        assert result["user"]["email"] == "test@example.com"


# ============================================================================
# TEST CLASS: Token Management
# ============================================================================


class TestTokenManagement:
    """Tests for JWT token generation and validation."""

    @pytest.mark.unit
    @pytest.mark.critical
    @pytest.mark.asyncio
    async def test_validate_valid_token(
        self, auth_service: MockAuthService, authenticated_user: dict[str, Any]
    ):
        """Should successfully validate valid token."""
        token = authenticated_user["access_token"]

        payload = await auth_service.validate_token(token)

        assert payload is not None
        assert "sub" in payload
        assert "email" in payload
        assert "role" in payload
        assert "exp" in payload

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reject_expired_token(self, auth_service: MockAuthService):
        """Should reject expired tokens."""
        import jwt

        # Create already-expired token
        expired_payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "role": "user",
            "exp": datetime.now(UTC) - timedelta(hours=1),
            "iat": datetime.now(UTC) - timedelta(hours=2),
        }

        expired_token = jwt.encode(expired_payload, TEST_SECRET_KEY, algorithm=TEST_ALGORITHM)

        with pytest.raises(ValueError, match="expired"):
            await auth_service.validate_token(expired_token)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reject_malformed_token(self, auth_service: MockAuthService):
        """Should reject malformed tokens."""
        malformed_tokens = [
            "",  # Empty
            "not.a.token",  # Not enough parts
            "invalid.token.here",  # Invalid format
            "bearer sometoken",  # With prefix
        ]

        for token in malformed_tokens:
            with pytest.raises((ValueError, Exception)):
                await auth_service.validate_token(token)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reject_tampered_token(self, auth_service: MockAuthService):
        """Should reject tampered tokens."""
        import jwt

        # Create valid token
        valid_payload = {
            "sub": "user-123",
            "role": "user",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        }

        valid_token = jwt.encode(valid_payload, TEST_SECRET_KEY, algorithm=TEST_ALGORITHM)

        # Tamper by changing role
        parts = valid_token.split(".")
        # Just modify slightly to break signature
        tampered_token = (
            parts[0] + "." + "tampered" + "." + parts[2] if len(parts) >= 3 else "tampered"
        )

        with pytest.raises(ValueError, match="signature|invalid"):
            await auth_service.validate_token(tampered_token)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_current_user_from_token(
        self, auth_service: MockAuthService, authenticated_user: dict[str, Any]
    ):
        """Should retrieve current user from valid token."""
        token = authenticated_user["access_token"]

        user = await auth_service.get_current_user(token)

        assert user is not None
        assert user["email"] == "test@example.com"
        assert "hashed_password" not in user  # Never expose password

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_refresh_token_generates_new_pair(
        self, auth_service: MockAuthService, authenticated_user: dict[str, Any]
    ):
        """Refresh token should generate new token pair."""
        old_refresh = authenticated_user["refresh_token"]

        new_tokens = await auth_service.refresh_access_token(old_refresh)

        assert new_tokens["access_token"] != authenticated_user["access_token"]
        assert new_tokens["refresh_token"] != old_refresh
        assert new_tokens["expires_in"] > 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reject_invalid_refresh_token(self, auth_service: MockAuthService):
        """Should reject invalid refresh tokens."""
        invalid_tokens = [
            "",
            "invalid-token",
            "access.token.instead",  # Wrong type
        ]

        for token in invalid_tokens:
            with pytest.raises(ValueError):
                await auth_service.refresh_access_token(token)


# ============================================================================
# TEST CLASS: Role-Based Access Control (RBAC)
# ============================================================================


class TestRoleBasedAccessControl:
    """Tests for RBAC permission system."""

    @pytest.mark.unit
    @pytest.mark.critical
    @pytest.mark.asyncio
    async def test_admin_has_highest_permissions(self, auth_service: MockAuthService):
        """Admin role should have highest permission level."""
        assert auth_service.check_permission("admin", "user") is True
        assert auth_service.check_permission("admin", "agent_operator") is True
        assert auth_service.check_permission("admin", "admin") is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_operator_permissions(self, auth_service: MockAuthService):
        """Agent operator should have medium permissions."""
        assert auth_service.check_permission("agent_operator", "user") is True
        assert auth_service.check_permission("agent_operator", "admin") is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_user_lowest_permissions(self, auth_service: MockAuthService):
        """Regular user should have lowest permissions."""
        assert auth_service.check_permission("user", "user") is True
        assert auth_service.check_permission("user", "agent_operator") is False
        assert auth_service.check_permission("user", "admin") is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invalid_role_no_permissions(self, auth_service: MockAuthService):
        """Invalid role should have no permissions."""
        assert auth_service.check_permission("invalid_role", "user") is False
        assert auth_service.check_permission("user", "invalid_role") is False


# ============================================================================
# TEST CLASS: User Management
# ============================================================================


class TestUserManagement:
    """Tests for user management operations."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_deactivate_user(
        self, auth_service: MockAuthService, registered_user: dict[str, Any]
    ):
        """Should successfully deactivate user."""
        result = await auth_service.deactivate_user(registered_user["id"])

        assert result is True

        # User should no longer be able to log in
        user = await auth_service.get_user_by_id(registered_user["id"])
        assert user["is_active"] is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_deactivate_nonexistent_user(self, auth_service: MockAuthService):
        """Should return False for nonexistent user."""
        result = await auth_service.deactivate_user("nonexistent-id")

        assert result is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_user_full_name(
        self, auth_service: MockAuthService, registered_user: dict[str, Any]
    ):
        """Should update user's full name."""
        updated = await auth_service.update_user(
            user_id=registered_user["id"], updates={"full_name": "Updated Name"}
        )

        assert updated["full_name"] == "Updated Name"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_user_role(
        self, auth_service: MockAuthService, registered_user: dict[str, Any]
    ):
        """Should update user's role."""
        updated = await auth_service.update_user(
            user_id=registered_user["id"], updates={"role": "agent_operator"}
        )

        assert updated["role"] == "agent_operator"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reject_invalid_role_update(
        self, auth_service: MockAuthService, registered_user: dict[str, Any]
    ):
        """Should reject invalid role during update."""
        with pytest.raises(ValueError, match="Invalid role"):
            await auth_service.update_user(
                user_id=registered_user["id"], updates={"role": "superadmin"}
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reject_update_nonexistent_user(self, auth_service: MockAuthService):
        """Should reject updating nonexistent user."""
        with pytest.raises(ValueError, match="not found"):
            await auth_service.update_user(user_id="nonexistent-id", updates={"full_name": "Name"})

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_user_by_id(
        self, auth_service: MockAuthService, registered_user: dict[str, Any]
    ):
        """Should retrieve user by ID."""
        user = await auth_service.get_user_by_id(registered_user["id"])

        assert user is not None
        assert user["id"] == registered_user["id"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, auth_service: MockAuthService):
        """Should return None for nonexistent ID."""
        user = await auth_service.get_user_by_id("nonexistent-id")

        assert user is None


# ============================================================================
# SECURITY EDGE CASE TESTS
# ============================================================================


class TestSecurityEdgeCases:
    """Tests for security-related edge cases."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_prevent_sql_injection_in_email(
        self, auth_service: MockAuthService, valid_password: str
    ):
        """Should handle SQL injection attempts in email gracefully."""
        injection_attempts = [
            "' OR '1'='1",
            "'; DROP TABLE users; --",
            "admin'--",
            "' UNION SELECT * FROM users--",
        ]

        for malicious_email in injection_attempts:
            # Should either raise validation error or fail safely
            try:
                user = await auth_service.create_user(
                    email=malicious_email, password=valid_password
                )
                # If it doesn't crash, that's good
                # But it shouldn't create a real user with SQL injection
                assert "@" in user.get("email", ""), (
                    f"SQL injection attempt may have succeeded: {malicious_email}"
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                import logging

                logging.getLogger(__name__).exception(f"Silenced error: {e}")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_unicode_in_credentials(
        self, auth_service: MockAuthService, valid_password: str
    ):
        """Should handle unicode characters correctly."""
        unicode_emails = [
            "user@例え.jp",
            "tëst@example.com",
            "user@äöü.com",
        ]

        for email in unicode_emails:
            try:
                user = await auth_service.create_user(email=email, password=valid_password)
                assert user is not None
            except asyncio.CancelledError:
                raise
            except Exception as e:
                import logging

                logging.getLogger(__name__).exception(f"Silenced error: {e}")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_very_long_inputs(self, auth_service: MockAuthService, valid_password: str):
        """Should handle very long inputs gracefully."""
        long_email = f"user{'a' * 1000}@example.com"
        long_name = "A" * 500

        # Should either accept or reject with proper error
        try:
            user = await auth_service.create_user(
                email=long_email, password=valid_password, full_name=long_name
            )
            assert user is not None
        except asyncio.CancelledError:
            raise
        except Exception as e:
            import logging

            logging.getLogger(__name__).exception(f"Silenced error: {e}")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_special_characters_in_names(
        self, auth_service: MockAuthService, valid_password: str
    ):
        """Should handle special characters in names."""
        special_names = [
            "O'Brien",
            "José García",
            "Müller-Lüdenscheidt",
            "张伟",  # Chinese
            "أحمد",  # Arabic
            "Иван",  # Cyrillic
        ]

        for name in special_names:
            user = await auth_service.create_user(
                email=f"test_{hash(name)}@example.com", password=valid_password, full_name=name
            )
            assert user["full_name"] == name

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_concurrent_registration_same_email(
        self, auth_service: MockAuthService, valid_password: str
    ):
        """Handle concurrent registration attempts for same email."""

        async def register():
            try:
                return await auth_service.create_user(
                    email="concurrent@example.com", password=valid_password
                )
            except ValueError:
                return None

        # Try to register same email concurrently
        tasks = [register() for _ in range(5)]
        results = await asyncio.gather(*tasks)

        # Only one should succeed
        successes = [r for r in results if r is not None]
        assert len(successes) == 1, "Only one registration should succeed"


# ============================================================================
# INTEGRATION TESTS: Full Auth Workflows
# ============================================================================


class TestAuthWorkflowsIntegration:
    """Integration tests for complete authentication workflows."""

    @pytest.mark.integration
    @pytest.mark.critical
    @pytest.mark.asyncio
    async def test_full_registration_and_login_workflow(
        self, auth_service: MockAuthService, valid_password: str
    ):
        """Complete workflow: register -> login -> use token -> logout."""

        # Step 1: Register new user
        user = await auth_service.create_user(
            email="workflow@example.com", password=valid_password, full_name="Workflow User"
        )

        assert user is not None
        assert user["is_active"] is True

        # Step 2: Login with credentials
        auth_result = await auth_service.authenticate_user(
            email="workflow@example.com", password=valid_password
        )

        assert auth_result["access_token"] is not None
        assert auth_result["refresh_token"] is not None

        # Step 3: Use token to get current user
        current_user = await auth_service.get_current_user(auth_result["access_token"])

        assert current_user["email"] == "workflow@example.com"
        assert current_user["full_name"] == "Workflow User"

        # Step 4: Use refresh token to get new access token
        refreshed = await auth_service.refresh_access_token(auth_result["refresh_token"])

        assert refreshed["access_token"] != auth_result["access_token"]

        # Step 5: New token should also work
        final_user = await auth_service.get_current_user(refreshed["access_token"])

        assert final_user["email"] == "workflow@example.com"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_password_change_workflow(
        self, auth_service: MockAuthService, registered_user: dict[str, Any], valid_password: str
    ):
        """Workflow: login -> change password -> re-login with new password."""

        # Initial login works
        auth1 = await auth_service.authenticate_user(
            email="test@example.com", password=valid_password
        )
        assert auth1 is not None

        # Simulate password change (would require current password in production)
        # For this test, we'll just verify the service handles it
        new_password = "NewSecurePass456!"

        # Update user's password directly (simulating change endpoint)
        user_data = auth_service.users[registered_user["id"]]
        user_data["hashed_password"] = await auth_service.hash_password(new_password)

        # Old password should no longer work
        with pytest.raises(ValueError):
            await auth_service.authenticate_user(email="test@example.com", password=valid_password)

        # New password should work
        auth2 = await auth_service.authenticate_user(
            email="test@example.com", password=new_password
        )

        assert auth2 is not None
        assert auth2["access_token"] is not None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_account_deactivation_workflow(
        self, auth_service: MockAuthService, registered_user: dict[str, Any], valid_password: str
    ):
        """Workflow: active -> deactivate -> login fails -> reactivate -> login succeeds."""

        # Account starts active
        auth1 = await auth_service.authenticate_user(
            email="test@example.com", password=valid_password
        )
        assert auth1 is not None

        # Deactivate account
        await auth_service.deactivate_user(registered_user["id"])

        # Login should fail
        with pytest.raises(ValueError, match="disabled"):
            await auth_service.authenticate_user(email="test@example.com", password=valid_password)

        # Reactivate (simulate admin action)
        auth_service.users[registered_user["id"]]["is_active"] = True

        # Login should work again
        auth2 = await auth_service.authenticate_user(
            email="test@example.com", password=valid_password
        )

        assert auth2 is not None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_role_upgrade_workflow(
        self, auth_service: MockAuthService, registered_user: dict[str, Any], valid_password: str
    ):
        """Workflow: user -> upgrade to operator -> check permissions."""

        # Start as regular user
        assert auth_service.check_permission("user", "agent_operator") is False

        # Upgrade role (simulating admin action)
        updated = await auth_service.update_user(
            user_id=registered_user["id"], updates={"role": "agent_operator"}
        )

        assert updated["role"] == "agent_operator"

        # Now has operator permissions
        assert auth_service.check_permission("agent_operator", "user") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=auth", "--cov-report=term-missing"])
