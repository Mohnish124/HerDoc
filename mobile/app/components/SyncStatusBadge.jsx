import React from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

export default function SyncStatusBadge({ isSyncing = false, pendingCount = 0, onSyncPress, isConnected = true }) {
  if (isSyncing) {
    return (
      <View style={[styles.badge, styles.syncingBadge]}>
        <ActivityIndicator size="small" color="#2563eb" style={styles.spinner} />
        <Text style={styles.syncingText}>Syncing…</Text>
      </View>
    );
  }

  if (pendingCount > 0) {
    return (
      <Pressable
        onPress={onSyncPress}
        style={({ pressed }) => [
          styles.badge,
          styles.pendingBadge,
          pressed && styles.badgePressed,
        ]}
      >
        <View style={styles.pendingDot} />
        <Text style={styles.pendingText}>
          {pendingCount} {pendingCount === 1 ? 'record' : 'records'} pending
        </Text>
        {isConnected ? <Text style={styles.syncNowAction}>• Sync now</Text> : <Text style={styles.offlineAction}>• Offline</Text>}
      </Pressable>
    );
  }

  return (
    <Pressable
      onPress={onSyncPress}
      style={({ pressed }) => [styles.badge, styles.syncedBadge, pressed && styles.badgePressed]}
    >
      <Text style={styles.syncedCheck}>✓</Text>
      <Text style={styles.syncedText}>Synced</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 999,
    borderWidth: 1,
    gap: 6,
  },
  badgePressed: { opacity: 0.8 },
  spinner: { marginRight: 2 },

  syncingBadge: {
    backgroundColor: '#eff6ff',
    borderColor: '#bfdbfe',
  },
  syncingText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#2563eb',
  },

  pendingBadge: {
    backgroundColor: '#fffbeb',
    borderColor: '#fde68a',
  },
  pendingDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    backgroundColor: '#d97706',
  },
  pendingText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#b45309',
  },
  syncNowAction: {
    fontSize: 12,
    fontWeight: '700',
    color: '#2563eb',
  },
  offlineAction: {
    fontSize: 11,
    fontWeight: '600',
    color: '#94a3b8',
  },

  syncedBadge: {
    backgroundColor: '#f0fdf4',
    borderColor: '#bbf7d0',
  },
  syncedCheck: {
    fontSize: 12,
    fontWeight: '800',
    color: '#16a34a',
  },
  syncedText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#15803d',
  },
});
