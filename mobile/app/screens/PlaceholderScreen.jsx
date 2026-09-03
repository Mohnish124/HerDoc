import React from 'react';
import { SafeAreaView, StyleSheet, Text, View } from 'react-native';

export default function PlaceholderScreen({ title, subtitle, description }) {
  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.container}>
        <Text style={styles.title}>{title || 'Coming soon'}</Text>
        {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
        <View style={styles.badge}>
          <Text style={styles.badgeText}>Placeholder</Text>
        </View>
        {description ? <Text style={styles.description}>{description}</Text> : null}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#fff' },
  container: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  title: { fontSize: 24, fontWeight: '700', color: '#0f172a' },
  subtitle: { marginTop: 6, color: '#475569', fontSize: 15 },
  badge: {
    marginTop: 18,
    backgroundColor: '#f1f5f9',
    borderRadius: 999,
    paddingHorizontal: 14,
    paddingVertical: 6,
  },
  badgeText: { color: '#64748b', fontSize: 12, fontWeight: '600' },
  description: { marginTop: 18, color: '#64748b', textAlign: 'center', lineHeight: 20, fontSize: 13 },
});
