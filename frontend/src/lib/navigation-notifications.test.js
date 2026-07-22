import test from "node:test";
import assert from "node:assert/strict";

import { NAV_NOTIFICATION_CATEGORIES } from "./navigation-notifications.ts";
import { getVerbCategory } from "./verbTranslations.ts";

const notificationSamples = [
  ["feed", "feed_new_post"],
  ["messages", "chat_new_message"],
  ["requests", "request_new"],
  ["guests", "guest_visit_submitted"],
  ["procurement", "procurement_new_request"],
  ["tasks", "task_assigned"],
  ["documents", "document_ready"],
  ["regulations", "regulation_ready"],
];

test("navigation badges use the same categories as notification verbs", () => {
  for (const [navigationKey, verb] of notificationSamples) {
    assert.equal(
      NAV_NOTIFICATION_CATEGORIES[navigationKey],
      getVerbCategory(verb),
      `${verb} must update the ${navigationKey} navigation badge`,
    );
  }
});
