import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { BrandMark } from './BrandMark';
import { chromeDark, font, radius, status } from '../theme';

/**
 * Top chrome — replicates the web app's dark brand header (h-16, sidebar bg
 * #0c0c12, hairline divider): gradient scissors mark, "AuraPOS" wordmark with
 * a tier-style badge, host subtitle, and right-aligned status/actions.
 * The chrome stays dark in both schemes, exactly like the web sidebar.
 */
interface Props {
  host: string;
  loading: boolean;
  offline: boolean;
  /** Status-bar inset from react-native-safe-area-context (iPhone notch). */
  topInset?: number;
  onReload: () => void;
  onEditUrl: () => void;
}

export function HeaderBar({ host, loading, offline, topInset = 0, onReload, onEditUrl }: Props) {
  return (
    <View style={[styles.bar, { paddingTop: topInset, height: 64 + topInset }]}>
      <View style={styles.brandRow}>
        <BrandMark size={34} iconSize={17} />
        <View style={styles.brandCol}>
          <View style={styles.nameRow}>
            <Text style={styles.name}>AuraPOS</Text>
            {/* Tier-badge replica: text-[10px] pill, emerald soft bg + border */}
            <View style={styles.badge}>
              <Text style={styles.badgeText}>MOBILE</Text>
            </View>
          </View>
          <Text style={styles.host} numberOfLines={1}>
            {host || 'not connected'}
          </Text>
        </View>
      </View>

      <View style={styles.actions}>
        {loading ? (
          <ActivityIndicator size="small" color={status.cyan} style={styles.spinner} />
        ) : (
          <View
            style={[
              styles.dot,
              { backgroundColor: offline ? status.rose : status.emerald },
            ]}
          />
        )}
        <IconButton icon="refresh-cw" onPress={onReload} />
        <IconButton icon="settings" onPress={onEditUrl} />
      </View>
    </View>
  );
}

function IconButton({ icon, onPress }: { icon: keyof typeof Feather.glyphMap; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      hitSlop={8}
      style={({ pressed }) => [styles.iconBtn, pressed && { opacity: 0.6 }]}
    >
      <Feather name={icon} size={17} color={chromeDark.subtext} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  bar: {
    height: 64, // h-16
    backgroundColor: chromeDark.bg, // dark:bg-[#0c0c12]
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: chromeDark.border,
    paddingHorizontal: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  brandRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    flexShrink: 1,
  },
  brandCol: {
    flexShrink: 1,
  },
  nameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  name: {
    color: chromeDark.text,
    fontFamily: font.bold,
    fontSize: 16,
    letterSpacing: -0.3, // tracking-tight
  },
  badge: {
    backgroundColor: 'rgba(16,185,129,0.10)', // bg-emerald-500/10
    borderColor: 'rgba(16,185,129,0.20)', // border-emerald-500/20
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.badge,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  badgeText: {
    color: '#34d399', // emerald-400 (dark:text-emerald-400)
    fontFamily: font.semibold,
    fontSize: 9,
    letterSpacing: 0.5,
  },
  host: {
    color: chromeDark.subtext,
    fontFamily: font.mono,
    fontSize: 10.5,
    marginTop: 1,
  },
  actions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  spinner: {
    marginRight: 6,
  },
  dot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    marginRight: 8,
  },
  iconBtn: {
    padding: 8,
    borderRadius: 8,
  },
});
