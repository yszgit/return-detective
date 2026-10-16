"""Calendar plans for human review, separate from historical evidence cutoffs.

Plans can optionally schedule an email reminder; they never schedule an Agent run.
"""
import datetime as dt
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import store


def build_plan(date, time, timezone, email='', *, now=None):
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError('Choose a valid time zone, for example America/Toronto or UTC.') from None
    local = dt.datetime.combine(date, time).replace(tzinfo=None)
    first, second = local.replace(tzinfo=zone, fold=0), local.replace(tzinfo=zone, fold=1)
    utc = first.astimezone(dt.timezone.utc)
    if utc.astimezone(zone).replace(tzinfo=None) != local:
        raise ValueError('This local time does not exist because the clocks change. Choose another time.')
    if first.utcoffset() != second.utcoffset():
        raise ValueError('This local time occurs twice because the clocks change. Choose another time or UTC.')
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise ValueError('The current time must include a time zone.')
    if utc <= now:
        raise ValueError('Choose a review date and time in the future.')
    email = email.strip()
    if email and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
        raise ValueError('Enter a valid review contact email, or leave it blank.')
    return {'review_at_utc': utc.isoformat(timespec='seconds'),
            'local_at': first.isoformat(timespec='minutes'), 'timezone': timezone,
            'contact_email': email, 'status': 'PLANNED_MANUAL',
            'email_delivery': 'NOT_ENABLED', 'automatic_run': False,
            'saved_at': now.astimezone(dt.timezone.utc).isoformat(timespec='seconds')}


def save_plan(case_id, date, time, timezone, email='', *, now=None, send_email=False):
    case = store.get_case(case_id)
    if not case:
        raise ValueError('The selected case no longer exists.')
    if case['status'] == 'CLOSED':
        raise ValueError('This case is closed. Select an open case to plan a review.')
    plan = build_plan(date, time, timezone, email, now=now)
    from . import reminders
    if send_email:
        return reminders.schedule(case, plan, now=now)
    reminders.cancel(case)
    if not store.update_case(case_id, review_plan=plan):
        raise ValueError('The review plan could not be saved.')
    return plan


def cancel_reminder(case_id):
    from . import reminders
    case = store.get_case(case_id)
    if not case:
        raise ValueError('The selected case no longer exists.')
    return reminders.cancel(case)
