type NotificationNavigationLike = {
  action_url?: string | null;
  verb?: string | null;
  category?: string | null;
  data?: Record<string, unknown> | null;
};

function parseNumericId(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  return null;
}

function buildUrl(pathname: string, params: Record<string, number | null>): string {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== null) {
      searchParams.set(key, String(value));
    }
  });

  const query = searchParams.toString();
  return query ? `${pathname}?${query}` : pathname;
}

function normalizeRawActionUrl(rawActionUrl: string): string {
  try {
    const url = new URL(rawActionUrl, "http://localhost");
    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return rawActionUrl;
  }
}

export function resolveNotificationActionUrl(
  notification: NotificationNavigationLike,
): string | null {
  const data = notification.data && typeof notification.data === "object"
    ? notification.data
    : null;

  const requestId = parseNumericId(data?.request_id);
  const documentId = parseNumericId(data?.document_id);
  const eventId = parseNumericId(data?.event_id);
  const postId = parseNumericId(data?.post_id);
  const chatId = parseNumericId(data?.chat_id);
  const messageId = parseNumericId(data?.message_id);
  const objectId = parseNumericId(data?.object_id);
  const objectType = typeof data?.object_type === "string"
    ? data.object_type.toLowerCase()
    : "";
  const categoryHint = [
    notification.verb || "",
    notification.category || "",
    objectType,
  ].join(" ").toLowerCase();

  if (requestId !== null && categoryHint.includes("procurement")) {
    return buildUrl("/procurement", { request: requestId });
  }

  if (
    requestId !== null && (
      categoryHint.includes("request")
      || objectType === "request"
    )
  ) {
    return buildUrl("/requests", { request: requestId });
  }

  if (
    documentId !== null && (
      categoryHint.includes("document")
      || objectType === "document"
    )
  ) {
    return buildUrl("/documents", { document: documentId });
  }

  if (eventId !== null && categoryHint.includes("event")) {
    return buildUrl("/calendar", { event: eventId });
  }

  if (
    postId !== null && (
      categoryHint.includes("feed")
      || categoryHint.includes("post")
      || objectType === "post"
    )
  ) {
    return buildUrl("/", { post: postId });
  }

  if (chatId !== null) {
    return buildUrl(`/messages/${chatId}`, { message: messageId });
  }

  if (objectId !== null) {
    if (objectType === "post") {
      return buildUrl("/", { post: objectId });
    }
    if (objectType === "document") {
      return buildUrl("/documents", { document: objectId });
    }
    if (objectType === "request") {
      return buildUrl("/requests", { request: objectId });
    }
  }

  const rawActionUrl = typeof notification.action_url === "string"
    ? normalizeRawActionUrl(notification.action_url.trim())
    : "";

  if (rawActionUrl) {
    const url = new URL(rawActionUrl, "http://localhost");

    if (url.pathname === "/procurement") {
      const rawProcurementRequestId = parseNumericId(url.searchParams.get("request"));
      return buildUrl("/procurement", { request: rawProcurementRequestId });
    }

    if (url.pathname === "/requests") {
      const rawLinkedRequestId = parseNumericId(
        url.searchParams.get("request") ?? url.searchParams.get("id"),
      );
      return buildUrl("/requests", { request: rawLinkedRequestId });
    }

    if (url.pathname === "/documents") {
      const rawLinkedDocumentId = parseNumericId(
        url.searchParams.get("document") ?? url.searchParams.get("id"),
      );
      return buildUrl("/documents", { document: rawLinkedDocumentId });
    }

    if (url.pathname === "/calendar") {
      const rawLinkedEventId = parseNumericId(url.searchParams.get("event"));
      return buildUrl("/calendar", { event: rawLinkedEventId });
    }

    if (url.pathname === "/") {
      const rawLinkedPostId = parseNumericId(url.searchParams.get("post"));
      return buildUrl("/", { post: rawLinkedPostId });
    }
  }

  const requestMatch = rawActionUrl.match(/^\/requests\/(\d+)\/?(?:[#?].*)?$/);
  if (requestMatch) {
    return buildUrl("/requests", { request: Number(requestMatch[1]) });
  }

  const documentMatch = rawActionUrl.match(/^\/documents\/(\d+)\/?(?:[#?].*)?$/);
  if (documentMatch) {
    return buildUrl("/documents", { document: Number(documentMatch[1]) });
  }

  const calendarMatch = rawActionUrl.match(/^\/calendar\/events\/(\d+)\/?(?:[#?].*)?$/);
  if (calendarMatch) {
    return buildUrl("/calendar", { event: Number(calendarMatch[1]) });
  }

  const feedPathMatch = rawActionUrl.match(/^\/feed\/(?:posts?\/)?(\d+)\/?(?:[#?].*)?$/);
  if (feedPathMatch) {
    return buildUrl("/", { post: Number(feedPathMatch[1]) });
  }

  const feedHashMatch = rawActionUrl.match(/^\/feed\/?#(\d+)$/);
  if (feedHashMatch) {
    return buildUrl("/", { post: Number(feedHashMatch[1]) });
  }

  return rawActionUrl || null;
}
