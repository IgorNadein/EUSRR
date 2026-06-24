const toDateOnlyTime = (value?: string | null): number | null => {
  if (!value) return null;
  const match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return null;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) return null;

  const date = new Date(year, month - 1, day);
  date.setHours(0, 0, 0, 0);
  return date.getTime();
};

export const getExpectedDeliveryDateBadgeClass = (
  value?: string | null,
  isFullyReceived = false,
): string => {
  if (isFullyReceived) return "app-badge";

  const dateTime = toDateOnlyTime(value);
  if (dateTime === null) return "app-badge";

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const todayTime = today.getTime();

  if (dateTime < todayTime) return "app-feedback-danger";
  if (dateTime === todayTime) return "app-feedback-warning";
  return "app-badge";
};
