const TEMPORARY_ACTION_META = {
  on_leave: {
    className: "text-amber-500",
    label: "В отпуске",
    nonWorking: true,
    priority: 2,
  },
  on_sick_leave: {
    className: "text-amber-500",
    label: "На больничном",
    nonWorking: true,
    priority: 0,
  },
  on_day_off: {
    className: "text-amber-500",
    label: "В отгуле",
    nonWorking: true,
    priority: 3,
  },
  on_maternity: {
    className: "text-amber-500",
    label: "В декрете",
    nonWorking: true,
    priority: 1,
  },
};

const PERMANENT_ACTION_META = {
  dismissed: {
    className: "text-red-400",
    label: "Уволен",
    nonWorking: true,
  },
  remote: {
    className: "text-sky-400",
    label: "На удалёнке",
    nonWorking: false,
  },
};

function dateKey(value) {
  if (!value) return null;
  const stringValue = String(value);
  const isoDate = stringValue.match(/^(\d{4}-\d{2}-\d{2})/);
  if (isoDate) return isoDate[1];

  const date = new Date(stringValue);
  if (Number.isNaN(date.getTime())) return null;

  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function actionTimestamp(action) {
  const date = new Date(action.date);
  return Number.isNaN(date.getTime()) ? 0 : date.getTime();
}

function actionId(action) {
  return Number(action.id || 0);
}

function actionLabel(action, fallback) {
  return action.action_display || fallback;
}

function metaFromAction(action, meta) {
  return {
    action,
    className: meta.className,
    label: actionLabel(action, meta.label),
    nonWorking: meta.nonWorking,
  };
}

function metaFromRecord(record, dateValue) {
  if (!record?.personnel_status || record.personnel_status === "normal") {
    return null;
  }

  const personnelStatus = String(record.personnel_status);
  return {
    action: {
      id: Number(record.personnel_action || 0),
      employee: 0,
      action: personnelStatus,
      action_display: record.personnel_status_label || record.personnel_status,
      date: String(dateValue || ""),
    },
    className: personnelStatus === "dismissed"
      ? "text-red-400"
      : personnelStatus === "remote"
        ? "text-sky-400"
        : "text-amber-500",
    label: record.personnel_status_label || record.personnel_status,
    nonWorking: record.effective_is_workday === false,
  };
}

function activeTemporaryAction(actions, targetDateKey) {
  return actions
    .filter((action) => {
      const meta = TEMPORARY_ACTION_META[action.action];
      if (!meta) return false;

      const from = dateKey(action.date);
      if (!from || from > targetDateKey) return false;

      const to = dateKey(action.date_to) || from;
      return to >= targetDateKey;
    })
    .sort((left, right) => {
      const leftMeta = TEMPORARY_ACTION_META[left.action];
      const rightMeta = TEMPORARY_ACTION_META[right.action];
      return (
        leftMeta.priority - rightMeta.priority
        || actionTimestamp(right) - actionTimestamp(left)
        || actionId(right) - actionId(left)
      );
    })[0] || null;
}

function latestRelevantAction(actions, targetDateKey) {
  return actions
    .filter((action) => {
      const from = dateKey(action.date);
      return Boolean(from && from <= targetDateKey);
    })
    .sort((left, right) => (
      actionTimestamp(right) - actionTimestamp(left)
      || actionId(right) - actionId(left)
    ))[0] || null;
}

export function getPersonnelDayMeta(actions, dateValue, record) {
  const recordMeta = metaFromRecord(record, dateValue);
  if (recordMeta) return recordMeta;

  if (!actions?.length) return null;

  const targetDateKey = dateKey(dateValue);
  if (!targetDateKey) return null;

  const temporaryAction = activeTemporaryAction(actions, targetDateKey);
  if (temporaryAction) {
    return metaFromAction(
      temporaryAction,
      TEMPORARY_ACTION_META[temporaryAction.action],
    );
  }

  const permanentAction = latestRelevantAction(actions, targetDateKey);
  if (permanentAction && PERMANENT_ACTION_META[permanentAction.action]) {
    return metaFromAction(
      permanentAction,
      PERMANENT_ACTION_META[permanentAction.action],
    );
  }

  return null;
}
