import React from 'react';
import { Alert, Pressable, SafeAreaView, StyleSheet, Text, View } from 'react-native';

import { isDatabaseSupported, getDatabaseVersion } from '../db';

export default function SettingsScreen({ user, onLogout }) {
  const dbSupported = isDatabaseSupported();
  const dbVersion = getDatabaseVersion();

  const handleLogout = () => {
    Alert.alert('Log out', 'Are you sure you want to sign out?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Log out',
        style: 'destructive',
        onPress: () => onLogout?.(),
      },
    ]);
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.container}>
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Signed in as</Text>
          <View style={styles.card}>
            <Text style={styles.primary}>{user?.name || 'Worker'}</Text>
            <Text style={styles.secondary}>{user?.phone || '—'}</Text>
            <Text style={styles.meta}>ID: {user?.id || '—'}</Text>
            <Text style={styles.meta}>Role: {user?.role || 'worker'}</Text>
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Device storage</Text>
          <View style={styles.card}>
            <Text style={styles.secondary}>Local SQLite: {dbSupported ? `enabled (v${dbVersion})` : 'unsupported on this platform'}</Text>
            <Text style={styles.meta}>Journalled with WAL. Secure PIN hashing only.</Text>
          </View>
        </View>

        <View style={styles.section}>
          <Pressable onPress={handleLogout} style={({ pressed }) => [styles.logoutButton, pressed && styles.logoutButtonPressed]}>
            <Text style={styles.logoutText}>Log out</Text>
          </Pressable>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#f8fafc' },
  container: { padding: 20 },
  section: { marginTop: 18 },
  sectionTitle: { fontSize: 12, fontWeight: '700', color: '#475569', marginBottom: 10, textTransform: 'uppercase', letterSpacing: 0.5 },
  card: {
    backgroundColor: '#ffffff',
    borderRadius: 14,
    padding: 16,
    shadowColor: '#000',
    shadowOpacity: 0.05,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  primary: { fontSize: 18, fontWeight: '700', color: '#0f172a' },
  secondary: { marginTop: 2, fontSize: 14, color: '#334155' },
  meta: { marginTop: 4, fontSize: 12, color: '#64748b' },
  logoutButton: {
    backgroundColor: '#fee2e2',
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: 'center',
  },
  logoutButtonPressed: { backgroundColor: '#fecaca' },
  logoutText: { color: '#b91c1c', fontWeight: '700', fontSize: 15 },
});
