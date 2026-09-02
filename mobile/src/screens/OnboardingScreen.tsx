import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import {
  Animated,
  Dimensions,
  Easing,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { BrandMark } from '../components/BrandMark';
import { colorsFor, font, neon, type Scheme, type ThemeColors } from '../theme';

type PlanType = 'free' | 'pro' | 'studio';
type BillingCycle = 'monthly' | 'yearly';

/** #rrggbb + alpha → rgba() string (mirrors Tailwind's /NN opacity tints). */
function rgba(hex: string, alpha: number): string {
  const n = hex.replace('#', '');
  const r = parseInt(n.slice(0, 2), 16);
  const g = parseInt(n.slice(2, 4), 16);
  const b = parseInt(n.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

interface SlideData {
  id: number;
  title: string;
  subtitle: string;
  accentColor: string;
  icon: keyof typeof Ionicons.glyphMap;
}

const SLIDES: SlideData[] = [
  {
    id: 0,
    title: 'Lightning Fast POS',
    subtitle:
      'Checkout clients in under 3 seconds. Built for high-volume front desks and mobile stylists.',
    accentColor: neon.cyan,
    icon: 'flash',
  },
  {
    id: 1,
    title: 'Smart Scheduling',
    subtitle:
      'Drag-and-drop chair management that prevents overlaps and keeps your whole team in sync.',
    accentColor: neon.magenta,
    icon: 'calendar',
  },
  {
    id: 2,
    title: 'Auto Commissions',
    subtitle:
      'Automatically track staff service sales and calculate complex commission splits on the fly.',
    accentColor: neon.violet,
    icon: 'people',
  },
];

const SLIDE_INTERVAL_MS = 4000;
const SHEET_MAX_HEIGHT = '85%';
const SHEET_SLIDE_DISTANCE = Dimensions.get('window').height * 0.9;

interface Props {
  /** App color scheme — seeds the in-screen theme toggle's initial state. */
  scheme: Scheme;
  /** Fired by "Log In to Existing" — leaves the homepage and enters the app. */
  onEnterApp: () => void;
}

/**
 * AuraPOS onboarding homepage — the app's home screen.
 *
 * Native port of `aurapos_onboarding_screen.tsx` (a web/Tailwind/lucide-react
 * composition that cannot render inside React Native): brand header with a
 * theme toggle, an auto-rotating 3-slide feature carousel over an accent
 * glow, tappable pagination dots, and CTAs — "Explore Plans" opens the INR
 * pricing bottom sheet, "Log In to Existing" enters the app proper
 * (SetupScreen / WebView at the configured server).
 */
export function OnboardingScreen({ scheme, onEnterApp }: Props) {
  const insets = useSafeAreaInsets();
  const [isDarkMode, setIsDarkMode] = useState<boolean>(scheme !== 'light');
  const [step, setStep] = useState<number>(0);
  const [plansOpen, setPlansOpen] = useState<boolean>(false);
  const [selectedPlan, setSelectedPlan] = useState<PlanType>('studio');
  const [billingCycle, setBillingCycle] = useState<BillingCycle>('monthly');

  const t = colorsFor(isDarkMode ? 'dark' : 'light');
  const currentSlide = SLIDES[step];

  // Auto-rotating feature carousel (4s cadence, wraps around).
  useEffect(() => {
    const timer = setInterval(() => {
      setStep((prev) => (prev + 1) % SLIDES.length);
    }, SLIDE_INTERVAL_MS);
    return () => clearInterval(timer);
  }, []);

  // Cross-slide entrance: fade + rise on every step change.
  const slideAnim = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    slideAnim.setValue(0);
    Animated.timing(slideAnim, {
      toValue: 1,
      duration: 380,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    }).start();
  }, [slideAnim, step]);

  // Plans sheet entrance/exit choreography.
  const backdropAnim = useRef(new Animated.Value(0)).current;
  const sheetAnim = useRef(new Animated.Value(SHEET_SLIDE_DISTANCE)).current;

  const openPlans = useCallback(() => {
    backdropAnim.setValue(0);
    sheetAnim.setValue(SHEET_SLIDE_DISTANCE);
    setPlansOpen(true);
  }, [backdropAnim, sheetAnim]);

  useEffect(() => {
    if (!plansOpen) return;
    Animated.parallel([
      Animated.timing(backdropAnim, { toValue: 1, duration: 200, useNativeDriver: true }),
      Animated.timing(sheetAnim, {
        toValue: 0,
        duration: 280,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: true,
      }),
    ]).start();
  }, [plansOpen, backdropAnim, sheetAnim]);

  const closePlans = useCallback(() => {
    Animated.parallel([
      Animated.timing(backdropAnim, { toValue: 0, duration: 180, useNativeDriver: true }),
      Animated.timing(sheetAnim, {
        toValue: SHEET_SLIDE_DISTANCE,
        duration: 220,
        easing: Easing.in(Easing.cubic),
        useNativeDriver: true,
      }),
    ]).start(() => setPlansOpen(false));
  }, [backdropAnim, sheetAnim]);

  /** Pick a plan in the sheet: record the choice and close the sheet. */
  const selectPlan = useCallback(
    (plan: PlanType) => {
      setSelectedPlan(plan);
      closePlans();
    },
    [closePlans],
  );

  return (
    <View style={[styles.screen, { backgroundColor: t.bg }]}>
      <StatusBar style={isDarkMode ? 'light' : 'dark'} />

      {/* Header — brand chip + wordmark + theme toggle */}
      <View style={[styles.header, { paddingTop: insets.top + 12 }]}>
        <View style={styles.headerBrand}>
          <BrandMark size={32} iconSize={16} />
          <Text style={[styles.wordmark, { color: t.text }]}>
            Aura<Text style={{ color: neon.cyan }}>POS</Text>
          </Text>
        </View>

        <Pressable
          onPress={() => setIsDarkMode((d) => !d)}
          accessibilityLabel="Toggle theme"
          style={({ pressed }) => [
            styles.themeToggle,
            { backgroundColor: isDarkMode ? '#11111a' : '#f1f5f9' },
            pressed && styles.ctaPressed,
          ]}
        >
          <Ionicons
            name={isDarkMode ? 'moon' : 'sunny'}
            size={16}
            color={isDarkMode ? '#a78bfa' : '#f59e0b'}
          />
        </Pressable>
      </View>

      {/* Feature carousel — accent glow + icon chip + copy */}
      <View style={styles.stage}>
        <View pointerEvents="none" style={styles.glowWrap}>
          <View style={[styles.glow, { backgroundColor: rgba(currentSlide.accentColor, 0.1) }]} />
          <View
            style={[styles.glowCore, { backgroundColor: rgba(currentSlide.accentColor, 0.14) }]}
          />
        </View>

        <Animated.View
          style={[
            styles.slideContent,
            {
              opacity: slideAnim,
              transform: [
                { translateY: slideAnim.interpolate({ inputRange: [0, 1], outputRange: [14, 0] }) },
              ],
            },
          ]}
        >
          <View style={[styles.iconChip, { borderColor: rgba(currentSlide.accentColor, 0.25) }]}>
            <Ionicons name={currentSlide.icon} size={40} color={currentSlide.accentColor} />
          </View>

          <Text style={[styles.slideTitle, { color: t.text }]}>{currentSlide.title}</Text>
          <Text style={[styles.slideSubtitle, { color: t.muted }]}>{currentSlide.subtitle}</Text>
        </Animated.View>
      </View>

      {/* Footer — pagination dots + CTAs */}
      <View
        style={[
          styles.footer,
          {
            backgroundColor: isDarkMode ? 'rgba(5, 5, 8, 0.92)' : 'rgba(255, 255, 255, 0.92)',
            borderTopColor: t.hairline,
            paddingBottom: insets.bottom + 24,
          },
        ]}
      >
        <View style={styles.dots}>
          {SLIDES.map((s, idx) => (
            <Pressable
              key={s.id}
              onPress={() => setStep(idx)}
              accessibilityLabel={`Go to slide ${idx + 1}`}
              style={[
                styles.dot,
                {
                  width: step === idx ? 24 : 6,
                  backgroundColor: step === idx ? currentSlide.accentColor : t.faint,
                },
              ]}
            />
          ))}
        </View>

        <Pressable
          onPress={openPlans}
          style={({ pressed }) => [styles.primaryCta, pressed && styles.ctaPressed]}
        >
          <Text style={styles.primaryCtaText}>Explore Plans</Text>
          <Ionicons name="sparkles" size={16} color="#ffffff" />
        </Pressable>

        <Pressable
          onPress={onEnterApp}
          style={({ pressed }) => [
            styles.secondaryCta,
            { backgroundColor: isDarkMode ? '#11111c' : '#f1f5f9' },
            pressed && styles.ctaPressed,
          ]}
        >
          <Text style={[styles.secondaryCtaText, { color: t.text }]}>Log In to Existing</Text>
        </Pressable>
      </View>

      {/* Plans bottom sheet */}
      {plansOpen && (
        <View style={styles.modal}>
          <Animated.View style={[StyleSheet.absoluteFill, { opacity: backdropAnim }]}>
            <Pressable
              style={StyleSheet.absoluteFill}
              onPress={closePlans}
              accessibilityLabel="Close plans"
            />
          </Animated.View>

          <Animated.View
            style={[
              styles.sheet,
              {
                backgroundColor: t.card,
                borderTopColor: t.cardBorder,
                maxHeight: SHEET_MAX_HEIGHT,
                paddingBottom: insets.bottom + 16,
                transform: [{ translateY: sheetAnim }],
              },
            ]}
          >
            {/* Sheet header */}
            <View style={[styles.sheetHeader, { borderBottomColor: t.hairline }]}>
              <View style={styles.flex1}>
                <View style={styles.sheetTitleRow}>
                  <Text style={[styles.sheetTitle, { color: t.text }]}>Select Your Plan</Text>
                  <View style={styles.inrBadge}>
                    <Text style={styles.inrBadgeText}>INR ₹</Text>
                  </View>
                </View>
                <Text style={[styles.sheetSubtitle, { color: t.muted }]}>
                  Instant activation · Razorpay Secured
                </Text>
              </View>
              <Pressable
                onPress={closePlans}
                accessibilityLabel="Close"
                style={({ pressed }) => [
                  styles.sheetClose,
                  { backgroundColor: t.inputBg },
                  pressed && { opacity: 0.7 },
                ]}
              >
                <Ionicons name="close" size={20} color={t.muted} />
              </Pressable>
            </View>

            {/* Billing cycle selector */}
            <View style={[styles.billingToggle, { backgroundColor: t.inputBg }]}>
              {(['monthly', 'yearly'] as const).map((cycle) => (
                <Pressable
                  key={cycle}
                  onPress={() => setBillingCycle(cycle)}
                  style={[
                    styles.billingOption,
                    billingCycle === cycle && { backgroundColor: isDarkMode ? '#1e1e2d' : '#ffffff' },
                  ]}
                >
                  <Text
                    style={[
                      styles.billingText,
                      {
                        color: billingCycle === cycle ? t.text : t.muted,
                        fontFamily: billingCycle === cycle ? font.bold : font.semibold,
                      },
                    ]}
                  >
                    {cycle === 'monthly' ? 'Monthly' : 'Annual'}
                  </Text>
                  {cycle === 'yearly' && (
                    <View style={styles.billingChip}>
                      <Text style={styles.billingChipText}>2 MO FREE</Text>
                    </View>
                  )}
                </Pressable>
              ))}
            </View>

            {/* Plans list */}
            <ScrollView
              style={styles.planList}
              contentContainerStyle={styles.planListContent}
              showsVerticalScrollIndicator={false}
            >
              {/* 1. Free Trial */}
              <PlanCard
                t={t}
                accent={neon.emerald}
                selected={selectedPlan === 'free'}
                title="Free Trial"
                badge={{ label: '14 Days', bg: neon.emerald }}
                subtitle="Core POS with single team seat"
                price="₹0"
                period="14 days free"
                features={FREE_FEATURES}
                cta={
                  <Pressable
                    onPress={() => selectPlan('free')}
                    style={({ pressed }) => [
                      styles.planCta,
                      styles.planCtaOutline,
                      { borderColor: neon.emerald },
                      pressed && { opacity: 0.9 },
                    ]}
                  >
                    <MaterialCommunityIcons name="rocket-launch" size={14} color={neon.emerald} />
                    <Text style={[styles.planCtaText, { color: neon.emerald }]}>
                      Start 14-Day Free Trial
                    </Text>
                  </Pressable>
                }
              />

              {/* 2. Pro */}
              <PlanCard
                t={t}
                accent={neon.cyan}
                selected={selectedPlan === 'pro'}
                title="Pro Plan"
                subtitle="Great start for growing salons"
                price={billingCycle === 'yearly' ? '₹690' : '₹69'}
                period={billingCycle === 'yearly' ? '/ year' : '/ month'}
                features={PRO_FEATURES}
                cta={
                  <Pressable
                    onPress={() => selectPlan('pro')}
                    style={({ pressed }) => [
                      styles.planCta,
                      { backgroundColor: neon.cyan },
                      pressed && { opacity: 0.9 },
                    ]}
                  >
                    <Ionicons name="checkmark" size={14} color="#050508" />
                    <Text style={[styles.planCtaText, { color: '#050508' }]}>Select Pro Plan</Text>
                  </Pressable>
                }
              />

              {/* 3. Studio */}
              <PlanCard
                t={t}
                accent={neon.magenta}
                selected={selectedPlan === 'studio'}
                forceHighlight
                cornerBadge="Most Powerful"
                title="Studio Plan"
                subtitle="Full feature suite & brand tools"
                price={billingCycle === 'yearly' ? '₹1,490' : '₹149'}
                period={billingCycle === 'yearly' ? '/ year' : '/ month'}
                features={STUDIO_FEATURES}
                cta={
                  <LinearGradient
                    colors={[neon.magenta, neon.violet]}
                    start={{ x: 0, y: 0.5 }}
                    end={{ x: 1, y: 0.5 }}
                    style={styles.planCtaGradient}
                  >
                    <Pressable
                      onPress={() => selectPlan('studio')}
                      style={({ pressed }) => [styles.planCtaBase, pressed && { opacity: 0.95 }]}
                    >
                      <Ionicons name="sparkles" size={14} color="#ffffff" />
                      <Text style={[styles.planCtaText, { color: '#ffffff' }]}>
                        Select Studio Plan
                      </Text>
                    </Pressable>
                  </LinearGradient>
                }
              />
            </ScrollView>

            {/* Sheet footer security badge */}
            <View style={[styles.sheetFooter, { borderTopColor: t.hairline }]}>
              <MaterialCommunityIcons name="shield-check-outline" size={14} color={neon.emerald} />
              <Text style={[styles.sheetFooterText, { color: t.muted }]}>
                256-bit Encrypted Razorpay Checkout
              </Text>
            </View>
          </Animated.View>
        </View>
      )}
    </View>
  );
}

type PlanFeatureIcon =
  | { set: 'ion'; name: keyof typeof Ionicons.glyphMap }
  | { set: 'mci'; name: keyof typeof MaterialCommunityIcons.glyphMap };

interface PlanFeature {
  icon: PlanFeatureIcon;
  color: string;
  label: string;
}

const FREE_FEATURES: PlanFeature[] = [
  { icon: { set: 'ion', name: 'checkmark-circle' }, color: neon.emerald, label: 'Single Team Seat' },
  {
    icon: { set: 'ion', name: 'checkmark-circle' },
    color: neon.emerald,
    label: 'Unlimited Billing & Invoices',
  },
  {
    icon: { set: 'ion', name: 'checkmark-circle' },
    color: neon.emerald,
    label: 'Online Client Booking Link',
  },
];

const PRO_FEATURES: PlanFeature[] = [
  { icon: { set: 'ion', name: 'checkmark-circle' }, color: neon.cyan, label: 'Up to 2 Team Seats' },
  {
    icon: { set: 'ion', name: 'checkmark-circle' },
    color: neon.cyan,
    label: 'Unlimited Billing & Invoices',
  },
  {
    icon: { set: 'ion', name: 'checkmark-circle' },
    color: neon.cyan,
    label: 'Online Client Booking Link',
  },
  {
    icon: { set: 'ion', name: 'location' },
    color: neon.cyan,
    label: 'Salon Address & Map Location',
  },
];

const STUDIO_FEATURES: PlanFeature[] = [
  {
    icon: { set: 'ion', name: 'checkmark-circle' },
    color: neon.magenta,
    label: 'Unlimited Team Seats',
  },
  {
    icon: { set: 'ion', name: 'checkmark-circle' },
    color: neon.magenta,
    label: 'Online Client Booking Link',
  },
  { icon: { set: 'mci', name: 'crown' }, color: '#fbbf24', label: 'Advanced Analytics Reports' },
  { icon: { set: 'mci', name: 'crown' }, color: '#fbbf24', label: 'Custom Salon Logo Branding' },
  { icon: { set: 'mci', name: 'crown' }, color: '#fbbf24', label: 'CSV Data Import & Export' },
];

/** One "✓ feature" row inside a plan card. */
function PlanFeatureRow({ feature, textColor }: { feature: PlanFeature; textColor: string }) {
  return (
    <View style={styles.featureRow}>
      {feature.icon.set === 'ion' ? (
        <Ionicons name={feature.icon.name} size={14} color={feature.color} />
      ) : (
        <MaterialCommunityIcons name={feature.icon.name} size={14} color={feature.color} />
      )}
      <Text style={[styles.featureText, { color: textColor }]}>{feature.label}</Text>
    </View>
  );
}

interface PlanCardProps {
  t: ThemeColors;
  accent: string;
  selected: boolean;
  /** Studio-style card that stays highlighted even when not selected. */
  forceHighlight?: boolean;
  /** Corner ribbon label (e.g. "Most Powerful"). */
  cornerBadge?: string;
  title: string;
  subtitle: string;
  /** Small pill next to the title (e.g. "14 Days"). */
  badge?: { label: string; bg: string };
  price: string;
  period: string;
  features: PlanFeature[];
  /** Call-to-action control rendered at the card's foot. */
  cta: ReactNode;
}

/** One pricing card inside the plans sheet. */
function PlanCard({
  t,
  accent,
  selected,
  forceHighlight = false,
  cornerBadge,
  title,
  subtitle,
  badge,
  price,
  period,
  features,
  cta,
}: PlanCardProps) {
  const highlighted = selected || forceHighlight;

  return (
    <View
      style={[
        styles.planCard,
        {
          backgroundColor: selected ? rgba(accent, 0.05) : t.card,
          borderWidth: highlighted ? 2 : 1,
          borderColor: highlighted ? accent : t.cardBorder,
        },
        highlighted && {
          shadowColor: accent,
          shadowOpacity: 0.35,
          shadowRadius: 10,
          shadowOffset: { width: 0, height: 0 },
          elevation: 6,
        },
      ]}
    >
      {cornerBadge ? (
        <View style={styles.cornerBadge}>
          <Text style={styles.cornerBadgeText}>{cornerBadge}</Text>
        </View>
      ) : null}

      <View style={styles.planCardTop}>
        <View style={styles.flex1}>
          <View style={styles.planTitleRow}>
            <Text style={[styles.planTitle, { color: t.text }]}>{title}</Text>
            {badge ? (
              <View style={[styles.planBadge, { backgroundColor: badge.bg }]}>
                <Text style={styles.planBadgeText}>{badge.label}</Text>
              </View>
            ) : null}
          </View>
          <Text style={[styles.planSubtitle, { color: t.muted }]}>{subtitle}</Text>
        </View>

        <View style={styles.planPriceBlock}>
          <Text style={[styles.planPrice, { color: accent }]}>{price}</Text>
          <Text style={[styles.planPeriod, { color: t.muted }]}>{period}</Text>
        </View>
      </View>

      <View style={styles.planFeatures}>
        {features.map((feature) => (
          <PlanFeatureRow key={feature.label} feature={feature} textColor={t.subtext} />
        ))}
      </View>

      {cta}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
  },
  flex1: {
    flex: 1,
  },
  ctaPressed: {
    opacity: 0.92,
    transform: [{ scale: 0.98 }],
  },

  // ---- Header ------------------------------------------------------------
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingBottom: 12,
    zIndex: 20,
  },
  headerBrand: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  wordmark: {
    fontFamily: font.extrabold,
    fontSize: 18,
    letterSpacing: -0.4,
  },
  themeToggle: {
    width: 41,
    height: 41,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },

  // ---- Feature carousel --------------------------------------------------
  stage: {
    flex: 1,
    justifyContent: 'center',
    paddingHorizontal: 24,
  },
  glowWrap: {
    ...StyleSheet.absoluteFillObject,
    alignItems: 'center',
    justifyContent: 'center',
  },
  glow: {
    position: 'absolute',
    width: 240,
    height: 240,
    borderRadius: 120,
  },
  glowCore: {
    position: 'absolute',
    width: 150,
    height: 150,
    borderRadius: 75,
  },
  slideContent: {
    alignItems: 'center',
  },
  iconChip: {
    width: 96,
    height: 96,
    borderRadius: 24,
    borderWidth: 1,
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 32,
    shadowColor: '#000000',
    shadowOpacity: 0.35,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 10 },
    elevation: 10,
  },
  slideTitle: {
    fontFamily: font.extrabold,
    fontSize: 24,
    letterSpacing: -0.5,
    marginBottom: 12,
    textAlign: 'center',
  },
  slideSubtitle: {
    fontFamily: font.regular,
    fontSize: 13,
    lineHeight: 20,
    textAlign: 'center',
    maxWidth: 280,
  },

  // ---- Footer ------------------------------------------------------------
  footer: {
    paddingHorizontal: 24,
    paddingTop: 24,
    borderTopWidth: StyleSheet.hairlineWidth,
    zIndex: 20,
  },
  dots: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginBottom: 24,
  },
  dot: {
    height: 6,
    borderRadius: 3,
  },
  primaryCta: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderRadius: 16,
    backgroundColor: neon.violet,
    shadowColor: neon.violet,
    shadowOpacity: 0.35,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 6 },
    elevation: 8,
  },
  primaryCtaText: {
    color: '#ffffff',
    fontFamily: font.bold,
    fontSize: 14,
  },
  secondaryCta: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    borderRadius: 16,
    marginTop: 12,
  },
  secondaryCtaText: {
    fontFamily: font.bold,
    fontSize: 14,
  },

  // ---- Plans sheet ---------------------------------------------------------
  modal: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'flex-end',
    zIndex: 30,
  },
  sheet: {
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    borderTopWidth: StyleSheet.hairlineWidth,
    paddingTop: 20,
    paddingHorizontal: 20,
  },
  sheetHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    paddingBottom: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    marginBottom: 12,
  },
  sheetTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  sheetTitle: {
    fontFamily: font.extrabold,
    fontSize: 18,
  },
  inrBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
    backgroundColor: rgba(neon.violet, 0.2),
    borderWidth: 1,
    borderColor: rgba(neon.violet, 0.3),
  },
  inrBadgeText: {
    fontFamily: font.bold,
    fontSize: 10,
    color: neon.violet,
  },
  sheetSubtitle: {
    fontFamily: font.regular,
    fontSize: 12,
    marginTop: 2,
  },
  sheetClose: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  billingToggle: {
    flexDirection: 'row',
    padding: 4,
    borderRadius: 12,
    marginBottom: 14,
  },
  billingOption: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 6,
    borderRadius: 8,
  },
  billingText: {
    fontSize: 12,
  },
  billingChip: {
    backgroundColor: neon.emerald,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 999,
  },
  billingChipText: {
    color: '#ffffff',
    fontFamily: font.extrabold,
    fontSize: 9,
    letterSpacing: -0.2,
  },
  planList: {
    flexGrow: 0,
    flexShrink: 1,
  },
  planListContent: {
    gap: 12,
    paddingBottom: 12,
  },
  sheetFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingTop: 8,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  sheetFooterText: {
    fontFamily: font.regular,
    fontSize: 11,
  },

  // ---- Plan cards ----------------------------------------------------------
  planCard: {
    padding: 16,
    borderRadius: 16,
    overflow: 'hidden',
  },
  planCardTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 12,
    marginBottom: 6,
  },
  planTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  planTitle: {
    fontFamily: font.bold,
    fontSize: 16,
  },
  planBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  planBadgeText: {
    color: '#ffffff',
    fontFamily: font.extrabold,
    fontSize: 9,
  },
  planSubtitle: {
    fontFamily: font.regular,
    fontSize: 12,
    marginTop: 2,
  },
  planPriceBlock: {
    alignItems: 'flex-end',
  },
  planPrice: {
    fontFamily: font.extrabold,
    fontSize: 18,
  },
  planPeriod: {
    fontFamily: font.regular,
    fontSize: 10,
    marginTop: 1,
  },
  planFeatures: {
    marginVertical: 8,
    gap: 6,
  },
  featureRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  featureText: {
    fontFamily: font.regular,
    fontSize: 12,
    flex: 1,
  },
  planCtaBase: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 10,
    borderRadius: 12,
  },
  planCta: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 10,
    borderRadius: 12,
    marginTop: 8,
  },
  planCtaOutline: {
    borderWidth: 1,
  },
  planCtaGradient: {
    borderRadius: 12,
    marginTop: 8,
    overflow: 'hidden',
  },
  planCtaText: {
    fontFamily: font.bold,
    fontSize: 12,
  },
  cornerBadge: {
    position: 'absolute',
    top: 0,
    right: 0,
    backgroundColor: neon.magenta,
    paddingHorizontal: 10,
    paddingVertical: 2,
    borderBottomLeftRadius: 8,
  },
  cornerBadgeText: {
    color: '#ffffff',
    fontFamily: font.extrabold,
    fontSize: 9,
    letterSpacing: 0.8,
  },
});
