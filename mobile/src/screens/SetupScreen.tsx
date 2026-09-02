import { useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Feather } from '@expo/vector-icons';
import { BrandMark } from '../components/BrandMark';
import { DEFAULT_BASE_URL, LAN_HINT, normalizeBaseUrl } from '../lib/url';
import { colorsFor, font, radius, type Scheme } from '../theme';

interface Props {
  scheme: Scheme;
  savedUrl: string | null;
  onSave: (url: string) => void;
}

/**
 * First-run gate shown before any WebView mounts (when no server URL has been
 * chosen yet). Matches the web app's auth pages: centered brand chip,
 * rounded-3xl card, micro-uppercase labels, mono input, gradient CTA.
 */
export function SetupScreen({ scheme, savedUrl, onSave }: Props) {
  const t = colorsFor(scheme);
  const [draft, setDraft] = useState(savedUrl ?? DEFAULT_BASE_URL);
  const [touched, setTouched] = useState(false);

  const parsed = normalizeBaseUrl(draft);
  const invalid = touched && parsed === null;

  return (
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={[styles.screen, { backgroundColor: t.bg }]}>
      <BrandMark size={52} iconSize={26} />

      <Text style={[styles.appName, { color: t.text }]}>AuraPOS</Text>
      <Text style={[styles.tagline, { color: t.muted }]}>Salon Billing &amp; Management · Mobile</Text>

      <View style={[styles.card, { backgroundColor: t.card, borderColor: t.cardBorder }]}>
        <Text style={[styles.fieldLabel, { color: t.muted }]}>SERVER URL</Text>
        <TextInput
          value={draft}
          onChangeText={setDraft}
          onBlur={() => setTouched(true)}
          placeholder={DEFAULT_BASE_URL}
          placeholderTextColor={t.faint}
          keyboardType="url"
          autoCapitalize="none"
          autoCorrect={false}
          spellCheck={false}
          selectTextOnFocus
          returnKeyType="go"
          onSubmitEditing={() => parsed && onSave(parsed)}
          style={[
            styles.input,
            { backgroundColor: t.inputBg, borderColor: invalid ? '#f43f5e' : t.cardBorder, color: t.text },
          ]}
        />
        {invalid ? (
          <Text style={styles.error}>That doesn't look like a valid URL.</Text>
        ) : (
          <Text style={[styles.hint, { color: t.muted }]}>
            Default targets the Flask dev server ({DEFAULT_BASE_URL} from the Android emulator). On a real device use your
            machine's LAN IP — e.g. {LAN_HINT}
          </Text>
        )}

        <LinearGradient
          colors={['#f72585', '#7c3aed', '#00f5d4']}
          start={{ x: 0, y: 0.5 }}
          end={{ x: 1, y: 0.5 }}
          style={styles.ctaGradient}
        >
          <Pressable
            onPress={() => {
              setTouched(true);
              if (parsed) onSave(parsed);
            }}
            android_ripple={{ color: 'rgba(255,255,255,0.25)' }}
            style={({ pressed }) => [styles.cta, pressed && { opacity: 0.9, transform: [{ scale: 0.98 }] }]}
          >
            <Feather name="zap" size={15} color="#ffffff" />
            <Text style={styles.ctaText}>Connect to AuraPOS</Text>
          </Pressable>
        </LinearGradient>

        <Text style={[styles.note, { color: t.faint }]}>
          You can change this any time from the header (⚙) — handy for switching between local, staging, and production.
        </Text>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  appName: {
    fontFamily: font.extrabold,
    fontSize: 22,
    letterSpacing: -0.5,
    marginTop: 16,
  },
  tagline: {
    fontFamily: font.regular,
    fontSize: 12,
    marginTop: 4,
    marginBottom: 24,
  },
  card: {
    width: '100%',
    maxWidth: 380,
    borderRadius: radius.card,
    borderWidth: StyleSheet.hairlineWidth,
    padding: 20,
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
    color: '#f43f5e',
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
  ctaGradient: {
    borderRadius: radius.btn,
    overflow: 'hidden',
    marginTop: 16,
  },
  cta: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 13,
  },
  ctaText: {
    color: '#ffffff',
    fontFamily: font.bold,
    fontSize: 13,
  },
  note: {
    fontFamily: font.regular,
    fontSize: 10.5,
    lineHeight: 15,
    textAlign: 'center',
    marginTop: 14,
  },
});
