import React from 'react';
import {
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

const RISK_THEMES = {
  green: {
    bg: '#dcfce7',
    border: '#86efac',
    titleColor: '#15803d',
    badgeBg: '#16a34a',
    badgeText: '#ffffff',
    label: 'Low Risk',
    action: 'Continue routine care',
    instruction: 'Schedule the next standard antenatal checkup per routine care protocol.',
  },
  yellow: {
    bg: '#fef3c7',
    border: '#fde047',
    titleColor: '#a16207',
    badgeBg: '#eab308',
    badgeText: '#854d0e',
    label: 'Moderate Risk',
    action: 'Recheck in 1 week',
    instruction: 'Advise rest, monitor symptoms, and perform a follow-up vitals check within 7 days.',
  },
  red: {
    bg: '#fee2e2',
    border: '#fca5a5',
    titleColor: '#b91c1c',
    badgeBg: '#dc2626',
    badgeText: '#ffffff',
    label: 'High Risk',
    action: 'Refer to PHC within 24 hours',
    instruction: 'Urgent medical attention required. Arrange safe transport to the nearest PHC immediately.',
  },
};

export default function RiskResultScreen({ navigation, route }) {
  const patientId = route?.params?.patientId;
  const patientName = route?.params?.patientName || 'Patient';
  const riskLevel = String(route?.params?.riskLevel || 'yellow').toLowerCase();
  const trendReason = route?.params?.trendReason || null;
  const escalated = Boolean(route?.params?.escalated || trendReason);
  const vitals = route?.params?.vitals || {};

  const theme = RISK_THEMES[riskLevel] || RISK_THEMES.yellow;

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.eyebrow}>On-Device Triage Result</Text>
        <Text style={styles.patientTitle}>{patientName}</Text>

        {/* Big Color Flag Card */}
        <View style={[styles.flagCard, { backgroundColor: theme.bg, borderColor: theme.border }]}>
          <View style={[styles.badge, { backgroundColor: theme.badgeBg }]}>
            <Text style={[styles.badgeText, { color: theme.badgeText }]}>{theme.label}</Text>
          </View>

          <Text style={[styles.actionText, { color: theme.titleColor }]}>{theme.action}</Text>
          <Text style={styles.instructionText}>{theme.instruction}</Text>
        </View>

        {/* Trend Escalation Card (When multi-visit pattern triggered escalation) */}
        {trendReason ? (
          <View style={styles.trendAlertCard}>
            <View style={styles.trendHeaderRow}>
              <View style={styles.trendIconWrap}>
                <Text style={styles.trendIcon}>↗</Text>
              </View>
              <View style={styles.trendTextWrap}>
                <Text style={styles.trendAlertTitle}>Trend Pattern Detected</Text>
                <Text style={styles.trendAlertReason}>{trendReason}</Text>
                <Text style={styles.trendAlertSub}>
                  Flag escalated based on sustained rise across consecutive visits.
                </Text>
              </View>
            </View>
          </View>
        ) : null}

        {/* Vitals Summary Card */}
        <View style={styles.summaryCard}>
          <Text style={styles.summaryTitle}>Recorded Visit Vitals</Text>
          <View style={styles.vitalsGrid}>
            <View style={styles.vitalItem}>
              <Text style={styles.vitalLabel}>Blood Pressure</Text>
              <Text style={styles.vitalValue}>
                {vitals.systolic_bp || '—'}/{vitals.diastolic_bp || '—'}
                <Text style={styles.unit}> mmHg</Text>
              </Text>
            </View>

            <View style={styles.vitalItem}>
              <Text style={styles.vitalLabel}>Blood Sugar</Text>
              <Text style={styles.vitalValue}>
                {vitals.blood_sugar || '—'}
                <Text style={styles.unit}> mg/dL</Text>
              </Text>
            </View>

            <View style={styles.vitalItem}>
              <Text style={styles.vitalLabel}>Body Temp</Text>
              <Text style={styles.vitalValue}>
                {vitals.body_temp_c || '—'}
                <Text style={styles.unit}> °C</Text>
              </Text>
            </View>

            <View style={styles.vitalItem}>
              <Text style={styles.vitalLabel}>Heart Rate</Text>
              <Text style={styles.vitalValue}>
                {vitals.heart_rate || '—'}
                <Text style={styles.unit}> bpm</Text>
              </Text>
            </View>
          </View>
        </View>

        {/* Action Buttons */}
        <Pressable
          style={styles.primaryButton}
          onPress={() => navigation?.navigate?.('Patient History', { patientId })}
        >
          <Text style={styles.primaryButtonText}>View Patient History & Trend</Text>
        </Pressable>

        <Pressable
          style={styles.secondaryButton}
          onPress={() => navigation?.navigate?.('Home')}
        >
          <Text style={styles.secondaryButtonText}>Return to Home</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#f8fafc' },
  content: { padding: 20, paddingBottom: 40 },
  eyebrow: { fontSize: 13, textTransform: 'uppercase', letterSpacing: 1, color: '#64748b', marginBottom: 4 },
  patientTitle: { fontSize: 26, fontWeight: '800', color: '#0f172a', marginBottom: 18 },

  flagCard: {
    borderRadius: 18,
    borderWidth: 2,
    padding: 24,
    alignItems: 'center',
    marginBottom: 16,
    shadowColor: '#000',
    shadowOpacity: 0.05,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
    elevation: 3,
  },
  badge: {
    borderRadius: 999,
    paddingVertical: 8,
    paddingHorizontal: 18,
    marginBottom: 14,
  },
  badgeText: {
    fontSize: 14,
    fontWeight: '800',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  actionText: {
    fontSize: 22,
    fontWeight: '800',
    textAlign: 'center',
    marginBottom: 10,
  },
  instructionText: {
    fontSize: 15,
    color: '#475569',
    textAlign: 'center',
    lineHeight: 22,
  },

  trendAlertCard: {
    backgroundColor: '#fff7ed',
    borderColor: '#fed7aa',
    borderWidth: 1.5,
    borderRadius: 14,
    padding: 16,
    marginBottom: 18,
  },
  trendHeaderRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  trendIconWrap: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#ffedd5',
    alignItems: 'center',
    justifyContent: 'center',
  },
  trendIcon: { fontSize: 18, fontWeight: '800', color: '#c2410c' },
  trendTextWrap: { flex: 1 },
  trendAlertTitle: { fontSize: 15, fontWeight: '800', color: '#9a3412', marginBottom: 4 },
  trendAlertReason: { fontSize: 14, fontWeight: '600', color: '#7c2d12', marginBottom: 4, lineHeight: 20 },
  trendAlertSub: { fontSize: 12, color: '#9a3412', opacity: 0.8 },

  summaryCard: {
    backgroundColor: '#ffffff',
    borderRadius: 16,
    padding: 18,
    marginBottom: 24,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  summaryTitle: { fontSize: 16, fontWeight: '700', color: '#0f172a', marginBottom: 14 },
  vitalsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  vitalItem: {
    width: '47%',
    backgroundColor: '#f8fafc',
    borderRadius: 10,
    padding: 12,
  },
  vitalLabel: { fontSize: 12, fontWeight: '600', color: '#64748b', marginBottom: 4 },
  vitalValue: { fontSize: 17, fontWeight: '800', color: '#0f172a' },
  unit: { fontSize: 13, fontWeight: '500', color: '#94a3b8' },

  primaryButton: {
    backgroundColor: '#2563eb',
    borderRadius: 14,
    paddingVertical: 15,
    alignItems: 'center',
    marginBottom: 12,
  },
  primaryButtonText: { color: '#ffffff', fontSize: 16, fontWeight: '700' },
  secondaryButton: {
    backgroundColor: '#ffffff',
    borderColor: '#cbd5e1',
    borderWidth: 1,
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: 'center',
  },
  secondaryButtonText: { color: '#334155', fontSize: 15, fontWeight: '700' },
});
