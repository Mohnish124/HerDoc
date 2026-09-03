import { Platform } from 'react-native';
import * as Network from 'expo-network';

export function isOnlineStatusAvailable() {
  return Platform.OS !== 'web';
}

export async function getIsConnected() {
  if (Platform.OS === 'web') {
    return typeof navigator !== 'undefined' ? Boolean(navigator.onLine) : true;
  }
  try {
    const state = await Network.getNetworkStateAsync();
    return Boolean(state?.isConnected);
  } catch {
    return true;
  }
}

export function subscribeToConnectivityChanges(listener) {
  if (Platform.OS !== 'web') {
    try {
      const sub = Network.addNetworkStateListener((state) => {
        listener(Boolean(state?.isConnected));
      });
      return () => sub?.remove?.();
    } catch {
      return () => {};
    }
  }

  if (typeof window === 'undefined') {
    return () => {};
  }

  const handleOnline = () => listener(true);
  const handleOffline = () => listener(false);

  window.addEventListener('online', handleOnline);
  window.addEventListener('offline', handleOffline);

  return () => {
    window.removeEventListener('online', handleOnline);
    window.removeEventListener('offline', handleOffline);
  };
}

export async function getNetworkDiagnostics() {
  const connected = await getIsConnected();
  if (Platform.OS === 'web') {
    return { connected, type: 'web', isInternetReachable: connected };
  }
  try {
    const state = await Network.getNetworkStateAsync();
    return {
      connected,
      type: state?.type ?? 'unknown',
      isInternetReachable: Boolean(state?.isInternetReachable),
    };
  } catch {
    return { connected, type: 'unknown', isInternetReachable: connected };
  }
}
