import os
import uuid
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
 
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRETS_DIR = os.path.join(BASE_DIR, "secrets")
CREDENTIALS_PATH = os.path.join(SECRETS_DIR, "credentials.json")
TOKEN_PATH = os.path.join(SECRETS_DIR, "token.json")
SCOPES = ["https://www.googleapis.com/auth/calendar"]
DEFAULT_TIMEZONE = "Asia/Ho_Chi_Minh"

def _get_credentials():
    if not os.path.exists(TOKEN_PATH):
        raise FileNotFoundError( f"Không tìm thấy {TOKEN_PATH}." )
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
 
    return creds

def _get_service():
    creds = _get_credentials()
    return build("calendar", "v3", credentials=creds)

def _to_rfc3339(dt: datetime) -> str:
    if dt.tzinfo is not None:
        return dt.isoformat()
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + "+07:00"

def get_busy_intervals(calendar_id: str, time_min: datetime, time_max: datetime):
    """
    Gọi freebusy.query, trả về danh sách khoảng BẬN dạng [(datetime, datetime), ...].
    """
    service = _get_service()
    body = {
        "timeMin": _to_rfc3339(time_min),
        "timeMax": _to_rfc3339(time_max),
        "timeZone": DEFAULT_TIMEZONE,
        "items": [{"id": calendar_id}],
    }
    result = service.freebusy().query(body = body).execute()
    busy_raw = result["calendars"][calendar_id]["busy"]
    busy_intervals = []
    for b in busy_raw:
        start = datetime.fromisoformat(b["start"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(b["end"].replace("Z", "+00:00"))
        busy_intervals.append((start, end))
 
    return busy_intervals

def get_free_intervals(
    calendar_id: str,
    time_min: datetime,
    time_max: datetime,
    work_start_hour: int = 9,
    work_end_hour: int = 18,):
    busy_intervals = get_busy_intervals(calendar_id, time_min, time_max)
    busy_intervals.sort(key=lambda x: x[0])
    #free invtervals = total time - busy intervals
    free_intervals = []
    current_day = time_min.date()
    last_day = time_max.date()
    while current_day<= last_day:
        day_start = datetime.combine(current_day, datetime.min.time()).replace(
            hour = work_start_hour
        )
        day_end = datetime.combine(current_day, datetime.min.time()).replace(
            hour = work_end_hour
        )
        cursor = day_start
        day_busy = [
            (max(b[0].replace(tzinfo=None), day_start), min(b[1].replace(tzinfo=None), day_end))
            for b in busy_intervals
            if b[0].date() <= current_day <= b[1].date()
        ]
        day_busy.sort(key=lambda x: x[0])
        #cusor work as a pointer, move to the end of busy, free intervals += (busy_start- cusor )
        for busy_start, busy_end in day_busy:
            if busy_start > cursor:
                free_intervals.append((cursor, busy_start))
            cursor = max(cursor, busy_end)
        # add the remaining of the day
        if cursor< day_end:
            free_intervals.append((cursor, day_end))
        
        current_day += timedelta(days = 1)
    return free_intervals

def create_events(
    summary: str,
    start: datetime,
    end: datetime,
    attendee_emails: list,
    calendar_id: str = "primary",
    description: str = "",
):
    service = _get_service()
    event_body = {
        "summary": summary,
        "description": description,
         "start": {"dateTime": _to_rfc3339(start), "timeZone": DEFAULT_TIMEZONE},
        "end": {"dateTime": _to_rfc3339(end), "timeZone": DEFAULT_TIMEZONE},
        "attendees": [{"email": email} for email in attendee_emails],
        "conferenceData": {
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }
 
    created_event = (
        service.events()
        .insert(
            calendarId=calendar_id,
            body=event_body,
            conferenceDataVersion=1,  
            sendUpdates="all", 
        )
        .execute()
    )
 
    return {
        "event_id": created_event.get("id"),
        "event_link": created_event.get("htmlLink"),
        "meet_link": created_event.get("hangoutLink"),
    }
 
    