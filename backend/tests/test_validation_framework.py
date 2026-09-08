"""Tests for ``app.core.validation`` — the backend's final input authority.

Structured in four parts, matching the four ways this can go wrong:

1. Legitimate input must not be blocked. A validator that refuses "O'Brien" or
   a description containing "5 < 10" is a bug that reaches the user as "the app
   won't let me save my work", and these cases are the ones most easily broken
   by a later tightening.
2. Malicious and malformed input must be refused.
3. Passwords must survive untouched, including every special character.
4. The rules must hold when the request does not come from our own clients —
   the case the whole layering exists for.
"""
from __future__ import annotations

import unittest
from decimal import Decimal

from pydantic import BaseModel, ValidationError

from app.core.validation import (
    DESCRIPTION_MAX_LENGTH,
    NAME_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    Credential,
    Email,
    Identifier,
    InputValidationError,
    LIKE_ESCAPE_CHARACTER,
    Name,
    OptionalDescription,
    Password,
    escape_like_wildcards,
    like_pattern,
    validate_credential,
    validate_date,
    validate_decimal,
    validate_description,
    validate_domain,
    validate_email,
    validate_enum,
    validate_id_list,
    validate_identifier,
    validate_integer,
    validate_name,
    validate_password,
    validate_plain_text,
    validate_search_term,
    validate_url,
    validate_uuid,
)

# The payloads the requirement calls out by name, plus the encodings usually
# used to slip them past a naive filter.
ATTACK_PAYLOADS = [
    "<script>alert(1)</script>",
    "<div>test</div>",
    "<img src=x onerror=alert(1)>",
    "<iframe src='http://evil.example'></iframe>",
    "<a href='javascript:alert(1)'>x</a>",
    "<svg/onload=alert(1)>",
    "<?xml version='1.0'?><root/>",
    "<!DOCTYPE html>",
    "<![CDATA[payload]]>",
    "&lt;script&gt;alert(1)&lt;/script&gt;",
    "&#60;script&#62;",
    "${jndi:ldap://evil.example/a}",
    "{{7*7}}",
    "javascript:alert(1)",
    "onerror=alert(1)",
]


class LegitimateInputIsNotBlockedTests(unittest.TestCase):
    """The accept cases. Over-restriction is the failure mode users report."""

    def test_names_with_real_world_punctuation_and_scripts(self):
        for value in [
            "Website Redesign",
            "O'Brien & Sons, Ltd.",
            "Jean-Luc Picard",
            "José Álvarez",
            "プロジェクト計画",
            "Проект Альфа",
            "Q3 2026 — Phase 2 (final)",
            "100% Coverage",
            "R&D / Prototype #4",
        ]:
            with self.subTest(value=value):
                self.assertEqual(validate_name(value), value)

    def test_descriptions_with_ordinary_prose(self):
        for value in [
            "Fixed the timer bug. It only happened when 5 < 10 and a -> b.",
            "Line one.\nLine two.\n\nA final paragraph.",
            "Cost is 50% of budget; see item #4 (approx. $1,200).",
            # A bug report quoting a payload is the commonest legitimate reason
            # for a description to contain braces.
            'The API returned {"error": 1} and then stopped responding.',
            "Réunion à 14h — préparer l'ordre du jour.",
            "Use the a > b comparison, not a >= b.",
        ]:
            with self.subTest(value=value):
                self.assertTrue(validate_description(value))

    def test_a_name_is_trimmed_and_interior_whitespace_collapsed(self):
        self.assertEqual(validate_name("  Acme   Corp  "), "Acme Corp")

    def test_email_domain_is_lowercased_but_local_part_is_preserved(self):
        """RFC 5321 makes the local part case-sensitive; the domain is not."""
        self.assertEqual(
            validate_email("User.Name+tag@Example.COM"), "User.Name+tag@example.com"
        )

    def test_windows_line_endings_normalise_to_match_the_desktop(self):
        self.assertEqual(
            validate_description("first\r\nsecond\rthird"), "first\nsecond\nthird"
        )

    def test_legitimate_urls_survive_url_rules(self):
        """URL punctuation would be refused by the prose rules."""
        for url in [
            "https://example.com",
            "http://docs.example.com/a/b?query=1&other=2#frag",
            "https://example.com/search?q=100%25",
        ]:
            with self.subTest(url=url):
                self.assertEqual(validate_url(url), url)

    def test_a_boundary_length_value_is_accepted(self):
        self.assertTrue(validate_name("x" * NAME_MAX_LENGTH))
        self.assertTrue(validate_description("x" * DESCRIPTION_MAX_LENGTH))


class MaliciousInputIsRejectedTests(unittest.TestCase):
    def test_every_attack_payload_is_refused_by_the_text_rules(self):
        for payload in ATTACK_PAYLOADS:
            with self.subTest(payload=payload):
                with self.assertRaises(InputValidationError):
                    validate_description(payload)
                with self.assertRaises(InputValidationError):
                    validate_name(payload)

    def test_a_whole_json_document_is_refused_where_prose_is_expected(self):
        for payload in ['{"key":"value"}', '["unexpected","json"]', "{}", "[]"]:
            with self.subTest(payload=payload):
                with self.assertRaises(InputValidationError):
                    validate_description(payload)

    def test_a_value_of_only_punctuation_is_refused(self):
        """Regression: these were saved.

        Length and structure alone passed them — "!!!" has a length, is not
        markup and is not JSON — so a required field could be satisfied without
        being answered.
        """
        for payload in [
            "!!!", "@@@", "...", "---", "???", "$$$", "***", "&&&",
            "##", "()", "/", "\\", ".", "-", "_", "+++", "~~~", ";;",
            "!@#$%^&*()", "   ---   ",
        ]:
            with self.subTest(payload=payload):
                with self.assertRaises(InputValidationError):
                    validate_name(payload)
                with self.assertRaises(InputValidationError):
                    validate_description(payload)
                with self.assertRaises(InputValidationError):
                    validate_plain_text(payload, required=True)

    def test_the_punctuation_only_message_says_what_to_do(self):
        with self.assertRaises(InputValidationError) as caught:
            validate_name("!!!", field_label="Project name")
        self.assertEqual(
            str(caught.exception),
            "Project name must contain at least one letter or number.",
        )

    def test_punctuation_alongside_real_content_is_still_fine(self):
        """The check asks for *some* content, not for the absence of symbols."""
        for value in ["Fixed!!!", "...and then it crashed", "C++", "v2.0!",
                      "R&D / Prototype #4", "50% !!!", "A"]:
            with self.subTest(value=value):
                self.assertTrue(validate_name(value))

    def test_non_latin_scripts_satisfy_the_content_requirement(self):
        """A letter is a letter in any script — this is not an ASCII check."""
        for value in ["プロジェクト", "Проект", "مشروع", "项目", "프로젝트"]:
            with self.subTest(value=value):
                self.assertTrue(validate_name(value))

    def test_a_search_term_may_still_be_punctuation_only(self):
        """The backend does not require content in a search box.

        Searching for "???" is harmless: it filters, it is not stored. The
        clients deliberately match this, so neither is stricter than here.
        """
        self.assertIsNotNone(validate_search_term("???"))

    def test_control_characters_are_rejected_not_silently_stripped(self):
        """Rejecting is the point: normalising first would hide the NUL."""
        with self.assertRaises(InputValidationError) as caught:
            validate_name("Project\x00Name")
        self.assertIn("unsupported characters", str(caught.exception))

    def test_terminal_escape_sequences_are_rejected(self):
        with self.assertRaises(InputValidationError):
            validate_description("status: \x1b[31mFAILED\x1b[0m")

    def test_dangerous_url_schemes_are_refused(self):
        for url in [
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "vbscript:msgbox(1)",
            "ftp://example.com/file",
            "file:///etc/passwd",
        ]:
            with self.subTest(url=url):
                with self.assertRaises(InputValidationError):
                    validate_url(url)

    def test_oversized_input_is_refused(self):
        with self.assertRaises(InputValidationError):
            validate_name("x" * (NAME_MAX_LENGTH + 1))
        with self.assertRaises(InputValidationError):
            validate_description("x" * (DESCRIPTION_MAX_LENGTH + 1))
        with self.assertRaises(InputValidationError):
            validate_plain_text("x" * 5000, required=True)

    def test_wrong_types_are_refused_rather_than_coerced(self):
        for value in [123, [], {}, object()]:
            with self.subTest(value=value):
                with self.assertRaises(InputValidationError):
                    validate_name(value)


class PasswordHandlingTests(unittest.TestCase):
    """Passwords are the one field nothing here may alter."""

    SPECIAL_PASSWORDS = [
        "p@ssw0rd!",
        "<script>alert(1)</script>",
        "{}[]<>!@#$%^&*()_+-=",
        "correct horse battery staple",
        "パスワード12345",
        "  leading and trailing  ",
        "'; DROP TABLE users; --",
    ]

    def test_special_characters_are_accepted_and_the_value_is_unchanged(self):
        """Applying the text rules here would reject good secrets.

        Every one of these is a legitimate password. ``<script>`` as a password
        is eccentric but valid, and refusing it would lock the owner out with an
        error that looks like "wrong password".
        """
        for password in self.SPECIAL_PASSWORDS:
            with self.subTest(password=password):
                self.assertEqual(validate_password(password), password)

    def test_whitespace_is_never_trimmed_from_a_password(self):
        self.assertEqual(validate_password("  spaced  "), "  spaced  ")

    def test_unicode_in_a_password_is_not_normalised(self):
        """NFC folding would change the bytes handed to the hasher.

        The composed and decomposed spellings look identical but are different
        secrets; normalising one into the other breaks an existing login.
        """
        decomposed = "café" + "12345"
        self.assertEqual(validate_password(decomposed), decomposed)

    def test_the_minimum_length_policy_applies_when_choosing_a_password(self):
        with self.assertRaises(InputValidationError):
            validate_password("short")

    def test_login_accepts_a_short_legacy_password(self):
        """Enforcing the minimum at login would lock out older accounts."""
        self.assertEqual(validate_credential("old1"), "old1")

    def test_login_still_rejects_an_empty_password(self):
        with self.assertRaises(InputValidationError):
            validate_credential("")

    def test_the_upper_bound_still_applies_at_login(self):
        """Only to cap the work handed to the hasher."""
        with self.assertRaises(InputValidationError):
            validate_credential("x" * 5000)


class NumberAndFormatTests(unittest.TestCase):
    def test_identifiers_accept_positive_keys_only(self):
        self.assertEqual(validate_identifier(42), 42)
        self.assertEqual(validate_identifier("42"), 42)
        for value in [0, -1, "abc", 1.5, None, ""]:
            with self.subTest(value=value):
                with self.assertRaises(InputValidationError):
                    validate_identifier(value)

    def test_a_boolean_is_not_an_identifier(self):
        """``bool`` subclasses ``int``, so ``True`` would pass as 1."""
        with self.assertRaises(InputValidationError):
            validate_identifier(True)

    def test_integer_ranges_are_enforced(self):
        self.assertEqual(validate_integer("5", minimum=1, maximum=10), 5)
        with self.assertRaises(InputValidationError):
            validate_integer("0", minimum=1)
        with self.assertRaises(InputValidationError):
            validate_integer("11", maximum=10)

    def test_non_finite_decimals_are_refused(self):
        """NaN parses cleanly and then poisons every later comparison."""
        for value in ["NaN", "Infinity", "-Infinity", "sNaN"]:
            with self.subTest(value=value):
                with self.assertRaises(InputValidationError):
                    validate_decimal(value)

    def test_decimal_bounds(self):
        self.assertEqual(validate_decimal("12.50"), Decimal("12.50"))
        with self.assertRaises(InputValidationError):
            validate_decimal("-1", allow_negative=False)
        with self.assertRaises(InputValidationError):
            validate_decimal("101", maximum=Decimal("100"))

    def test_uuid_requires_canonical_form(self):
        self.assertEqual(
            validate_uuid("123E4567-E89B-12D3-A456-426614174000"),
            "123e4567-e89b-12d3-a456-426614174000",
        )
        for value in ["123e4567e89b12d3a456426614174000", "not-a-uuid", ""]:
            with self.subTest(value=value):
                with self.assertRaises(InputValidationError):
                    validate_uuid(value)

    def test_dates_reject_wrong_formats_and_impossible_days(self):
        self.assertEqual(str(validate_date("2026-09-08")), "2026-09-08")
        for value in ["08/09/2026", "2026-02-30", "2026-13-01", "yesterday"]:
            with self.subTest(value=value):
                with self.assertRaises(InputValidationError):
                    validate_date(value)

    def test_enum_rejects_values_outside_the_set(self):
        allowed = ["open", "in_progress", "done"]
        self.assertEqual(validate_enum("open", allowed), "open")
        with self.assertRaises(InputValidationError):
            validate_enum("deleted", allowed)

    def test_enum_error_names_the_permitted_values(self):
        """The allowed set is part of the API contract, not a secret."""
        with self.assertRaises(InputValidationError) as caught:
            validate_enum("nope", ["a", "b"], field_label="Status")
        self.assertIn("a, b", str(caught.exception))

    def test_domains_are_lowercased_and_checked(self):
        self.assertEqual(validate_domain("Docs.Example.COM"), "docs.example.com")
        for value in ["not a domain", "-bad.example", ""]:
            with self.subTest(value=value):
                with self.assertRaises(InputValidationError):
                    validate_domain(value)

    def test_id_lists_are_bounded_and_deduplicated(self):
        self.assertEqual(validate_id_list([1, 2, 3]), [1, 2, 3])
        with self.assertRaises(InputValidationError):
            validate_id_list([1, 1, 2])
        with self.assertRaises(InputValidationError):
            validate_id_list(list(range(1, 500)))
        with self.assertRaises(InputValidationError):
            validate_id_list([1, 0, 2])


class SearchAndLikeEscapingTests(unittest.TestCase):
    """A user's ``%`` must mean a literal percent sign."""

    def test_wildcards_in_a_search_term_are_escaped(self):
        self.assertEqual(validate_search_term("100% done_now"), r"100\% done\_now")

    def test_the_escape_character_itself_is_escaped_first(self):
        """Otherwise a trailing backslash would escape the closing wildcard."""
        self.assertEqual(escape_like_wildcards(r"a\b"), r"a\\b")

    def test_like_pattern_wraps_and_escapes(self):
        self.assertEqual(like_pattern("50%"), r"%50\%%")

    def test_a_lone_wildcard_no_longer_matches_everything(self):
        """Unescaped, this turned a filtered query into a full table scan."""
        self.assertEqual(like_pattern("%"), r"%\%%")

    def test_prefix_patterns_are_supported(self):
        self.assertEqual(like_pattern("ab", contains=False), "ab%")

    def test_the_escape_character_is_the_one_the_queries_declare(self):
        self.assertEqual(LIKE_ESCAPE_CHARACTER, "\\")

    def test_a_blank_search_becomes_none_rather_than_matching_nothing(self):
        self.assertIsNone(validate_search_term("   "))
        self.assertIsNone(validate_search_term(None))

    def test_markup_in_a_search_box_is_still_refused(self):
        with self.assertRaises(InputValidationError):
            validate_search_term("<script>alert(1)</script>")


class PydanticIntegrationTests(unittest.TestCase):
    """The types must behave inside a real model, which is how schemas use them."""

    class Sample(BaseModel):
        name: Name
        description: OptionalDescription = None
        owner_id: Identifier
        email: Email
        password: Password

    def _valid_payload(self, **overrides):
        payload = {
            "name": "  Website   Redesign ",
            "description": "Ships on Friday.",
            "owner_id": "7",
            "email": "Owner@Example.COM",
            "password": "p@ssw0rd!<>",
        }
        payload.update(overrides)
        return payload

    def test_a_valid_payload_is_normalised(self):
        model = self.Sample(**self._valid_payload())
        self.assertEqual(model.name, "Website Redesign")
        self.assertEqual(model.owner_id, 7)
        self.assertEqual(model.email, "Owner@example.com")
        self.assertEqual(model.password, "p@ssw0rd!<>", "password was modified")

    def test_rejections_surface_as_pydantic_validation_errors(self):
        """Which is what FastAPI turns into its standard 422 response.

        Raising a ValueError subclass is what keeps the existing error contract
        intact — no new envelope, and no 500.
        """
        for field, value in [
            ("name", "<script>alert(1)</script>"),
            ("description", '{"a":1}'),
            ("owner_id", 0),
            ("email", "not-an-email"),
            ("password", "short"),
        ]:
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    self.Sample(**self._valid_payload(**{field: value}))

    def test_an_omitted_optional_description_stays_none(self):
        model = self.Sample(**self._valid_payload(description="   "))
        self.assertIsNone(model.description)


class DirectApiRequestTests(unittest.TestCase):
    """Requests that never ran our frontend or desktop code.

    This is the case the whole layering exists for. The values below are what a
    hand-built ``curl`` call, a replayed request with an edited body, or a
    custom HTTP client would send — none of them passed through a form, so none
    of them had client-side validation applied. They must still be refused.
    """

    def test_schema_rejects_payloads_a_client_would_never_produce(self):
        from app.schemas.project import ProjectCreate
        from app.schemas.task import TaskCreate
        from app.schemas.time_entry import TimeEntryStart
        from app.schemas.user import LoginRequest

        with self.assertRaises(ValidationError):
            ProjectCreate(project_name="<script>alert(1)</script>")
        with self.assertRaises(ValidationError):
            ProjectCreate(project_name="x" * 5000)
        with self.assertRaises(ValidationError):
            ProjectCreate(project_name="   ")
        with self.assertRaises(ValidationError):
            TaskCreate(task_name="ok", assignee_id=-5)
        with self.assertRaises(ValidationError):
            TaskCreate(task_name="ok", estimated_hours=-3)
        with self.assertRaises(ValidationError):
            TimeEntryStart(project_id=0, task_id=1)
        with self.assertRaises(ValidationError):
            TimeEntryStart(project_id=1, task_id=1, description="<div>x</div>")
        with self.assertRaises(ValidationError):
            LoginRequest(username="", password="whatever")

    def test_a_manual_entry_cannot_claim_more_than_a_day(self):
        """Previously any integer was accepted, including a negative one."""
        from app.schemas.manual_time_entry import ManualTimeEntryCreate

        base = {"project_id": 1, "task_id": 1, "work_date": "2026-09-08"}
        self.assertTrue(ManualTimeEntryCreate(**base, total_seconds=3600))
        for seconds in [0, -60, 24 * 60 * 60 + 1, 10**9]:
            with self.subTest(seconds=seconds):
                with self.assertRaises(ValidationError):
                    ManualTimeEntryCreate(**base, total_seconds=seconds)

    def test_a_manual_entry_update_enforces_the_time_slot_pairing(self):
        """The docstring promised this; no validator implemented it."""
        from app.schemas.manual_time_entry import ManualTimeEntryUpdate

        with self.assertRaises(ValidationError):
            ManualTimeEntryUpdate(start_time="2026-09-08T10:00:00")
        with self.assertRaises(ValidationError):
            ManualTimeEntryUpdate(
                start_time="2026-09-08T12:00:00", end_time="2026-09-08T10:00:00"
            )

    def test_bulk_id_payloads_are_bounded(self):
        """An unbounded list is a cheap way to make the database work hard."""
        from app.schemas.project_member import ProjectMembersAddRequest

        self.assertTrue(ProjectMembersAddRequest(member_ids=[1, 2, 3]))
        with self.assertRaises(ValidationError):
            ProjectMembersAddRequest(member_ids=list(range(1, 5000)))

    def test_identifier_fields_reject_injection_shaped_strings(self):
        from app.schemas.task_assignee import TaskAssigneeCreate

        for value in ["1 OR 1=1", "1; DROP TABLE users", "../../etc/passwd", "1e9999"]:
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    TaskAssigneeCreate(user_id=value)


class ConsistencyWithClientLayersTests(unittest.TestCase):
    """The backend must never be *stricter* than the clients on passwords.

    If it were, a password the desktop or web form happily accepted would be
    refused on submit, and the user would see a failure they cannot act on.
    """

    def test_password_policy_numbers_are_the_shared_ones(self):
        from app.core.validation import PASSWORD_MAX_LENGTH

        self.assertEqual(PASSWORD_MIN_LENGTH, 8)
        self.assertEqual(PASSWORD_MAX_LENGTH, 128)

    def test_credential_type_is_used_for_login_not_the_password_type(self):
        """A regression here silently locks out every legacy account."""
        from app.schemas.user import DevLoginRequest, LoginRequest

        for model in (LoginRequest, DevLoginRequest):
            with self.subTest(model=model.__name__):
                annotation = model.model_fields["password"].annotation
                self.assertIs(annotation, str)

        # The behavioural proof: a short password is accepted at login.
        self.assertTrue(LoginRequest(username="jo", password="old1"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
