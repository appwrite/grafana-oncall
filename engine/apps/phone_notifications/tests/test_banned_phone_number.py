import pytest

from apps.phone_notifications.models.banned_phone_number import BannedPhoneNumber, ban_phone_number


@pytest.mark.django_db
def test_ban_phone_number(make_organization, make_user_for_organization, caplog):
    organization = make_organization()
    banned_phone_number = "+1234567890"
    unbanned_phone_number = "+0987654321"
    banned_user_1 = make_user_for_organization(
        organization=organization,
        _verified_phone_number=banned_phone_number,
        unverified_phone_number=banned_phone_number,
    )
    banned_user_2 = make_user_for_organization(
        organization=organization,
        _verified_phone_number=banned_phone_number,
        unverified_phone_number=banned_phone_number,
    )
    unbanned_user = make_user_for_organization(
        organization=organization,
        _verified_phone_number=unbanned_phone_number,
        unverified_phone_number=unbanned_phone_number,
    )
    reason = "usage too high"
    with caplog.at_level("INFO", logger="apps.phone_notifications.models.banned_phone_number"):
        ban_phone_number(banned_phone_number, reason)
    assert "affected_users=2" in caplog.text
    assert banned_phone_number not in caplog.text
    assert reason not in caplog.text
    banned_user_1.refresh_from_db()
    assert banned_user_1._verified_phone_number is None
    assert banned_user_1.unverified_phone_number == banned_phone_number
    banned_user_2.refresh_from_db()
    assert banned_user_2._verified_phone_number is None
    assert banned_user_2.unverified_phone_number == banned_phone_number
    unbanned_user.refresh_from_db()
    assert unbanned_user._verified_phone_number == unbanned_phone_number
    assert unbanned_user.unverified_phone_number == unbanned_phone_number
    ban_phone_number_entry = BannedPhoneNumber.objects.get(pk=banned_phone_number)
    assert ban_phone_number_entry is not None
    assert ban_phone_number_entry.reason == reason
    user_entries = ban_phone_number_entry.get_user_entries()
    assert len(user_entries) == 2
