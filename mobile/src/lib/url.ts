import { Platform } from 'react-native';

/**
 * URL helpers for the editable server target.
 * The default targets the Flask dev server (`python app.py`, port 5000):
 *  - Android emulator reaches the host machine via 10.0.2.2
 *  - iOS simulator can use localhost directly
 */
export const DEFAULT_BASE_URL = Platform.select({
  android: 'http://10.0.2.2:5000',
  default: 'http://localhost:5000',
}) as string;

export const LAN_HINT = 'http://<your-lan-ip>:5000';

/**
 * Normalizes a user-entered base URL:
 *  - trims whitespace
 *  - prepends http:// when the scheme is missing
 *  - strips trailing slashes (keeps any path prefix)
 * Returns null when the value can't be parsed as a URL.
 */
export function normalizeBaseUrl(raw: string): string | null {
  let value = raw.trim();
  if (!value) return null;
  if (!/^https?:\/\//i.test(value)) value = `http://${value}`;
  try {
    const url = new URL(value);
    if (!url.hostname) return null;
    const path = url.pathname.replace(/\/+$/, '');
    return `${url.protocol}//${url.host}${path === '/' ? '' : path}`;
  } catch {
    return null;
  }
}

/** "http://10.0.2.2:5000/settings" → "10.0.2.2:5000" */
export function hostOf(url: string): string {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}
