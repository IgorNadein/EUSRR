export function extractDepartmentApiErrorMessage(error, fallback) {
  const raw = String(error?.message || fallback || "").trim();
  const prefix = "API Error:";
  if (!raw.startsWith(prefix)) return raw || fallback;

  const payload = raw.slice(prefix.length).trim();
  const jsonStart = payload.indexOf("{");
  if (jsonStart >= 0) {
    try {
      const parsed = JSON.parse(payload.slice(jsonStart));
      const detail = parsed.detail;
      if (typeof detail === "string" && detail.trim()) return detail;
      const firstEntry = Object.entries(parsed)[0];
      if (firstEntry) {
        const value = firstEntry[1];
        if (Array.isArray(value) && value[0]) return String(value[0]);
        if (typeof value === "string" && value.trim()) return value;
      }
    } catch {
      return fallback;
    }
  }

  const plainMessage = payload.replace(/^\d+\s+/, "").trim();
  if (/^\d+$/.test(plainMessage || payload)) {
    return fallback;
  }
  return plainMessage || fallback;
}
