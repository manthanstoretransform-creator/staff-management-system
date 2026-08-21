from datetime import date, timedelta
import unittest

from pydantic import ValidationError

from app.schemas.member import MemberCreate


def valid_member(**overrides):
    values = {
        "name": " Ada Lovelace ",
        "email": "ADA@example.com",
        "role": "employee",
        "status": "active",
        "date_of_joining": date(2026, 1, 1),
        "date_of_birth": date(1990, 1, 1),
        "designation": " Engineer ",
    }
    values.update(overrides)
    return values


class MemberSchemaTests(unittest.TestCase):
    def test_member_input_is_normalized(self):
        member = MemberCreate(**valid_member())
        self.assertEqual(member.name, "Ada Lovelace")
        self.assertEqual(member.email, "ada@example.com")
        self.assertEqual(member.designation, "Engineer")


    def test_required_text_fields_reject_whitespace(self):
        for field in ("name", "designation"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                MemberCreate(**valid_member(**{field: "   "}))


    def test_member_input_rejects_invalid_role_and_future_birth_date(self):
        with self.assertRaises(ValidationError):
            MemberCreate(**valid_member(role="manager"))
        with self.assertRaises(ValidationError):
            MemberCreate(**valid_member(date_of_birth=date.today() + timedelta(days=1)))