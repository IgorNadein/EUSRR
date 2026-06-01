/** Helper to build URL query string from params object */
export function buildQuery(params?: Record<string, string | number | boolean | undefined | null>): string {
    if (!params) return '';
    const qp = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
            qp.append(key, String(value));
        }
    });
    const qs = qp.toString();
    return qs ? `?${qs}` : '';
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type RequestFn = (endpoint: string, options?: RequestInit) => Promise<any>;
export type RawRequestFn = (endpoint: string, options?: RequestInit) => Promise<Response>;
export type GetTokenFn = () => string | null;
