"""Daily watcher for new official Ministry of Agriculture egg-price announcements.

The workflow uses the existing GitHub Actions database secrets; no Render cron
service or paid external monitoring provider is required. A newly discovered
announcement creates in-app notifications for each tenant's administrators.
The watcher never changes supplier prices or inserts regulatory values.
"""
import hashlib
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from sqlalchemy import select

from app import create_app
from app.extensions import db
from app.models.notification import Notification, STATUS_UNREAD
from app.models.regulatory_price_monitor_state import RegulatoryPriceMonitorState
from app.models.tenant import Tenant
from app.models.user import User, ROLE_ADMIN, ROLE_MANAGER

SOURCE_PAGE = "https://www.gov.il/he/Departments/ministry_of_agriculture_and_food_security/govil-landing-page?NRMODE=Published"
DASHBOARD_PATH = "/dashboard/regulatory-prices"
KEYWORDS = ("מחירי הביצים שבפיקוח", "מחירי ביצים שבפיקוח", "מחירי הביצים")


class AnnouncementParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            title = " ".join(" ".join(self._text).split())
            if title:
                self.links.append((self._href, title))
            self._href = None
            self._text = []


def find_latest_egg_announcement(html: str):
    parser = AnnouncementParser()
    parser.feed(html)
    matches = []
    for href, title in parser.links:
        if any(keyword in title for keyword in KEYWORDS):
            published = re.search(r"(\d{2}/\d{2}/\d{2,4})", title)
            matches.append({
                "url": urljoin(SOURCE_PAGE, href),
                "title": title[:500],
                "published_at": published.group(1) if published else None,
            })
    return matches[0] if matches else None


def fetch_announcement():
    request = Request(SOURCE_PAGE, headers={"User-Agent": "SSOS-RegulatoryPriceMonitor/1.0"})
    with urlopen(request, timeout=25) as response:
        content_type = response.headers.get("Content-Type", "")
        raw = response.read(4 * 1024 * 1024)
        charset = "utf-8"
        match = re.search(r"charset=([^;]+)", content_type, re.I)
        if match:
            charset = match.group(1).strip(' "')
        html = raw.decode(charset, errors="replace")
    return find_latest_egg_announcement(html)


def run_monitor():
    checked_at = datetime.now(timezone.utc)
    state = db.session.get(RegulatoryPriceMonitorState, 1)
    if state is None:
        state = RegulatoryPriceMonitorState(id=1)
        db.session.add(state)
        db.session.flush()

    try:
        announcement = fetch_announcement()
        state.last_checked_at = checked_at
        state.last_error = None
        if not announcement:
            state.last_error = "לא נמצאה הודעת ביצים מתאימה בעמוד הרשמי; נדרש לוודא שינוי במבנה האתר."
            db.session.commit()
            print(state.last_error)
            return 0

        is_first_run = not state.last_article_url
        is_new = not is_first_run and announcement["url"] != state.last_article_url
        if is_first_run:
            print("Initial baseline established; no notification sent.")
        elif is_new:
            digest = hashlib.sha256(announcement["url"].encode("utf-8")).hexdigest()[:24]
            tenants = db.session.scalars(select(Tenant).where(Tenant.active.is_(True))).all()
            created = 0
            for tenant in tenants:
                users = db.session.scalars(select(User).where(
                    User.tenant_id == tenant.id,
                    User.active.is_(True),
                    User.role.in_((ROLE_ADMIN, ROLE_MANAGER)),
                )).all()
                for user in users:
                    dedupe_key = f"regulated-egg-announcement:{digest}:user:{user.id}"
                    exists = db.session.scalar(select(Notification.id).where(Notification.dedupe_key == dedupe_key).limit(1))
                    if exists:
                        continue
                    db.session.add(Notification(
                        tenant_id=tenant.id,
                        user_id=user.id,
                        title="עדכון ממשלתי חדש בנושא מחירי ביצים",
                        message=f"נמצאה הודעה חדשה באתר משרד החקלאות: {announcement['title']}. יש לבדוק את הצו והמחירים, ולא לעדכן מחירי ספקים אוטומטית.",
                        status=STATUS_UNREAD,
                        action_url=DASHBOARD_PATH,
                        notification_type="regulatory_egg_price_update",
                        dedupe_key=dedupe_key,
                    ))
                    created += 1
            print(f"New official announcement detected; created {created} notification(s).")

        state.last_article_url = announcement["url"]
        state.last_article_title = announcement["title"]
        state.last_published_at = announcement["published_at"]
        db.session.commit()
        return 1 if is_new else 0
    except Exception as exc:
        db.session.rollback()
        state = db.session.get(RegulatoryPriceMonitorState, 1)
        if state is None:
            state = RegulatoryPriceMonitorState(id=1)
            db.session.add(state)
        state.last_checked_at = checked_at
        state.last_error = str(exc)[:500]
        db.session.commit()
        raise


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        print(f"Watcher completed; new announcements: {run_monitor()}.")
