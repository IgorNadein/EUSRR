"""Calendar API v2 Views."""
from api.v1.calendar.views import (
    CalendarEventsViewSet as V1CalendarEventsViewSet,
    CalendarSubscriptionViewSet as V1CalendarSubscriptionViewSet,
    CalendarViewSet as V1CalendarViewSet,
)


class CalendarEventsViewSet(V1CalendarEventsViewSet):
    """API v2 для событий календаря."""
    pass


class CalendarViewSet(V1CalendarViewSet):
    """API v2 для календарей."""
    pass


class CalendarSubscriptionViewSet(V1CalendarSubscriptionViewSet):
    """API v2 для подписок на календари."""
    pass
