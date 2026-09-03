import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  SafeAreaView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { getOfflineLoginStatus } from '../services/auth';
import { OFFLINE_RATE_LIMIT } from '../services/auth';

function formatLockRemaining(ms) {
  if (!Number.isFinite(ms) || ms <= 0) {
    return 'soon';
  }
  const totalMinutes = Math.ceil(ms / 60000);
  if (totalMinutes < 1) {
    const seconds = Math.max(1, Math.ceil(ms / 1000));
    return `${seconds}s`;
  }
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours <= 0) {
    return `${minutes}m`;
  }
  if (minutes <= 0) {
    return `${hours}h`;
  }
  return `${hours}h ${minutes}m`;
}

export default function LoginScreen({ isConnected, onLogin, isBusy }) {
  const [phone, setPhone] = useState('');
  const [pin, setPin] = useState('');
  const [statusTick, setStatusTick] = useState(0);
  const [errorMessage, setErrorMessage] = useState(null);
  const phoneRef = useRef('');
  phoneRef.current = phone;

  useEffect(() => {
    let timer = null;
    let closed = false;
    const tick = () => {
      setStatusTick((t) => t + 1);
      if (!closed) {
        timer = setTimeout(tick, 5000);
      }
    };
    tick();
    return () => {
      closed = true;
      if (timer) {
        clearTimeout(timer);
      }
    };
  }, []);

  const offlineStatus = useMemo(() => {
    return getOfflineLoginStatus(phoneRef.current);
  }, [phone, statusTick]);

  const phoneTrimmed = phone.trim();
  const pinTrimmed = pin.trim();
  const isEmpty = !phoneTrimmed || !pinTrimmed;

  const canSubmit = !isBusy && !isEmpty && !(offlineStatus.available === false && !isConnected && offlineStatus.lockedUntil);

  const offlineMode = Boolean(!isConnected);
  const offlineUnavailable = offlineMode && !offlineStatus.available;

  const handleSubmit = async () => {
    if (isBusy) {
      return;
    }
    if (isEmpty) {
      setErrorMessage('Phone and PIN are required.');
      return;
    }
    if (offlineMode && !offlineStatus.available) {
      if (offlineStatus.lockedUntil) {
        const remainingMs = Number(offlineStatus.lockRemainingMs || 0);
        setErrorMessage(`Account is locked. Try again in ${formatLockRemaining(remainingMs)}.`);
        return;
      }
      setErrorMessage('No prior successful login on this device. Please connect to the network and try online login first.');
      return;
    }
    setErrorMessage(null);
    try {
      await onLogin(phoneTrimmed, pinTrimmed);
    } catch (error) {
      const message = error?.message || 'Login failed. Please try again.';
      setErrorMessage(message);
      if (__DEV__) {
        console.warn('[HerDoc] login error:', message);
      }
    }
  };

  const attemptLabel = (() => {
    if (offlineMode) {
      if (offlineStatus.lockedUntil) {
        return `Locked · ${formatLockRemaining(Number(offlineStatus.lockRemainingMs || 0))} remaining`;
      }
      if (offlineStatus.available) {
        const remaining = Number(offlineStatus.remainingAttempts ?? OFFLINE_RATE_LIMIT.MAX_ATTEMPTS);
        return `${remaining} offline PIN attempt${remaining === 1 ? '' : 's'} remaining`;
      }
      return 'Offline login not available for this phone yet';
    }
    return 'Server credentials will be verified online';
  })();

  const statusColor = (() => {
    if (offlineMode && offlineStatus.lockedUntil) {
      return 'lock';
    }
    if (offlineMode && !offlineStatus.available) {
      return 'warn';
    }
    if (offlineMode) {
      return 'offline';
    }
    return 'online';
  })();

  return (
    <SafeAreaView style={styles.safeArea}>
      <KeyboardAvoidingView
        style={styles.container}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 20 : 0}
      >
        <View style={styles.card}>
          <Text style={styles.title}>HerDoc</Text>
          <Text style={styles.subtitle}>Worker login</Text>

          <Text style={styles.label}>Phone</Text>
          <TextInput
            autoCapitalize="none"
            autoComplete="tel"
            autoCorrect={false}
            autoFocus={false}
            contextMenuHidden
            keyboardType="phone-pad"
            textContentType="telephoneNumber"
            value={phone}
            onChangeText={(value) => {
              setPhone(value);
              setErrorMessage(null);
            }}
            onSubmitEditing={handleSubmit}
            placeholder="e.g. 9876543210"
            placeholderTextColor="#94a3b8"
            returnKeyType="next"
            style={[
              styles.input,
              Boolean(errorMessage && errorMessage.toLowerCase().includes('phone')) && styles.inputError,
            ]}
            editable={!isBusy}
          />

          <Text style={styles.label}>PIN</Text>
          <TextInput
            autoCapitalize="none"
            autoCorrect={false}
            contextMenuHidden
            keyboardType="number-pad"
            maxLength={6}
            secureTextEntry
            textContentType="password"
            value={pin}
            onChangeText={(value) => {
              setPin(value.replace(/[^0-9]/g, ''));
              setErrorMessage(null);
            }}
            onSubmitEditing={handleSubmit}
            placeholder="Enter 4-6 digit PIN"
            placeholderTextColor="#94a3b8"
            returnKeyType="done"
            style={[
              styles.input,
              Boolean(errorMessage && (
                errorMessage.toLowerCase().includes('pin') ||
                errorMessage.toLowerCase().includes('invalid') ||
                errorMessage.toLowerCase().includes('locked') ||
                errorMessage.toLowerCase().includes('attempt')
              )) && styles.inputError,
            ]}
            editable={!isBusy}
          />

          <View style={[styles.connectionBox, styles[`connectionBox_${statusColor}`]]}>
            <Text style={[styles.connectionLabel, styles[`connectionLabel_${statusColor}`]]}>
              {isConnected ? 'Online mode' : 'Offline mode'}
            </Text>
            <Text style={styles.connectionText}>{attemptLabel}</Text>
            {offlineStatus.name && offlineMode ? (
              <Text style={styles.connectionHint}>Saved PIN for {offlineStatus.name}</Text>
            ) : null}
          </View>

          {errorMessage ? (
            <View style={styles.errorBox}>
              <Text style={styles.errorText}>{errorMessage}</Text>
            </View>
          ) : null}

          <Pressable
            onPress={handleSubmit}
            disabled={!canSubmit || isBusy}
            style={({ pressed }) => [
              styles.button,
              (!canSubmit || isBusy) && styles.buttonDisabled,
              pressed && canSubmit && !isBusy && styles.buttonPressed,
            ]}
            accessibilityRole="button"
          >
            {isBusy ? (
              <View style={styles.buttonInner}>
                <ActivityIndicator color="#ffffff" />
                <Text style={styles.buttonText}>{'  '}Signing in…</Text>
              </View>
            ) : (
              <Text style={styles.buttonText}>
                {isConnected ? 'Login online' : offlineStatus.lockedUntil ? 'Account locked' : offlineStatus.available ? 'Login offline' : 'Online login required'}
              </Text>
            )}
          </Pressable>

          <Text style={styles.footer}>
            Offline PIN is verified locally against a secure hash.{'\n'}
            {OFFLINE_RATE_LIMIT.MAX_ATTEMPTS} wrong PINs = {OFFLINE_RATE_LIMIT.LOCK_MINUTES}-minute lock.
          </Text>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#eef4ff',
  },
  container: {
    flex: 1,
    justifyContent: 'center',
    paddingHorizontal: 20,
  },
  card: {
    backgroundColor: '#ffffff',
    borderRadius: 18,
    padding: 24,
    shadowColor: '#000',
    shadowOpacity: 0.08,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 3 },
    elevation: 4,
  },
  title: {
    fontSize: 32,
    fontWeight: '800',
    color: '#0f172a',
    marginBottom: 6,
    letterSpacing: -0.3,
  },
  subtitle: {
    fontSize: 15,
    color: '#475569',
    marginBottom: 22,
  },
  label: {
    fontSize: 13,
    fontWeight: '700',
    color: '#334155',
    marginBottom: 8,
    letterSpacing: 0.2,
  },
  input: {
    borderWidth: 1,
    borderColor: '#cbd5e1',
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    marginBottom: 18,
    backgroundColor: '#f8fafc',
    color: '#0f172a',
  },
  inputError: {
    borderColor: '#f87171',
    backgroundColor: '#fef2f2',
  },
  connectionBox: {
    borderRadius: 12,
    padding: 12,
    marginBottom: 14,
  },
  connectionBox_online: { backgroundColor: '#ecfdf5' },
  connectionBox_offline: { backgroundColor: '#eff6ff' },
  connectionBox_warn: { backgroundColor: '#fffbeb' },
  connectionBox_lock: { backgroundColor: '#fef2f2' },

  connectionLabel: {
    fontWeight: '700',
    fontSize: 13,
    marginBottom: 4,
  },
  connectionLabel_online: { color: '#047857' },
  connectionLabel_offline: { color: '#1d4ed8' },
  connectionLabel_warn: { color: '#b45309' },
  connectionLabel_lock: { color: '#b91c1c' },

  connectionText: {
    color: '#334155',
    fontSize: 12,
  },
  connectionHint: {
    marginTop: 4,
    color: '#475569',
    fontSize: 11,
    fontStyle: 'italic',
  },
  errorBox: {
    backgroundColor: '#fef2f2',
    borderColor: '#fecaca',
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginBottom: 14,
  },
  errorText: {
    color: '#b91c1c',
    fontSize: 13,
    lineHeight: 18,
  },
  button: {
    backgroundColor: '#2563eb',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonPressed: {
    backgroundColor: '#1d4ed8',
  },
  buttonInner: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  buttonText: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '700',
    letterSpacing: 0.2,
  },
  footer: {
    marginTop: 16,
    color: '#64748b',
    fontSize: 11,
    textAlign: 'center',
    lineHeight: 16,
  },
});
