import { useEffect, useRef } from 'react';
import { Animated, Easing, Pressable, StyleSheet, Text, View, type StyleProp, type ViewStyle } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Feather } from '@expo/vector-icons';
import { BrandMark } from './BrandMark';
import { colorsFor, font, motion, radius, status, type Scheme, type ThemeColors } from '../theme';

export type ErrorKind = 'offline' | 'dns' | 'network' | 'http' | 'crash';

export interface LoadError {
  kind: ErrorKind;
  statusCode?: number;
  description?: string;
  url?: string;
}

interface Copy {
  label: string;
  title: string;
  body: string;
  icon: keyof typeof Feather.glyphMap;
  tone: string; // icon color
  chipBg: string; // soft icon-chip background
}

function copyFor(err: LoadError, t: ThemeColors): Copy {
  switch (err.kind) {
    case 'offline':
      return {
        label: 'No Connection',
        title: "You're offline",
        body: 'AuraPOS needs the internet to reach your salon server. Reconnect and it will pick up right where you left off.',
        icon: 'wifi-off',
        tone: status.amber,
        chipBg: 'rgba(245,158,11,0.12)',
      };
    case 'dns':
      return {
        label: 'DNS Lookup Failed',
        title: 'Server not found',
        body: "We couldn't resolve the address below. It may be a typo — check the server URL, or confirm the dev server is running.",
        icon: 'globe',
        tone: t.accent,
        chipBg: t.accentSoft,
      };
    case 'http':
      return {
        label: `HTTP ${err.statusCode ?? 'Error'}`,
        title: err.statusCode && err.statusCode >= 500 ? 'Server error' : 'Request rejected',
        body: `The server responded with HTTP ${err.statusCode ?? '??'}. If this keeps happening, check the Flask console for a traceback.`,
        icon: 'alert-triangle',
        tone: status.rose,
        chipBg: 'rgba(244,63,94,0.12)',
      };
    case 'crash':
      return {
        label: 'Renderer Crashed',
        title: 'Page crashed',
        body: 'The page ran out of memory or crashed unexpectedly. Reloading usually fixes it.',
        icon: 'alert-octagon',
        tone: status.rose,
        chipBg: 'rgba(244,63,94,0.12)',
      };
    default:
      return {
        label: 'Connection Failed',
        title: "Can't reach the server",
        body: 'The server refused the connection or timed out. It may be offline, asleep, or running on a different port.',
        icon: 'server',
        tone: status.rose,
        chipBg: 'rgba(244,63,94,0.12)',
      };
  }
}

/** Fade + rise entrance, mirroring the web app's data-anim="up" reveal. */
function Reveal({ delay, style, children }: { delay: number; style?: StyleProp<ViewStyle>; children: React.ReactNode }) {
  const anim = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.timing(anim, {
      toValue: 1,
      duration: motion.duration,
      delay,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    }).start();
  }, [anim, delay]);
  return (
    <Animated.View
      style={[
        style,
        {
          opacity: anim,
          transform: [{ translateY: anim.interpolate({ inputRange: [0, 1], outputRange: [motion.distance, 0] }) }],
        },
      ]}
    >
      {children}
    </Animated.View>
  );
}

/** Soft-breathing dot for the auto-reconnect hint (offline mode). */
function PulseDot({ color }: { color: string }) {
  const pulse = useRef(new Animated.Value(0.35)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 900, easing: Easing.inOut(Easing.quad), useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0.35, duration: 900, easing: Easing.inOut(Easing.quad), useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [pulse]);
  return (
    <View style={styles.pulseWrap}>
      <Animated.View style={[styles.pulseHalo, { opacity: pulse, backgroundColor: color }]} />
      <View style={[styles.pulseCore, { backgroundColor: color }]} />
    </View>
  );
}

interface Props {
  error: LoadError;
  scheme: Scheme;
  /** True when this is the proactive offline gate (WebView was never mounted). */
  proactiveOffline?: boolean;
  onRetry: () => void;
  onEditUrl?: () => void;
}

export function ErrorFallback({ error, scheme, proactiveOffline = false, onRetry, onEditUrl }: Props) {
  const t = colorsFor(scheme);
  const c = copyFor(error, t);

  const detail =
    error.kind === 'http'
      ? error.description?.trim() || `HTTP ${error.statusCode}`
      : error.description?.trim() || undefined;

  return (
    <View style={[styles.screen, { backgroundColor: t.bg }]}>
      <Reveal delay={0} style={styles.brandWrap}>
        <BrandMark size={40} iconSize={20} />
      </Reveal>

      <Reveal delay={motion.stagger} style={styles.cardWrap}>
        <View style={[styles.card, { backgroundColor: t.card, borderColor: t.cardBorder }]}>
          {/* Icon chip — mirrors the web w-9 h-9 rounded-xl icon tiles */}
          <View style={[styles.iconChip, { backgroundColor: c.chipBg }]}>
            <Feather name={c.icon} size={22} color={c.tone} />
          </View>

          {/* Micro label — mirrors text-[10px] uppercase tracking-wider headers */}
          <Text style={[styles.label, { color: t.muted }]}>{c.label.toUpperCase()}</Text>

          <Text style={[styles.title, { color: t.text }]}>{c.title}</Text>
          <Text style={[styles.body, { color: t.subtext }]}>{c.body}</Text>

          {error.url ? (
            <View style={[styles.urlChip, { borderColor: t.hairline, backgroundColor: t.inputBg }]}>
              <Feather name="link" size={11} color={t.muted} />
              <Text style={[styles.urlText, { color: t.subtext }]} numberOfLines={1}>
                {error.url}
              </Text>
            </View>
          ) : null}

          {detail ? (
            <Text style={[styles.detail, { color: t.muted }]} numberOfLines={2}>
              {detail}
            </Text>
          ) : null}

          {/* Primary CTA — magenta→violet→cyan gradient, like the web Quick Sale button */}
          <LinearGradient
            colors={['#f72585', '#7c3aed', '#00f5d4']}
            start={{ x: 0, y: 0.5 }}
            end={{ x: 1, y: 0.5 }}
            style={styles.primaryGradient}
          >
            <Pressable
              onPress={onRetry}
              android_ripple={{ color: 'rgba(255,255,255,0.25)' }}
              style={({ pressed }) => [styles.primaryBtn, pressed && { opacity: 0.9, transform: [{ scale: 0.98 }] }]}
            >
              <Feather name="refresh-cw" size={14} color="#ffffff" />
              <Text style={styles.primaryText}>Try Again</Text>
            </Pressable>
          </LinearGradient>

          {onEditUrl ? (
            <Pressable
              onPress={onEditUrl}
              style={({ pressed }) => [styles.secondaryBtn, { borderColor: t.cardBorder }, pressed && { opacity: 0.7 }]}
            >
              <Feather name="settings" size={14} color={t.subtext} />
              <Text style={[styles.secondaryText, { color: t.subtext }]}>Edit Server URL</Text>
            </Pressable>
          ) : null}
        </View>
      </Reveal>

      <Reveal delay={motion.stagger * 2} style={styles.footer}>
        {proactiveOffline ? (
          <View style={styles.reconnectRow}>
            <PulseDot color={status.emerald} />
            <Text style={[styles.footerText, { color: t.muted }]}>Reconnecting automatically…</Text>
          </View>
        ) : (
          <Text style={[styles.footerText, { color: t.muted }]}>AuraPOS Mobile · your data lives on your server</Text>
        )}
      </Reveal>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  brandWrap: {
    marginBottom: 20,
  },
  cardWrap: {
    width: '100%',
    maxWidth: 360,
  },
  card: {
    borderRadius: radius.card, // rounded-3xl
    borderWidth: StyleSheet.hairlineWidth,
    padding: 24,
    alignItems: 'center',
  },
  iconChip: {
    width: 48,
    height: 48,
    borderRadius: radius.chip,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 14,
  },
  label: {
    fontFamily: font.semibold,
    fontSize: 10,
    letterSpacing: 1.4,
    marginBottom: 6,
  },
  title: {
    fontFamily: font.extrabold,
    fontSize: 20,
    letterSpacing: -0.3, // tracking-tight
    marginBottom: 8,
  },
  body: {
    fontFamily: font.regular,
    fontSize: 12.5,
    lineHeight: 19,
    textAlign: 'center',
    marginBottom: 16,
  },
  urlChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    borderRadius: 8,
    borderWidth: StyleSheet.hairlineWidth,
    paddingHorizontal: 10,
    paddingVertical: 7,
    marginBottom: 10,
    maxWidth: '100%',
  },
  urlText: {
    fontFamily: font.mono,
    fontSize: 11,
    flexShrink: 1,
  },
  detail: {
    fontFamily: font.mono,
    fontSize: 10,
    marginBottom: 16,
    textAlign: 'center',
  },
  primaryGradient: {
    width: '100%',
    borderRadius: radius.btn,
    overflow: 'hidden',
    marginTop: 4,
  },
  primaryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    width: '100%',
    paddingVertical: 13,
  },
  primaryText: {
    color: '#ffffff',
    fontFamily: font.bold,
    fontSize: 13,
  },
  secondaryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    width: '100%',
    borderRadius: radius.btn,
    borderWidth: StyleSheet.hairlineWidth,
    paddingVertical: 12,
    marginTop: 10,
  },
  secondaryText: {
    fontFamily: font.semibold,
    fontSize: 12.5,
  },
  footer: {
    marginTop: 22,
    alignItems: 'center',
  },
  reconnectRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  footerText: {
    fontFamily: font.regular,
    fontSize: 11,
    textAlign: 'center',
  },
  pulseWrap: {
    width: 10,
    height: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  pulseHalo: {
    position: 'absolute',
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  pulseCore: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
});


