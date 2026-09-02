import { useEffect, useState } from 'react';
import {
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Feather } from '@expo/vector-icons';
import { DEFAULT_BASE_URL, LAN_HINT, normalizeBaseUrl } from '../lib/url';
import { colorsFor, font, radius, status, type Scheme, type ThemeColors } from '../theme';

interface Preset {
  label: string;
  url: string;
}

const PRESETS: Preset[] = [
  { label: 'Android emulator', url: 'http://10.0.2.2:5000' },
  { label: 'Localhost', url: 'http://localhost:5000' },
];

interface Props {
  visible: boolean;
  scheme: Scheme;
  currentUrl: string | null;
  onClose: () => void;
  onSave: (url: string) => void;
}

/**
 * Bottom sheet for editing the AuraPOS server URL — the testing escape hatch.
 * Themed after the web app's modals: rounded-3xl surface, micro-uppercase
 * field labels, mono input, accent primary action.
 */
export function UrlSheet({ visible, scheme, currentUrl, onClose, onSave }: Props) {
  const t: ThemeColors = colorsFor(scheme);
  const [draft, setDraft] = useState('');
  const [touched, setTouched] = useState(false);

  useEffect(() => {
    if (visible) {
      setDraft(currentUrl ?? DEFAULT_BASE_URL);
      setTouched(false);
    }
  }, [visible, currentUrl]);

  const parsed = normalizeBaseUrl(draft);
  const invalid = touched && parsed === null;

  const commit = () => {
    setTouched(true);
    if (parsed) onSave(parsed);
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={styles.flex}>
        <Pressable style={styles.backdrop} onPress={onClose} />
        <View style={[styles.sheet, { backgroundColor: t.card, borderColor: t.hairline }]}>
          <View style={[styles.handle, { backgroundColor: t.faint }]} />

          {/* Header row — icon chip + title + close, like the web modals */}
          <View style={styles.header}>
            <View style={[styles.headerChip, { backgroundColor: t.accentSoft }]}>
              <Feather name="settings" size={15} color={t.accent} />
            </View>
            <View style={styles.headerText}>
              <Text style={[styles.title, { color: t.text }]}>Server URL</Text>
              <Text style={[styles.subtitle, { color: t.muted }]}>Point the app at your AuraPOS server</Text>
            </View>
            <Pressable onPress={onClose} hitSlop={8} style={({ pressed }) => [pressed && { opacity: 0.6 }]}>
              <Feather name="x" size={18} color={t.muted} />
            </Pressable>
          </View>

          {/* Field */}
          <Text style={[styles.fieldLabel, { color: t.muted }]}>BASE URL</Text>
          <TextInput
            value={draft}
            onChangeText={setDraft}
            onBlur={() => setTouched(true)}
            onSubmitEditing={commit}
            placeholder={DEFAULT_BASE_URL}
            placeholderTextColor={t.faint}
            keyboardType="url"
            autoCapitalize="none"
            autoCorrect={false}
            spellCheck={false}
            selectTextOnFocus
            returnKeyType="go"
            style={[
              styles.input,
              { backgroundColor: t.inputBg, borderColor: invalid ? status.rose : t.cardBorder, color: t.text },
            ]}
          />
          {invalid ? (
            <Text style={[styles.error, { color: status.rose }]}>That doesn't look like a valid URL.</Text>
          ) : (
            <Text style={[styles.hint, { color: t.muted }]}>
              Scheme optional (http:// added). Flask runs on port 5000 — e.g. {LAN_HINT}
            </Text>
          )}

          {/* Testing presets */}
          <View style={styles.presetsRow}>
            {PRESETS.map((p) => (
              <Pressable
                key={p.url}
                onPress={() => {
                  setDraft(p.url);
                  setTouched(false);
                }}
                style={({ pressed }) => [
                  styles.preset,
                  { borderColor: draft === p.url ? t.accent : t.cardBorder },
                  pressed && { opacity: 0.7 },
                ]}
              >
                <Text style={[styles.presetText, { color: draft === p.url ? t.accent : t.subtext }]}>{p.label}</Text>
              </Pressable>
            ))}
          </View>

          {/* Actions */}
          <View style={styles.actionsRow}>
            <Pressable
              onPress={onClose}
              style={({ pressed }) => [styles.cancelBtn, { borderColor: t.cardBorder }, pressed && { opacity: 0.7 }]}
            >
              <Text style={[styles.cancelText, { color: t.subtext }]}>Cancel</Text>
            </Pressable>
            <Pressable onPress={commit} disabled={invalid} style={styles.saveWrap}>
              <View style={[styles.saveBtn, invalid && { opacity: 0.4 }]}>
                <Feather name="check" size={14} color="#050508" />
                <Text style={styles.saveText}>Save &amp; Connect</Text>
              </View>
            </Pressable>
          </View>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  backdrop: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.55)',
  },
  sheet: {
    borderTopLeftRadius: 24, // rounded-3xl top corners
    borderTopRightRadius: 24,
    borderWidth: StyleSheet.hairlineWidth,
    borderBottomWidth: 0,
    paddingHorizontal: 20,
    paddingTop: 10,
    paddingBottom: 28,
  },
  handle: {
    alignSelf: 'center',
    width: 36,
    height: 4,
    borderRadius: 2,
    marginBottom: 14,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 18,
  },
  headerChip: {
    width: 34,
    height: 34,
    borderRadius: radius.chip,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerText: {
    flex: 1,
  },
  title: {
    fontFamily: font.bold,
    fontSize: 15,
  },
  subtitle: {
    fontFamily: font.regular,
    fontSize: 11,
    marginTop: 1,
  },
  fieldLabel: {
    fontFamily: font.semibold,
    fontSize: 10,
    letterSpacing: 1.2,
    marginBottom: 6,
  },
  input: {
    fontFamily: font.mono,
    fontSize: 13,
    borderWidth: 1,
    borderRadius: radius.input,
    paddingHorizontal: 12,
    paddingVertical: Platform.OS === 'ios' ? 12 : 10,
  },
  error: {
    fontFamily: font.regular,
    fontSize: 11,
    marginTop: 6,
  },
  hint: {
    fontFamily: font.regular,
    fontSize: 11,
    lineHeight: 15,
    marginTop: 6,
  },
  presetsRow: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 14,
  },
  preset: {
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  presetText: {
    fontFamily: font.semibold,
    fontSize: 11,
  },
  actionsRow: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 18,
  },
  cancelBtn: {
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.btn,
    paddingVertical: 13,
    paddingHorizontal: 18,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cancelText: {
    fontFamily: font.semibold,
    fontSize: 13,
  },
  saveWrap: {
    flex: 1,
  },
  saveBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#00f5d4', // neon-cyan — dark-theme accent CTA
    borderRadius: radius.btn,
    paddingVertical: 13,
  },
  saveText: {
    color: '#050508',
    fontFamily: font.bold,
    fontSize: 13,
  },
});

