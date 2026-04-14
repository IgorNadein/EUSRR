export type MobileNavPlacement = "top" | "bottom";

export const MOBILE_NAV_PLACEMENT_STORAGE_KEY = "mobile-nav-placement";
export const DEFAULT_MOBILE_NAV_PLACEMENT: MobileNavPlacement = "top";

const VALID_MOBILE_NAV_PLACEMENTS = new Set<MobileNavPlacement>(["top", "bottom"]);
const MOBILE_NAV_PLACEMENT_EVENT = "eusrr-mobile-nav-placement-change";

function isMobileNavPlacement(value: string | null): value is MobileNavPlacement {
  return Boolean(value) && VALID_MOBILE_NAV_PLACEMENTS.has(value as MobileNavPlacement);
}

export function readMobileNavPlacementPreference(): MobileNavPlacement {
  if (typeof window === "undefined") {
    return DEFAULT_MOBILE_NAV_PLACEMENT;
  }

  try {
    const stored = window.localStorage.getItem(MOBILE_NAV_PLACEMENT_STORAGE_KEY);
    return isMobileNavPlacement(stored) ? stored : DEFAULT_MOBILE_NAV_PLACEMENT;
  } catch {
    return DEFAULT_MOBILE_NAV_PLACEMENT;
  }
}

export function applyMobileNavPlacement(preference: MobileNavPlacement): MobileNavPlacement {
  if (typeof document === "undefined") {
    return preference;
  }

  document.documentElement.setAttribute("data-mobile-nav-placement", preference);
  return preference;
}

export function setMobileNavPlacementPreference(preference: MobileNavPlacement): MobileNavPlacement {
  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(MOBILE_NAV_PLACEMENT_STORAGE_KEY, preference);
    } catch {
      // Ignore storage failures.
    }
  }

  applyMobileNavPlacement(preference);

  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(MOBILE_NAV_PLACEMENT_EVENT, { detail: { preference } }));
  }

  return preference;
}

export function initializeMobileNavPlacement(): MobileNavPlacement {
  const preference = readMobileNavPlacementPreference();
  applyMobileNavPlacement(preference);
  return preference;
}

export function subscribeToMobileNavPlacementChanges(callback: () => void): () => void {
  if (typeof window === "undefined") {
    return () => {};
  }

  const onPlacementEvent = () => callback();
  const onStorage = (event: StorageEvent) => {
    if (!event.key || event.key === MOBILE_NAV_PLACEMENT_STORAGE_KEY) {
      callback();
    }
  };

  window.addEventListener(MOBILE_NAV_PLACEMENT_EVENT, onPlacementEvent);
  window.addEventListener("storage", onStorage);

  return () => {
    window.removeEventListener(MOBILE_NAV_PLACEMENT_EVENT, onPlacementEvent);
    window.removeEventListener("storage", onStorage);
  };
}

export function getMobileNavPlacementInitScript(): string {
  return `
    (function () {
      var storageKey = ${JSON.stringify(MOBILE_NAV_PLACEMENT_STORAGE_KEY)};
      var defaultPreference = ${JSON.stringify(DEFAULT_MOBILE_NAV_PLACEMENT)};
      var valid = { top: true, bottom: true };
      var root = document.documentElement;
      var preference = defaultPreference;

      try {
        var stored = window.localStorage.getItem(storageKey);
        if (stored && valid[stored]) {
          preference = stored;
        }
      } catch (error) {}

      root.setAttribute("data-mobile-nav-placement", preference);
    })();
  `;
}
