type NotificationNavigationLike = {
  action_url?: string | null;
  verb?: string | null;
  category?: string | null;
  data?: Record<string, unknown> | null;
};

export function resolveNotificationActionUrl(
  notification: NotificationNavigationLike,
): string | null {
  const rawRequestId = notification.data?.request_id;
  const requestId = typeof rawRequestId === "number"
    ? rawRequestId
    : typeof rawRequestId === "string" && rawRequestId.trim()
      ? Number(rawRequestId)
      : null;

  const categoryHint = `${notification.verb || ""} ${notification.category || ""}`.toLowerCase();
  if (requestId && Number.isFinite(requestId) && categoryHint.includes("procurement")) {
    return `/procurement?request=${requestId}`;
  }

  return notification.action_url || null;
}
