export type ThemePreference = "light" | "dark" | "auto";
export type ResolvedTheme = "light" | "dark";

export const THEME_STORAGE_KEY = "theme";
export const DEFAULT_THEME_PREFERENCE: ThemePreference = "auto";
export const SYSTEM_THEME_QUERY = "(prefers-color-scheme: dark)";

const VALID_THEME_PREFERENCES = new Set<ThemePreference>(["light", "dark", "auto"]);
const THEME_EVENT = "eusrr-theme-change";

function isThemePreference(value: string | null): value is ThemePreference {
  return Boolean(value) && VALID_THEME_PREFERENCES.has(value as ThemePreference);
}

export function getSystemTheme(): ResolvedTheme {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return "light";
  }

  return window.matchMedia(SYSTEM_THEME_QUERY).matches ? "dark" : "light";
}

export function readThemePreference(): ThemePreference {
  if (typeof window === "undefined") {
    return DEFAULT_THEME_PREFERENCE;
  }

  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isThemePreference(stored) ? stored : DEFAULT_THEME_PREFERENCE;
  } catch {
    return DEFAULT_THEME_PREFERENCE;
  }
}

export function resolveTheme(preference: ThemePreference): ResolvedTheme {
  return preference === "auto" ? getSystemTheme() : preference;
}

export function applyTheme(preference: ThemePreference): ResolvedTheme {
  if (typeof document === "undefined") {
    return preference === "dark" ? "dark" : "light";
  }

  const resolved = resolveTheme(preference);
  const root = document.documentElement;
  root.setAttribute("data-bs-theme", resolved);
  root.style.colorScheme = resolved;
  return resolved;
}

export function setThemePreference(preference: ThemePreference): ResolvedTheme {
  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, preference);
    } catch {
      // Ignore storage errors in private mode / blocked storage.
    }
  }

  const resolved = applyTheme(preference);

  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(THEME_EVENT, { detail: { preference, resolved } }));
  }

  return resolved;
}

export function initializeTheme(): { preference: ThemePreference; resolved: ResolvedTheme } {
  const preference = readThemePreference();
  const resolved = applyTheme(preference);
  return { preference, resolved };
}

export function subscribeToThemeChanges(callback: () => void): () => void {
  if (typeof window === "undefined") {
    return () => {};
  }

  const mediaQuery = window.matchMedia?.(SYSTEM_THEME_QUERY);
  const onThemeEvent = () => callback();
  const onStorage = (event: StorageEvent) => {
    if (!event.key || event.key === THEME_STORAGE_KEY) {
      callback();
    }
  };
  const onMediaChange = () => {
    if (readThemePreference() === "auto") {
      applyTheme("auto");
      callback();
    }
  };

  window.addEventListener(THEME_EVENT, onThemeEvent);
  window.addEventListener("storage", onStorage);
  mediaQuery?.addEventListener?.("change", onMediaChange);

  return () => {
    window.removeEventListener(THEME_EVENT, onThemeEvent);
    window.removeEventListener("storage", onStorage);
    mediaQuery?.removeEventListener?.("change", onMediaChange);
  };
}

export function getThemeInitScript(): string {
  return `
    (function () {
      var storageKey = ${JSON.stringify(THEME_STORAGE_KEY)};
      var defaultPreference = ${JSON.stringify(DEFAULT_THEME_PREFERENCE)};
      var valid = { light: true, dark: true, auto: true };
      var root = document.documentElement;
      var preference = defaultPreference;

      try {
        var stored = window.localStorage.getItem(storageKey);
        if (stored && valid[stored]) {
          preference = stored;
        }
      } catch (error) {}

      var isDark = false;
      try {
        isDark = window.matchMedia && window.matchMedia(${JSON.stringify(SYSTEM_THEME_QUERY)}).matches;
      } catch (error) {}

      var resolved = preference === "auto" ? (isDark ? "dark" : "light") : preference;
      root.setAttribute("data-bs-theme", resolved);
      root.style.colorScheme = resolved;
    })();
  `;
}
