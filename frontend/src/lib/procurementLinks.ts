export const toLinkRows = (links?: string[] | null): string[] => {
  const rows = Array.isArray(links)
    ? links.map((link) => String(link || "").trim()).filter(Boolean)
    : [];
  return rows.length > 0 ? rows : [""];
};

export const cleanLinkRows = (links: string[]): string[] => (
  links.map((link) => link.trim()).filter(Boolean)
);

export const linkHref = (link: string): string => (
  /^https?:\/\//i.test(link) ? link : `https://${link}`
);

export const validateLinkRows = (links: string[], label = "Ссылка"): string | null => {
  const cleaned = cleanLinkRows(links);

  for (let index = 0; index < cleaned.length; index += 1) {
    const value = cleaned[index];
    const displayIndex = cleaned.length > 1 ? ` ${index + 1}` : "";

    if ((value.match(/https?:\/\//gi) || []).length > 1) {
      return `${label}${displayIndex}: вставьте каждую ссылку в отдельное поле.`;
    }

    try {
      const url = new URL(value);
      if (!["http:", "https:"].includes(url.protocol) || !url.hostname.includes(".")) {
        return `${label}${displayIndex}: укажите корректный URL с http:// или https://.`;
      }
    } catch {
      return `${label}${displayIndex}: укажите корректный URL с http:// или https://.`;
    }
  }

  return null;
};
