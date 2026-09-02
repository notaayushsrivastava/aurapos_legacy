/**
 * AuraPOS Mobile — design tokens extracted from the AuraPOS web app
 * (templates/layout.html + tailwind.config.js).
 *
 * Brand gradient (sidebar logo / primary CTA):
 *   from-neon-magenta via-violet-600 to-neon-cyan
 *   #f72585 → #7c3aed → #00f5d4
 */

export type Scheme = 'light' | 'dark';

export const neon = {
  cyan: '#00f5d4',
  magenta: '#f72585',
  violet: '#7b2cbf',
  emerald: '#10b981',
  amber: '#f59e0b',
} as const;

/** violet-600 — the light-mode accent used across the web app */
export const violet600 = '#7c3aed';

/** Status colors mirroring the web toast palette (layout.html flash messages) */
export const status = {
  rose: '#f43f5e', // rose-500  — error
  emerald: '#10b981', // emerald-500 — success / online
  amber: '#f59e0b', // amber-500 — warning / loading
  cyan: '#06b6d4', // cyan-500  — info
} as const;

export interface ThemeColors {
  bg: string; // page background (body)
  card: string; // card / sheet surface
  cardBorder: string; // 1px card border
  hairline: string; // subtle dividers (neutral-800/80 style)
  text: string; // primary text
  subtext: string; // secondary text (neutral-600 / neutral-300)
  muted: string; // tertiary text (neutral-400 / neutral-500)
  faint: string; // disabled icons (neutral-300 / neutral-700)
  accent: string; // light: violet-600 · dark: neon-cyan (dark:text-neon-cyan)
  accentSoft: string; // soft tint behind accent icon chips
  inputBg: string; // input wells
}

export const lightColors: ThemeColors = {
  bg: '#fafafa', // bg-neutral-50
  card: '#ffffff', // bg-white
  cardBorder: '#e5e5e5', // border-neutral-200
  hairline: 'rgba(229,229,229,0.8)', // border-neutral-200/80
  text: '#171717', // text-neutral-900
  subtext: '#525252', // text-neutral-600
  muted: '#a3a3a3', // text-neutral-400
  faint: '#d4d4d4', // text-neutral-300
  accent: violet600, // text-violet-600
  accentSoft: 'rgba(124,58,237,0.10)', // bg-violet-50 / violet-500/10
  inputBg: '#f5f5f5', // bg-neutral-100
};

export const darkColors: ThemeColors = {
  bg: '#050508', // dark:bg-[#050508]
  card: '#0c0c12', // dark:bg-[#0c0c12] (sidebar / cards)
  cardBorder: '#262626', // border-neutral-800
  hairline: 'rgba(38,38,38,0.8)', // border-neutral-800/80
  text: '#f5f5f5', // dark:text-neutral-100
  subtext: '#d4d4d4', // text-neutral-300
  muted: '#a3a3a3',
  faint: '#404040', // text-neutral-700 (excluded X icons)
  accent: neon.cyan, // dark:text-neon-cyan
  accentSoft: 'rgba(0,245,212,0.10)', // bg-violet-500/10 → cyan equivalent
  inputBg: '#050508',
};

export const colorsFor = (scheme: Scheme): ThemeColors =>
  scheme === 'dark' ? darkColors : lightColors;

/** Brand header on the web is a dark surface in BOTH themes (sidebar bg). */
export const chromeDark = {
  bg: '#0c0c12',
  border: 'rgba(38,38,38,0.8)',
  text: '#ffffff',
  subtext: '#a3a3a3',
};

export const radius = {
  card: 24, // rounded-3xl
  btn: 12, // rounded-xl
  chip: 12, // icon chip (w-9 h-9 rounded-xl)
  badge: 4, // tier badge (rounded)
  input: 12, // rounded-xl inputs
} as const;

export const font = {
  regular: 'PlusJakartaSans_400Regular',
  medium: 'PlusJakartaSans_500Medium',
  semibold: 'PlusJakartaSans_600SemiBold',
  bold: 'PlusJakartaSans_700Bold',
  extrabold: 'PlusJakartaSans_800ExtraBold',
  mono: 'JetBrainsMono_400Regular',
  monoMedium: 'JetBrainsMono_500Medium',
} as const;

/** Entrance animation constants mirroring data-anim="up" (anime.js reveal). */
export const motion = {
  distance: 14,
  duration: 420,
  stagger: 90,
  easing: 'cubic-bezier(0.22, 1, 0.36, 1)',
} as const;
