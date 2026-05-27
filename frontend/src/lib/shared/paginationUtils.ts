/**
 * Shared pagination helpers.
 */

export function extractNextPage(nextUrl?: string | null): number | null {
  if (!nextUrl) return null;
  try {
    const parsed = new URL(nextUrl, typeof window !== "undefined" ? window.location.origin : "http://localhost");
    const num = Number(parsed.searchParams.get("page"));
    return Number.isFinite(num) && num > 0 ? num : null;
  } catch {
    return null;
  }
}

type PageFetcher<T> = (params: Record<string, number>) => Promise<{ results?: T[]; next?: string | null } | T[]>;

export async function loadAllPages<T extends { id: number }>(fetcher: PageFetcher<T>): Promise<T[]> {
  const all: T[] = [];
  let page = 1;
  for (;;) {
    const res = await fetcher({ page, page_size: 200, limit: 200 });
    const results = Array.isArray(res) ? res : (res.results || []);
    all.push(...results);
    if (Array.isArray(res) || !(res as { next?: string | null }).next) break;
    page++;
  }
  return all;
}
