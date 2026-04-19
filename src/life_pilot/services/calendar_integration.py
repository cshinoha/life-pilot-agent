"""Google Calendar integration for Life Pilot"""

import json
import os
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytz


def get_calendar_events(
    days_ahead: int = 0,
    timezone: str | None = None,
    token_path: Path | None = None,
) -> list[dict[str, str]]:
    """
    Получает события из Google Calendar

    Args:
        days_ahead: на сколько дней вперёд (0 = сегодня, 7 = неделя)
        timezone: временная зона (None = читать из Settings)
        token_path: путь к файлу токена (JSON). Если None — дефолт из Settings.

    Returns:
        list: события [{summary, start, end, description}]
    """
    from life_pilot.config import get_settings
    settings = get_settings()
    if timezone is None:
        timezone = settings.timezone
    if token_path is None:
        token_path = Path(os.path.expanduser(str(settings.google_token_path)))
    else:
        token_path = Path(os.path.expanduser(str(token_path)))

    if not token_path.exists():
        raise FileNotFoundError(f"Token not found: {token_path}")

    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build  # type: ignore[import-untyped]

    with open(token_path) as f:
        creds_data = cast(dict[str, Any], json.load(f))
    from_authorized_user_info = cast(
        Callable[[dict[str, Any]], Credentials],
        Credentials.from_authorized_user_info,
    )
    creds = from_authorized_user_info(creds_data)

    service = build('calendar', 'v3', credentials=creds)
    
    tz = pytz.timezone(timezone)
    
    now = datetime.now(tz)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_period = start_of_day + timedelta(days=days_ahead + 1)
    
    time_min = start_of_day.isoformat()
    time_max = end_of_period.isoformat()
    
    events_result = service.events().list(
        calendarId='primary',
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    events = events_result.get('items', [])
    
    formatted_events = []
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))
        
        formatted_events.append({
            'summary': event.get('summary', 'No title'),
            'start': start,
            'end': end,
            'description': event.get('description', ''),
            'location': event.get('location', '')
        })
    
    return formatted_events


if __name__ == '__main__':
    print("Testing calendar integration...")
    events = get_calendar_events(days_ahead=0)
    
    if not events:
        print("No events found for today")
    else:
        print(f"\nFound {len(events)} events:\n")
        for event in events:
            print(f"- {event['summary']}")
            print(f"  Start: {event['start']}")
            print(f"  End: {event['end']}")
            if event['description']:
                print(f"  Description: {event['description']}")
            print()
