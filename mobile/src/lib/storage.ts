import AsyncStorage from '@react-native-async-storage/async-storage';

const BASE_URL_KEY = '@aurapos/baseUrl';

export async function loadBaseUrl(): Promise<string | null> {
  try {
    return await AsyncStorage.getItem(BASE_URL_KEY);
  } catch {
    return null;
  }
}

export async function saveBaseUrl(url: string): Promise<void> {
  try {
    await AsyncStorage.setItem(BASE_URL_KEY, url);
  } catch {
    // Storage failures shouldn't crash the wrapper — the URL just won't persist.
  }
}

export async function clearBaseUrl(): Promise<void> {
  try {
    await AsyncStorage.removeItem(BASE_URL_KEY);
  } catch {
    // ignore
  }
}
