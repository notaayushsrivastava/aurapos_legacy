import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, BackHandler, StyleSheet, Text, View, useColorScheme } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { useFonts } from 'expo-font';
import { SafeAreaProvider, useSafeAreaInsets } from 'react-native-safe-area-context';
import { WebView } from 'react-native-webview';
import type {
  WebViewErrorEvent,
  WebViewHttpErrorEvent,
  WebViewNavigation,
} from 'react-native-webview/lib/WebViewTypes';
import {
  PlusJakartaSans_400Regular,
  PlusJakartaSans_500Medium,
  PlusJakartaSans_600SemiBold,
  PlusJakartaSans_700Bold,
  PlusJakartaSans_800ExtraBold,
} from '@expo-google-fonts/plus-jakarta-sans';
import { JetBrainsMono_400Regular, JetBrainsMono_500Medium } from '@expo-google-fonts/jetbrains-mono';

import { ErrorFallback, type LoadError } from './src/components/ErrorFallback';
import { HeaderBar } from './src/components/HeaderBar';
import { BrandMark } from './src/components/BrandMark';
import { UrlSheet } from './src/components/UrlSheet';
import { SetupScreen } from './src/screens/SetupScreen';
import { OnboardingScreen } from './src/screens/OnboardingScreen';
import { useNetInfo, useOnlineTransition } from './src/hooks/useNetInfo';
import { loadBaseUrl, saveBaseUrl } from './src/lib/storage';
import { hostOf } from './src/lib/url';
import { colorsFor, font, status } from './src/theme';

/**
 * Classifies a WebView onError description into an ErrorFallback kind.
 * Matches Chromium network error codes (Android) and NSURLError descriptions (iOS).
 */
function classifyError(description: string): LoadError {
  const d = description.toLowerCase();
  if (d.includes('err_name_not_resolved') || d.includes('err_dns') || d.includes('cannot find server') || d.includes('-host not found') || d.includes('-1003')) {
    return { kind: 'dns', description };
  }
  if (d.includes('err_internet_disconnected') || d.includes('-1009') || d.includes('offline') || d.includes('network connection was lost')) {
    return { kind: 'offline', description };
  }
  return { kind: 'network', description };
}

/**
 * AuraPOS Mobile — a resilient WebView wrapper for the Flask web app.
 *
 * Homepage flow: the app boots into the native onboarding homepage
 * (src/screens/OnboardingScreen). The WebView — the server's default `/`
 * route — mounts only after the user taps "Log In to Existing".
 *
 * Failure contract (no OS "Webpage not available" screen, ever):
 *  1. Proactive — @react-native-community/netinfo gates the WebView OFF when
 *     the device is offline, before it ever attempts a navigation.
 *  2. onError — classifies the failure, hides the WebView (unmount) and shows
 *     the custom themed fallback.
 *  3. onHttpError — same, but only for main-frame 4xx/5xx responses
 *     (sub-resource failures like favicon 404s must not nuke the page).
 *  4. onRenderProcessGone / onContentProcessDidTerminate — renderer crash
 *     guards for Android / iOS respectively.
 *  5. renderError — belt-and-braces so even a race that slips past the
 *     handlers renders a blank surface instead of the OS error page.
 */
export default function App() {
  return (
    <SafeAreaProvider>
      <AuraPOSApp />
    </SafeAreaProvider>
  );
}

function AuraPOSApp() {
  const systemScheme = useColorScheme();
  const scheme: 'light' | 'dark' = systemScheme === 'light' ? 'light' : 'dark';
  const t = colorsFor(scheme);
  const insets = useSafeAreaInsets();

  const [fontsLoaded] = useFonts({
    PlusJakartaSans_400Regular,
    PlusJakartaSans_500Medium,
    PlusJakartaSans_600SemiBold,
    PlusJakartaSans_700Bold,
    PlusJakartaSans_800ExtraBold,
    JetBrainsMono_400Regular,
    JetBrainsMono_500Medium,
  });

  const net = useNetInfo();
  const [ready, setReady] = useState(false); // persisted URL has been read
  const [baseUrl, setBaseUrl] = useState<string | null>(null);
  const [error, setError] = useState<LoadError | null>(null);
  const [loading, setLoading] = useState(false); // drives the header spinner
  const [sheetOpen, setSheetOpen] = useState(false);
  const [reloadKey, setReloadKey] = useState(0); // forces a fresh WebView mount
  const [showOnboarding, setShowOnboarding] = useState(true); // homepage gate

  const webViewRef = useRef<WebView>(null);
  const mainUrlRef = useRef<string | null>(null); // last known main-frame URL
  const canGoBackRef = useRef(false);
  const errorRef = useRef<LoadError | null>(null);
  errorRef.current = error;

  // Read the persisted server URL once on boot.
  useEffect(() => {
    loadBaseUrl().then((saved) => {
      if (saved) mainUrlRef.current = saved;
      setBaseUrl(saved);
      setReady(true);
    });
  }, []);

  // Auto-recover: when connectivity returns, drop any error and remount.
  const handleBackOnline = useCallback(() => {
    if (errorRef.current) {
      setError(null);
      setReloadKey((k) => k + 1);
    }
  }, []);
  useOnlineTransition(handleBackOnline);

  // Android hardware back walks WebView history instead of exiting the app.
  useEffect(() => {
    if (!baseUrl) return;
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      if (webViewRef.current && canGoBackRef.current) {
        webViewRef.current.goBack();
        return true;
      }
      return false;
    });
    return () => sub.remove();
  }, [baseUrl]);

  const failWith = useCallback((next: LoadError) => {
    setLoading(false);
    setError(next);
  }, []);

  const handleError = useCallback((e: WebViewErrorEvent) => {
    const { description = '', url = '' } = e.nativeEvent;
    // Android fires onError for subframes/iframes too — ignore those unless the
    // main URL isn't known yet (then the very first frame failing IS fatal).
    if (mainUrlRef.current && url && hostOf(url) !== hostOf(mainUrlRef.current)) return;
    failWith({ ...classifyError(description), url: url || mainUrlRef.current || undefined });
  }, [failWith]);

  const handleHttpError = useCallback((e: WebViewHttpErrorEvent) => {
    const { url = '', statusCode = 0 } = e.nativeEvent;
    if (!statusCode || statusCode < 400) return; // redirects/informational
    // Sub-resource failures (favicons, assets) share the event — filter to the main frame host.
    if (mainUrlRef.current && url && hostOf(url) !== hostOf(mainUrlRef.current)) return;
    failWith({ kind: 'http', statusCode, description: `HTTP ${statusCode}`, url: url || mainUrlRef.current || undefined });
  }, [failWith]);

  const handleRenderProcessGone = useCallback(() => {
    failWith({ kind: 'crash', description: 'Render process gone', url: mainUrlRef.current || undefined });
  }, [failWith]);

  const handleNavState = useCallback((nav: WebViewNavigation) => {
    if (nav.url) mainUrlRef.current = nav.url;
    canGoBackRef.current = nav.canGoBack === true;
  }, []);

  const handleLoadStart = useCallback(() => setLoading(true), []);
  const handleLoadEnd = useCallback(() => setLoading(false), []);

  /** Retry: clear the error — the WebView remounts at the last attempted URL. */
  const retry = useCallback(() => {
    setError(null);
    setReloadKey((k) => k + 1);
  }, []);

  /** Save a new server URL from the sheet: persist, reset state, remount. */
  const handleSaveUrl = useCallback((url: string) => {
    saveBaseUrl(url);
    mainUrlRef.current = url;
    canGoBackRef.current = false;
    setBaseUrl(url);
    setError(null);
    setReloadKey((k) => k + 1);
    setSheetOpen(false);
  }, []);

  // ---- Render decision tree -------------------------------------------------
  if (!fontsLoaded || !ready) {
    return (
      <View style={[styles.splash, { backgroundColor: t.bg }]}>
        <StatusBar style={scheme === 'dark' ? 'light' : 'dark'} />
        <BrandMark size={48} iconSize={24} />
        <Text style={[styles.splashName, { color: t.text }]}>AuraPOS</Text>
        <ActivityIndicator color={status.cyan} style={{ marginTop: 14 }} />
      </View>
    );
  }

  // Homepage: boot into the onboarding screen. The WebView — the server's
  // default `/` route — mounts only once the user leaves onboarding via
  // "Log In to Existing" (the SetupScreen gate still applies when no server
  // URL has been configured yet).
  if (showOnboarding) {
    return (
      <View style={{ flex: 1, backgroundColor: t.bg }}>
        <OnboardingScreen scheme={scheme} onEnterApp={() => setShowOnboarding(false)} />
      </View>
    );
  }

  if (!baseUrl) {
    return (
      <View style={{ flex: 1, backgroundColor: t.bg }}>
        <StatusBar style={scheme === 'dark' ? 'light' : 'dark'} />
        <SetupScreen scheme={scheme} savedUrl={baseUrl} onSave={handleSaveUrl} />
      </View>
    );
  }

  const activeUrl = mainUrlRef.current ?? baseUrl;
  const showOfflineGate = net.offline; // proactive — WebView never mounts

  return (
    <View style={{ flex: 1, backgroundColor: t.bg }}>
      <StatusBar style={scheme === 'dark' ? 'light' : 'dark'} />

      <HeaderBar
        host={hostOf(activeUrl)}
        loading={loading}
        offline={showOfflineGate}
        topInset={insets.top}
        onReload={retry}
        onEditUrl={() => setSheetOpen(true)}
      />

      {showOfflineGate ? (
        <ErrorFallback
          scheme={scheme}
          error={{ kind: 'offline', url: activeUrl }}
          proactiveOffline
          onRetry={retry}
          onEditUrl={() => setSheetOpen(true)}
        />
      ) : error ? (
        <ErrorFallback
          scheme={scheme}
          error={{ ...error, url: error.url ?? activeUrl }}
          onRetry={retry}
          onEditUrl={() => setSheetOpen(true)}
        />
      ) : (
        <WebView
          key={reloadKey}
          ref={webViewRef}
          source={{ uri: activeUrl }}
          style={{ backgroundColor: t.bg }}
          onError={handleError}
          onHttpError={handleHttpError}
          onRenderProcessGone={handleRenderProcessGone}
          onContentProcessDidTerminate={handleRenderProcessGone}
          onNavigationStateChange={handleNavState}
          onLoadStart={handleLoadStart}
          onLoadEnd={handleLoadEnd}
          startInLoadingState
          renderLoading={() => <LoadingView color={t.bg} spinner={status.cyan} />}
          renderError={() => (
            /* Belt-and-braces: even if a failure slips past the handlers,
               render a blank surface instead of the OS error page. */
            <View style={{ flex: 1, backgroundColor: 'transparent' }} />
          )}
          javaScriptEnabled
          domStorageEnabled
          allowsBackForwardNavigationGestures
          originWhitelist={['http://*', 'https://*', 'about:*', 'data:*']}
        />
      )}

      <UrlSheet
        visible={sheetOpen}
        scheme={scheme}
        currentUrl={baseUrl}
        onClose={() => setSheetOpen(false)}
        onSave={handleSaveUrl}
      />
    </View>
  );
}

/** Themed first-paint placeholder while the WebView fetches the page. */
function LoadingView({ color, spinner }: { color: string; spinner: string }) {
  return (
    <View style={[styles.splash, { backgroundColor: color }]}>
      <ActivityIndicator color={spinner} />
      <Text style={styles.loadingText}>Connecting…</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  splash: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  splashName: {
    fontFamily: font.extrabold,
    fontSize: 18,
    letterSpacing: -0.4,
    marginTop: 12,
  },
  loadingText: {
    fontFamily: font.mono,
    fontSize: 11,
    opacity: 0.5,
    marginTop: 10,
  },
});



