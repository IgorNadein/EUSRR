export function getDepartmentMembersListClassName(isManagementMode: boolean) {
  return isManagementMode
    ? "space-y-3"
    : "flex flex-wrap items-center gap-2";
}

export const DEPARTMENT_MEMBERS_EMPTY_STATE_CLASSNAME =
  "app-surface-muted w-full rounded-xl p-8 text-center";
