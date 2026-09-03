import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useFocusEffect } from '@react-navigation/native';

import { getPatientById, getRiskFlagsByVisitIds, listPatientVisits } from '../db';
import VitalsTrendChart from '../components/VitalsTrendChart';

function formatDate(value) {
  if (!value) {
    return 'Unknown date';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

const RISK_BADGES = {
  green: { bg: '#dcfce7', text: '#15803d', label: 'Low Risk' },
  yellow: { bg: '#fef3c7', text: '#a16207', label: 'Moderate' },
  red: { bg: '#fee2e2', text: '#b91c1c', label: 'High Risk' },
};

export default function PatientHistoryScreen({ navigation, route }) {
  const patientId = route?.params?.patientId;
  const [patient, setPatient] = useState(null);
  const [visits, setVisits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadData = useCallback(() => {
    if (!patientId) {
      setError('No patient ID provided.');
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError('');
      const patientRecord = getPatientById(patientId);
      const visitRecords = listPatientVisits(patientId);
      const visitIds = (visitRecords || []).map((v) => v.id);
      const flags = getRiskFlagsByVisitIds(visitIds);
      const flagMap = (flags || []).reduce((acc, f) => {
        acc[f.visit_id] = f;
        return acc;
      }, {});

      const enrichedVisits = (visitRecords || []).map((v) => ({
        ...v,
        riskFlag: flagMap[v.id] || null,
      }));

      setPatient(patientRecord || null);
      setVisits(enrichedVisits || []);
    } catch {
      setError('Unable to load patient records from local database.');
    } finally {
      setLoading(false);
    }
  }, [patientId]);

  useFocusEffect(
    useCallback(() => {
      loadData();
    }, [loadData]),
  );

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.content}>
        {loading ? (
          <View style={styles.stateCard}>
            <ActivityIndicator size="small" color="#2563eb" />
            <Text style={styles.stateText}>Loading patient records…</Text>
          </View>
        ) : null}

        {!loading && error ? (
          <View style={styles.errorCard}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        ) : null}

        {!loading && !patient && !error ? (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyTitle}>Patient not found</Text>
            <Text style={styles.emptyText}>This patient record could not be found locally.</Text>
            <Pressable style={styles.secondaryButton} onPress={() => navigation?.goBack?.()}>
              <Text style={styles.secondaryButtonText}>Go back</Text>
            </Pressable>
          </View>
        ) : null}

        {!loading && patient ? (
          <>
            {/* Patient Header Card */}
            <View style={styles.profileCard}>
              <View style={styles.profileHeader}>
                <View>
                  <Text style={styles.profileName}>{patient.name}</Text>
                  <Text style={styles.profileVillage}>{patient.village || 'Village not specified'}</Text>
                </View>
                <Pressable
                  style={styles.newVisitButton}
                  onPress={() =>
                    navigation?.navigate?.('New Visit', {
                      patientId: patient.id,
                      patientName: patient.name,
                    })
                  }
                >
                  <Text style={styles.newVisitButtonText}>+ New Visit</Text>
                </Pressable>
              </View>

              <View style={styles.divider} />

              <View style={styles.infoGrid}>
                <View style={styles.infoItem}>
                  <Text style={styles.infoLabel}>Age</Text>
                  <Text style={styles.infoValue}>{patient.age ? `${patient.age} yrs` : '—'}</Text>
                </View>
                <View style={styles.infoItem}>
                  <Text style={styles.infoLabel}>EDD</Text>
                  <Text style={styles.infoValue}>{patient.edd || '—'}</Text>
                </View>
                <View style={styles.infoItem}>
                  <Text style={styles.infoLabel}>Phone</Text>
                  <Text style={styles.infoValue}>{patient.phone || '—'}</Text>
                </View>
              </View>
            </View>

            {/* Vitals Trend Chart (Visible when >= 2 visits exist) */}
            {visits.length >= 2 ? <VitalsTrendChart visits={visits} /> : null}

            {/* Visit History Section */}
            <View style={styles.sectionHeaderRow}>
              <Text style={styles.sectionTitle}>Visit History</Text>
              <Text style={styles.sectionBadge}>
                {visits.length} {visits.length === 1 ? 'visit' : 'visits'}
              </Text>
            </View>

            {visits.length === 0 ? (
              <View style={styles.emptyCard}>
                <Text style={styles.emptyTitle}>No visits recorded yet</Text>
                <Text style={styles.emptyText}>
                  Record the patient’s initial vitals to start tracking their pregnancy health offline.
                </Text>
                <Pressable
                  style={styles.primaryActionButton}
                  onPress={() =>
                    navigation?.navigate?.('New Visit', {
                      patientId: patient.id,
                      patientName: patient.name,
                    })
                  }
                >
                  <Text style={styles.primaryActionButtonText}>Record First Visit</Text>
                </Pressable>
              </View>
            ) : (
              <View style={styles.visitList}>
                {visits.map((visit, index) => {
                  const effectiveRisk =
                    visit.riskFlag?.trend_adjusted_level || visit.riskFlag?.model_risk_level || null;

                  return (
                    <View key={visit.id || index} style={styles.visitCard}>
                      <View style={styles.visitCardHeader}>
                        <View>
                          <Text style={styles.visitDateText}>
                            {formatDate(visit.visit_date || visit.created_locally_at)}
                          </Text>
                          <Text style={styles.visitSubText}>Recorded offline on device</Text>
                        </View>
                        <View style={styles.badgeGroup}>
                          {effectiveRisk && RISK_BADGES[effectiveRisk] ? (
                            <View
                              style={[
                                styles.riskFlagBadge,
                                { backgroundColor: RISK_BADGES[effectiveRisk].bg },
                              ]}
                            >
                              <Text
                                style={[
                                  styles.riskFlagText,
                                  { color: RISK_BADGES[effectiveRisk].text },
                                ]}
                              >
                                {RISK_BADGES[effectiveRisk].label}
                              </Text>
                            </View>
                          ) : null}
                          <View style={styles.visitIndexBadge}>
                            <Text style={styles.visitIndexText}>Visit #{visits.length - index}</Text>
                          </View>
                        </View>
                      </View>

                      {/* Trend Escalation Indicator */}
                      {visit.riskFlag?.trend_reason ? (
                        <View style={styles.trendReasonBanner}>
                          <Text style={styles.trendReasonText}>
                            ↗ {visit.riskFlag.trend_reason}
                          </Text>
                        </View>
                      ) : null}

                      <View style={styles.vitalsGrid}>
                        <View style={styles.vitalBox}>
                          <Text style={styles.vitalLabel}>Blood Pressure</Text>
                          <Text style={styles.vitalValue}>
                            {visit.systolic_bp != null && visit.diastolic_bp != null
                              ? `${visit.systolic_bp}/${visit.diastolic_bp}`
                              : '—'}
                            <Text style={styles.vitalUnit}> mmHg</Text>
                          </Text>
                        </View>

                        <View style={styles.vitalBox}>
                          <Text style={styles.vitalLabel}>Blood Sugar</Text>
                          <Text style={styles.vitalValue}>
                            {visit.blood_sugar != null ? visit.blood_sugar : '—'}
                            <Text style={styles.vitalUnit}> mg/dL</Text>
                          </Text>
                        </View>

                        <View style={styles.vitalBox}>
                          <Text style={styles.vitalLabel}>Body Temp</Text>
                          <Text style={styles.vitalValue}>
                            {visit.body_temp_c != null ? visit.body_temp_c : '—'}
                            <Text style={styles.vitalUnit}> °C</Text>
                          </Text>
                        </View>

                        <View style={styles.vitalBox}>
                          <Text style={styles.vitalLabel}>Heart Rate</Text>
                          <Text style={styles.vitalValue}>
                            {visit.heart_rate != null ? visit.heart_rate : '—'}
                            <Text style={styles.vitalUnit}> bpm</Text>
                          </Text>
                        </View>
                      </View>
                    </View>
                  );
                })}
              </View>
            )}
          </>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#f8fafc' },
  content: { padding: 20, paddingTop: 12, paddingBottom: 40 },
  stateCard: { backgroundColor: '#ffffff', borderRadius: 12, padding: 18, alignItems: 'center', marginBottom: 12 },
  stateText: { marginTop: 8, color: '#475569', fontSize: 14 },
  errorCard: { backgroundColor: '#fef2f2', borderRadius: 12, padding: 14, marginBottom: 12 },
  errorText: { color: '#b91c1c', fontSize: 14, fontWeight: '600' },
  emptyCard: { backgroundColor: '#ffffff', borderRadius: 14, padding: 24, alignItems: 'center', marginTop: 12 },
  emptyTitle: { color: '#0f172a', fontSize: 18, fontWeight: '700', marginBottom: 6 },
  emptyText: { color: '#64748b', fontSize: 14, textAlign: 'center', marginBottom: 16, lineHeight: 20 },
  secondaryButton: { backgroundColor: '#dbeafe', borderRadius: 10, paddingVertical: 10, paddingHorizontal: 16 },
  secondaryButtonText: { color: '#1d4ed8', fontWeight: '700' },
  primaryActionButton: { backgroundColor: '#2563eb', borderRadius: 12, paddingVertical: 12, paddingHorizontal: 20 },
  primaryActionButtonText: { color: '#ffffff', fontSize: 15, fontWeight: '700' },

  profileCard: {
    backgroundColor: '#ffffff',
    borderRadius: 16,
    padding: 18,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOpacity: 0.05,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  profileHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  profileName: { fontSize: 22, fontWeight: '800', color: '#0f172a' },
  profileVillage: { fontSize: 14, color: '#64748b', marginTop: 2 },
  newVisitButton: {
    backgroundColor: '#2563eb',
    borderRadius: 12,
    paddingVertical: 8,
    paddingHorizontal: 14,
  },
  newVisitButtonText: { color: '#ffffff', fontSize: 14, fontWeight: '700' },
  divider: { height: 1, backgroundColor: '#f1f5f9', marginVertical: 14 },
  infoGrid: { flexDirection: 'row', justifyContent: 'space-between' },
  infoItem: { flex: 1 },
  infoLabel: { fontSize: 11, fontWeight: '700', textTransform: 'uppercase', color: '#94a3b8', marginBottom: 4 },
  infoValue: { fontSize: 15, fontWeight: '600', color: '#0f172a' },

  sectionHeaderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  sectionTitle: { fontSize: 18, fontWeight: '800', color: '#0f172a' },
  sectionBadge: { fontSize: 13, fontWeight: '600', color: '#64748b', backgroundColor: '#e2e8f0', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 999 },

  visitList: { gap: 14 },
  visitCard: {
    backgroundColor: '#ffffff',
    borderRadius: 14,
    padding: 16,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  visitCardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 },
  visitDateText: { fontSize: 16, fontWeight: '700', color: '#0f172a' },
  visitSubText: { fontSize: 12, color: '#94a3b8', marginTop: 2 },
  badgeGroup: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  riskFlagBadge: { borderRadius: 8, paddingVertical: 4, paddingHorizontal: 8 },
  riskFlagText: { fontSize: 11, fontWeight: '800', textTransform: 'uppercase' },
  visitIndexBadge: { backgroundColor: '#f1f5f9', borderRadius: 8, paddingVertical: 4, paddingHorizontal: 8 },
  visitIndexText: { fontSize: 11, fontWeight: '700', color: '#475569' },

  trendReasonBanner: {
    backgroundColor: '#fff7ed',
    borderColor: '#fed7aa',
    borderWidth: 1,
    borderRadius: 8,
    paddingVertical: 6,
    paddingHorizontal: 10,
    marginBottom: 12,
  },
  trendReasonText: { fontSize: 12, fontWeight: '700', color: '#c2410c' },

  vitalsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  vitalBox: {
    backgroundColor: '#f8fafc',
    borderRadius: 10,
    padding: 10,
    width: '48%',
  },
  vitalLabel: { fontSize: 11, fontWeight: '600', color: '#64748b', marginBottom: 4 },
  vitalValue: { fontSize: 16, fontWeight: '800', color: '#0f172a' },
  vitalUnit: { fontSize: 12, fontWeight: '500', color: '#94a3b8' },
});
