import asyncio
import datetime
import unicodedata

from .exceptions import CalendarServiceError, UnsafeCalendarActionItemError

MAX_CALENDAR_ACTION_ITEM_LENGTH = 500
UNSAFE_CALENDAR_ACTION_ITEM_SEQUENCES = ("<", ">", "`", "$(", "${")
GOOGLE_OAUTH_ENDPOINT_URL = "https://oauth2.googleapis.com/token"
GOOGLE_OAUTH_ALLOWED_KEYS = {
    "account",
    "client_id",
    "client_secret",
    "expiry",
    "quota_project_id",
    "rapt_token",
    "refresh_token",
    "scopes",
    "token",
    "token_uri",
    "universe_domain",
}
GOOGLE_OAUTH_REQUIRED_KEYS = {
    "client_id",
    "client_secret",
    "refresh_token",
    "token_uri",
}
GOOGLE_CALENDAR_BATCH_MAX_REQUESTS = 50


def build(*args, **kwargs):
    from googleapiclient.discovery import build as google_calendar_build

    return google_calendar_build(*args, **kwargs)


def _google_credentials(validated_user_token: dict):
    from google.oauth2.credentials import Credentials

    return Credentials(**validated_user_token)


def validate_calendar_action_item_text(action_item_text: str) -> str:
    """Validate user-authored calendar text before external writeback."""
    normalized = action_item_text.strip()
    if not normalized or len(normalized) > MAX_CALENDAR_ACTION_ITEM_LENGTH:
        raise UnsafeCalendarActionItemError("Unsafe calendar action item text")
    if any(unicodedata.category(character) == "Cc" for character in normalized):
        raise UnsafeCalendarActionItemError("Unsafe calendar action item text")
    if any(
        sequence in normalized for sequence in UNSAFE_CALENDAR_ACTION_ITEM_SEQUENCES
    ):
        raise UnsafeCalendarActionItemError("Unsafe calendar action item text")
    return normalized


def validate_google_user_token(user_token: dict) -> dict:
    """Allow only server-issued Google OAuth credential fields."""
    if not isinstance(user_token, dict):
        raise CalendarServiceError("Invalid calendar credentials")

    unexpected_keys = set(user_token) - GOOGLE_OAUTH_ALLOWED_KEYS
    if unexpected_keys:
        raise CalendarServiceError("Invalid calendar credentials")

    missing_required_keys = {
        key
        for key in GOOGLE_OAUTH_REQUIRED_KEYS
        if not isinstance(user_token.get(key), str) or not user_token[key].strip()
    }
    if missing_required_keys:
        raise CalendarServiceError("Invalid calendar credentials")

    token_uri = user_token.get("token_uri")
    if token_uri != GOOGLE_OAUTH_ENDPOINT_URL:
        raise CalendarServiceError("Invalid calendar credentials")

    access_token = user_token.get("token")
    if access_token is not None and (
        not isinstance(access_token, str) or not access_token.strip()
    ):
        raise CalendarServiceError("Invalid calendar credentials")

    return dict(user_token)


async def create_calendar_event(action_item_text: str, user_token: dict) -> dict:
    """Creates a calendar event for a given action item text."""
    try:
        safe_action_item_text = validate_calendar_action_item_text(action_item_text)
        validated_user_token = validate_google_user_token(user_token)
        creds = _google_credentials(validated_user_token)
        service = build("calendar", "v3", credentials=creds)

        now = datetime.datetime.now(datetime.timezone.utc)
        event = {
            "summary": safe_action_item_text,
            "start": {"dateTime": now.isoformat()},
            "end": {"dateTime": (now + datetime.timedelta(hours=1)).isoformat()},
        }
        request = service.events().insert(calendarId="primary", body=event)
        created_event = await asyncio.to_thread(request.execute)
        return created_event
    except UnsafeCalendarActionItemError:
        raise
    except CalendarServiceError:
        raise
    except Exception as e:
        raise CalendarServiceError("Failed to create event") from e


async def _execute_calendar_event_batch(
    service,
    safe_action_item_texts: list[str],
    now: datetime.datetime,
) -> list[dict]:
    results: list[dict | None] = [None] * len(safe_action_item_texts)
    exceptions: list[Exception | None] = [None] * len(safe_action_item_texts)

    def callback(request_id, response, exception):
        idx = int(request_id)
        if exception is not None:
            exceptions[idx] = exception
            return
        results[idx] = response

    batch = service.new_batch_http_request(callback=callback)
    for idx, safe_action_item_text in enumerate(safe_action_item_texts):
        event = {
            "summary": safe_action_item_text,
            "start": {"dateTime": now.isoformat()},
            "end": {"dateTime": (now + datetime.timedelta(hours=1)).isoformat()},
        }
        request = service.events().insert(calendarId="primary", body=event)
        batch.add(request, request_id=str(idx))

    await asyncio.to_thread(batch.execute)

    for exc in exceptions:
        if exc is not None:
            raise CalendarServiceError("Failed to create event in batch") from exc

    created_events: list[dict] = []
    for result in results:
        if result is None:
            raise CalendarServiceError("Failed to create event in batch")
        created_events.append(result)
    return created_events


async def create_calendar_events_batch(
    action_item_texts: list[str], user_token: dict
) -> list[dict]:
    """Creates calendar events for action item text in bounded Google batch requests."""
    if not action_item_texts:
        return []

    try:
        safe_action_item_texts = [
            validate_calendar_action_item_text(action_item_text)
            for action_item_text in action_item_texts
        ]
        validated_user_token = validate_google_user_token(user_token)
        creds = _google_credentials(validated_user_token)
        now = datetime.datetime.now(datetime.timezone.utc)

        tasks = []
        for start in range(
            0, len(safe_action_item_texts), GOOGLE_CALENDAR_BATCH_MAX_REQUESTS
        ):
            chunk = safe_action_item_texts[
                start : start + GOOGLE_CALENDAR_BATCH_MAX_REQUESTS
            ]
            chunk_service = build("calendar", "v3", credentials=creds)
            tasks.append(_execute_calendar_event_batch(chunk_service, chunk, now))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        created_events: list[dict] = []
        for result in results:
            if isinstance(result, Exception):
                raise CalendarServiceError(
                    "Failed to create events in batch"
                ) from result
            created_events.extend(result)
        return created_events
    except UnsafeCalendarActionItemError:
        raise
    except CalendarServiceError:
        raise
    except Exception as e:
        raise CalendarServiceError("Failed to create events in batch") from e
