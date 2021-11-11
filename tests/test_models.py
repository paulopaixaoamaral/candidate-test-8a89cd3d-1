import datetime
import uuid

import pytest
from django.utils.timezone import now as tz_now

from visitors.models import InvalidVisitorPass, Visitor

TEST_UUID: str = "68201321-9dd2-4fb3-92b1-24367f38a7d6"

TODAY: datetime.datetime = tz_now()
ONE_DAY: datetime.timedelta = datetime.timedelta(days=1)
TOMORROW: datetime.datetime = TODAY + ONE_DAY
YESTERDAY: datetime.datetime = TODAY - ONE_DAY


@pytest.mark.parametrize(
    "url_in,url_out",
    (
        ("google.com", f"google.com?vuid={TEST_UUID}"),
        ("google.com?vuid=123", f"google.com?vuid={TEST_UUID}"),
    ),
)
def test_visitor_tokenise(url_in, url_out):
    visitor = Visitor(uuid=uuid.UUID(TEST_UUID))
    assert visitor.tokenise(url_in) == url_out


@pytest.mark.django_db
def test_deactivate():
    visitor = Visitor.objects.create(email="foo@bar.com")
    assert visitor.is_active
    visitor.deactivate()
    assert not visitor.is_active
    visitor.refresh_from_db()
    assert not visitor.is_active


@pytest.mark.django_db
def test_reactivate():
    visitor = Visitor.objects.create(
        email="foo@bar.com",
        is_active=False,
        expires_at=YESTERDAY,
        maximum_visits=10,
        visits_count=11,
    )
    assert not visitor.is_active
    assert visitor.has_expired
    assert visitor.has_exceeded_maximum_visits
    assert not visitor.is_valid
    visitor.reactivate()
    assert visitor.is_active
    assert not visitor.has_expired
    assert not visitor.has_exceeded_maximum_visits
    assert visitor.is_valid
    visitor.refresh_from_db()
    assert visitor.is_active
    assert not visitor.has_expired
    assert not visitor.has_exceeded_maximum_visits
    assert visitor.is_valid


@pytest.mark.parametrize(
    "is_active,expires_at,maximum_visits,visits_count,is_valid",
    (
        (True, TOMORROW, None, 0, True),
        (True, TOMORROW, 10, 10, True),
        (False, TOMORROW, None, 0, False),
        (False, YESTERDAY, None, 0, False),
        (True, YESTERDAY, None, 0, False),
        (True, TOMORROW, 10, 11, False),
    ),
)
def test_validate(is_active, expires_at, maximum_visits, visits_count, is_valid):
    visitor = Visitor(
        is_active=is_active,
        expires_at=expires_at,
        maximum_visits=maximum_visits,
        visits_count=visits_count,
    )
    assert visitor.is_active == is_active
    assert visitor.has_expired == bool(expires_at < TODAY)
    if is_valid:
        visitor.validate()
        return
    with pytest.raises(InvalidVisitorPass):
        visitor.validate()


@pytest.mark.parametrize(
    "is_active,expires_at,maximum_visits,visits_count,is_valid",
    (
        (True, TOMORROW, None, 0, True),
        (True, TOMORROW, 10, 10, True),
        (False, TOMORROW, None, 0, False),
        (False, YESTERDAY, None, 0, False),
        (True, YESTERDAY, None, 0, False),
        (True, None, None, 0, True),
        (False, None, None, 0, False),
        (False, None, 10, 11, False),
    ),
)
def test_is_valid(is_active, expires_at, maximum_visits, visits_count, is_valid):
    visitor = Visitor(
        is_active=is_active,
        expires_at=expires_at,
        maximum_visits=maximum_visits,
        visits_count=visits_count,
    )
    assert visitor.is_valid == is_valid


def test_defaults():
    visitor = Visitor()
    assert visitor.created_at
    assert visitor.expires_at == visitor.created_at + Visitor.DEFAULT_TOKEN_EXPIRY
    assert visitor.maximum_visits is None
    assert visitor.visits_count == 0


@pytest.mark.parametrize(
    "expires_at,has_expired",
    (
        (TOMORROW, False),
        (YESTERDAY, True),
        (None, False),
    ),
)
def test_has_expired(expires_at, has_expired):
    visitor = Visitor()
    visitor.expires_at = expires_at
    assert visitor.has_expired == has_expired


@pytest.mark.parametrize(
    "maximum_visits,visits_count,has_exceeded",
    (
        (None, 11, False),
        (10, 0, False),
        (10, 10, False),
        (10, 11, True),
    ),
)
def test_has_exceeded_maximum_visits(maximum_visits, visits_count, has_exceeded):
    visitor = Visitor(maximum_visits=maximum_visits, visits_count=visits_count)
    assert visitor.has_exceeded_maximum_visits is has_exceeded


@pytest.mark.django_db
def test_add_visit():
    # Adding a visit when maximum_visits is None should not increment the number of
    # visits.
    visitor = Visitor.objects.create()
    assert visitor.visits_count == 0
    visitor.add_visit()
    assert visitor.visits_count == 0
    visitor.refresh_from_db()
    assert visitor.visits_count == 0

    # Adding a visit when maximum_visits is not None should increment the number of
    # visits.
    visitor.maximum_visits = 10
    visitor.add_visit()
    assert visitor.visits_count == 1
    visitor.refresh_from_db()
    assert visitor.visits_count == 1
