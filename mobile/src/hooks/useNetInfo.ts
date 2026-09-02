import { useEffect, useRef, useState } from 'react';
import { AppState, type AppStateStatus } from 'react-native';
import NetInfo, { type NetInfoState } from '@react-native-community/netinfo';

export interface NetStatus {
  /** True when the device has no usable network path (airplane mode, wifi off…). */
  offline: boolean;
  /** Human-readable connection label for diagnostics. */
  label: string;
}

/**
 * Proactive connectivity watcher.
 *
 * Subscribes immediately on mount so an offline state is known BEFORE the
 * WebView attempts its first navigation — letting the app render the custom
 * offline template instead of ever hitting the OS error page. Also re-checks
 * on AppState changes (returning from background triggers a fresh probe).
 */
export function useNetInfo(): NetStatus {
  const [status, setStatus] = useState<NetStatus>({ offline: false, label: 'checking…' });

  useEffect(() => {
    let mounted = true;

    const apply = (state: NetInfoState) => {
      if (!mounted) return;
      const isConnected = state.isConnected === true && state.isInternetReachable !== false;
      const label = !state.isConnected
        ? 'no connection'
        : state.isInternetReachable === false
          ? 'no internet'
          : `${state.type ?? 'unknown'}${state.details?.isConnectionExpensive ? ' (metered)' : ''}`;
      setStatus({ offline: !isConnected, label });
    };

    // Fire an immediate one-shot probe, then keep subscribing.
    const unsubscribe = NetInfo.addEventListener(apply);
    NetInfo.fetch().then(apply).catch(() => undefined);

    const onAppState = (_next: AppStateStatus) => {
      NetInfo.fetch().then(apply).catch(() => undefined);
    };
    const appSub = AppState.addEventListener('change', onAppState);

    return () => {
      mounted = false;
      unsubscribe();
      appSub.remove();
    };
  }, []);

  return status;
}

/**
 * Fires `onOnline` once each time the device transitions offline → online.
 * Used to auto-recover the proactive offline gate without user input.
 */
export function useOnlineTransition(onOnline: () => void) {
  const [offline, setOffline] = useState(false);
  const wasOffline = useRef(false);

  useEffect(() => {
    const unsub = NetInfo.addEventListener((state) => {
      setOffline(!(state.isConnected === true && state.isInternetReachable !== false));
    });
    return () => unsub();
  }, []);

  useEffect(() => {
    if (offline) {
      wasOffline.current = true;
    } else if (wasOffline.current) {
      wasOffline.current = false;
      onOnline();
    }
  }, [offline, onOnline]);
}
