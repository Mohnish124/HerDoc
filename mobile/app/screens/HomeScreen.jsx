import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useFocusEffect } from '@react-navigation/native';

import {
  getPendingSyncItemsCount,
  getRiskFlagByVisitId,
  listAllPatients,
  listPatientVisits,
} from '../db';
import { getCurrentCoordinatesIfAvailable, sendEmergencySOS } from '../services/emergency';
import { getIsConnected, subscribeToConnectivityChanges } from '../services/connectivity';
import { subscribeToSyncState, synchronizeOfflineData } from '../services/sync';
import SyncStatusBadge from '../components/SyncStatusBadge';

function formatDate(value) {
  if (!value) {
    return 'No visit yet';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return 'No visit yet';
  }

  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

const RISK_BADGES = {
  green: { bg: '#dcfce7', text: '#15803d', label: 'Low Risk' },
  yellow: { bg: '#fef3c7', text: '#a16207', label: 'Moderate' },
  red: { bg: '#fee2e2', text: '#b91c1c', label: 'High Risk' },
};

export default function HomeScreen({ user, navigation }) {
  const [patients, setPatients] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [sosSending, setSosSending] = useState(false);

  // Sync state
  const [isSyncing, setIsSyncing] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);
  const [isConnected, setIsConnected] = useState(getIsConnected());

  const refreshPendingCount = useCallback(() => {
    const count = getPendingSyncItemsCount();
    setPendingCount(count);
  }, []);

  const loadPatients = useCallback(async () => {
    if (!user?.id) {
      setPatients([]);
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError('');
      const rows = await Promise.resolve(listAllPatients(user.id));
      const enriched = await Promise.all(
        (rows || []).map(async (patient) => {
          const visits = await Promise.resolve(listPatientVisits(patient.id));
          const lastVisit = visits?.length
            ? visits.reduce((latest, current) => {
                const latestDate = new Date(latest.visit_date || latest.created_locally_at || 0).getTime();
                const currentDate = new Date(current.visit_date || current.created_locally_at || 0).getTime();
                return currentDate > latestDate ? current : latest;
              }, visits[0])
            : null;

          const lastFlag = lastVisit ? getRiskFlagByVisitId(lastVisit.id) : null;

          return {
            ...patient,
            lastVisitDate: lastVisit?.visit_date || lastVisit?.created_locally_at || null,
            lastRiskLevel: lastFlag?.trend_adjusted_level || lastFlag?.model_risk_level || null,
          };
        }),
      );
      setPatients(enriched || []);
    } catch {
      setPatients([]);
      setError('Unable to load local patients.');
    } finally {
      setLoading(false);
      refreshPendingCount();
    }
  }, [user?.id, refreshPendingCount]);

  // Sync action
  const handleTriggerSync = useCallback(async () => {
    if (isSyncing) return;
    setIsSyncing(true);
    try {
      await synchronizeOfflineData({ force: true });
      await loadPatients();
    } finally {
      setIsSyncing(false);
      refreshPendingCount();
    }
  }, [isSyncing, loadPatients, refreshPendingCount]);

  // Subscribe to connectivity changes & trigger auto-sync on connectivity return
  useEffect(() => {
    const unsubscribeConn = subscribeToConnectivityChanges((connected) => {
      setIsConnected(connected);
      if (connected) {
        // Auto-sync when coming back online
        synchronizeOfflineData().then(() => {
          loadPatients();
        });
      }
    });

    const unsubscribeSync = subscribeToSyncState((syncState) => {
      if (syncState.isSyncing !== undefined) setIsSyncing(syncState.isSyncing);
      if (syncState.pendingCount !== undefined) setPendingCount(syncState.pendingCount);
    });

    return () => {
      unsubscribeConn();
      unsubscribeSync();
    };
  }, [loadPatients]);

  useFocusEffect(
    useCallback(() => {
      loadPatients();
      refreshPendingCount();

      // If online and pending items exist, sync automatically in background
      if (getIsConnected()) {
        synchronizeOfflineData().then(() => {
          refreshPendingCount();
        });
      }
    }, [loadPatients, refreshPendingCount]),
  );

  // Emergency SOS: confirm -> GPS (if available) -> backend -> result
  const notify = useCallback((title, message) => {
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      window.alert(`${title}\n\n${message}`);
    } else {
      Alert.alert(title, message);
    }
  }, []);

  const runSOS = useCallback(async () => {
    setSosSending(true);
    try {
      const coordinates = await getCurrentCoordinatesIfAvailable();
      await sendEmergencySOS({ coordinates });
      notify(
        'SOS sent',
        coordinates
          ? 'Emergency alert sent with your location.'
          : 'Emergency alert sent (location was not available).',
      );
    } catch (sosError) {
      notify('SOS failed', sosError?.message || 'Could not send the alert. Call emergency services directly.');
    } finally {
      setSosSending(false);
    }
  }, [notify]);

  const handleSOSPress = useCallback(() => {
    if (sosSending) return;
    const title = 'Send Emergency SOS?';
    const message = 'This will alert the emergency contact now and share your location if available.';
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      if (window.confirm(`${title}\n\n${message}`)) {
        runSOS();
      }
      return;
    }
    Alert.alert(title, message, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Send SOS', style: 'destructive', onPress: runSOS },
    ]);
  }, [sosSending, runSOS]);

  const filteredPatients = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();
    if (!normalizedSearch) {
      return patients;
    }

    return patients.filter((patient) =>
      String(patient?.name || '').toLowerCase().includes(normalizedSearch),
    );
  }, [patients, search]);

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.content}>
        {/* Top Sync & Action Header */}
        <View style={styles.topStatusRow}>
          <SyncStatusBadge
            isSyncing={isSyncing}
            pendingCount={pendingCount}
            onSyncPress={handleTriggerSync}
            isConnected={isConnected}
          />
          <Pressable
            style={styles.primaryButton}
            onPress={() => navigation?.navigate?.('New Patient')}
          >
            <Text style={styles.primaryButtonText}>+ New Patient</Text>
          </Pressable>
        </View>

        <Pressable
          style={[styles.sosButton, sosSending && styles.sosButtonDisabled]}
          onPress={handleSOSPress}
          disabled={sosSending}
          accessibilityRole="button"
          accessibilityLabel="Emergency SOS"
        >
          {sosSending ? (
            <ActivityIndicator size="small" color="#ffffff" />
          ) : (
            <Text style={styles.sosButtonText}>🚨 Emergency SOS</Text>
          )}
        </Pressable>

        <View style={styles.headerTextWrap}>
          <Text style={styles.eyebrow}>ASHA / ANM Field Worker</Text>
          <Text style={styles.title}>Registered Patients</Text>
        </View>

        <TextInput
          value={search}
          onChangeText={setSearch}
          placeholder="Search patients by name"
          placeholderTextColor="#94a3b8"
          style={styles.searchInput}
          autoCapitalize="none"
          autoCorrect={false}
        />

        {loading ? (
          <View style={styles.stateCard}>
            <ActivityIndicator size="small" color="#2563eb" />
            <Text style={styles.stateText}>Loading local records…</Text>
          </View>
        ) : null}

        {!loading && error ? (
          <View style={styles.errorCard}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        ) : null}

        {!loading && !error && filteredPatients.length === 0 ? (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyTitle}>
              {search.trim() ? 'No matching patients' : 'No patients yet'}
            </Text>
            <Text style={styles.emptyText}>
              {search.trim()
                ? `No local records match "${search.trim()}".`
                : 'Create a new patient to begin storing local records offline.'}
            </Text>
            {!search.trim() ? (
              <Pressable
                style={styles.secondaryButton}
                onPress={() => navigation?.navigate?.('New Patient')}
              >
                <Text style={styles.secondaryButtonText}>Add patient</Text>
              </Pressable>
            ) : null}
          </View>
        ) : null}

        {!loading && !error && filteredPatients.length > 0 ? (
          <View style={styles.patientList}>
            {filteredPatients.map((patient) => (
              <Pressable
                key={patient.id}
                style={styles.patientCard}
                onPress={() =>
                  navigation?.navigate?.('Patient History', { patientId: patient.id })
                }
              >
                <View style={styles.patientHeader}>
                  <View>
                    <Text style={styles.patientName}>{patient.name}</Text>
                    <Text style={styles.patientVillage}>
                      {patient.village || 'Village not provided'}
                    </Text>
                  </View>
                  {patient.lastRiskLevel && RISK_BADGES[patient.lastRiskLevel] ? (
                    <View
                      style={[
                        styles.riskBadge,
                        { backgroundColor: RISK_BADGES[patient.lastRiskLevel].bg },
                      ]}
                    >
                      <Text
                        style={[
                          styles.riskText,
                          { color: RISK_BADGES[patient.lastRiskLevel].text },
                        ]}
                      >
                        {RISK_BADGES[patient.lastRiskLevel].label}
                      </Text>
                    </View>
                  ) : (
                    <View style={[styles.riskBadge, { backgroundColor: '#f1f5f9' }]}>
                      <Text style={[styles.riskText, { color: '#64748b' }]}>No visit</Text>
                    </View>
                  )}
                </View>

                {/* Review status from doctor if reviewed */}
                {patient.review_status && patient.review_status !== 'pending' ? (
                  <View style={styles.reviewNoticeRow}>
                    <Text style={styles.reviewNoticeText}>
                      Doctor status: <Text style={styles.reviewStatusBold}>{patient.review_status.toUpperCase()}</Text>
                      {patient.review_notes ? ` — "${patient.review_notes}"` : ''}
                    </Text>
                  </View>
                ) : null}

                <View style={styles.metaRow}>
                  <Text style={styles.metaLabel}>Last visit</Text>
                  <Text style={styles.metaValue}>{formatDate(patient.lastVisitDate)}</Text>
                </View>
              </Pressable>
            ))}
          </View>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#f8fafc' },
  content: { padding: 20, paddingTop: 12, paddingBottom: 36 },
  topStatusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  headerTextWrap: { marginBottom: 14 },
  eyebrow: {
    fontSize: 12,
    textTransform: 'uppercase',
    letterSpacing: 1,
    color: '#64748b',
    marginBottom: 2,
  },
  title: { fontSize: 26, fontWeight: '800', color: '#0f172a' },
  sosButton: {
    backgroundColor: '#dc2626',
    borderRadius: 14,
    paddingVertical: 16,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
    minHeight: 54,
  },
  sosButtonDisabled: { opacity: 0.7 },
  sosButtonText: { color: '#ffffff', fontSize: 18, fontWeight: '800' },
  primaryButton: {
    backgroundColor: '#2563eb',
    borderRadius: 12,
    paddingVertical: 9,
    paddingHorizontal: 14,
  },
  primaryButtonText: { fontSize: 13, fontWeight: '700', color: '#ffffff' },
  searchInput: {
    backgroundColor: '#ffffff',
    borderColor: '#dbeafe',
    borderWidth: 1,
    borderRadius: 12,
    paddingVertical: 12,
    paddingHorizontal: 14,
    fontSize: 15,
    color: '#0f172a',
    marginBottom: 14,
  },
  stateCard: {
    backgroundColor: '#ffffff',
    borderRadius: 12,
    padding: 18,
    alignItems: 'center',
    marginBottom: 12,
  },
  stateText: { marginTop: 8, color: '#475569', fontSize: 14 },
  errorCard: {
    backgroundColor: '#fef2f2',
    borderRadius: 12,
    padding: 14,
    marginBottom: 12,
  },
  errorText: { color: '#b91c1c', fontSize: 14, fontWeight: '600' },
  emptyCard: {
    backgroundColor: '#ffffff',
    borderRadius: 12,
    padding: 20,
    alignItems: 'center',
    marginTop: 8,
  },
  emptyTitle: {
    color: '#0f172a',
    fontSize: 18,
    fontWeight: '700',
    marginBottom: 6,
  },
  emptyText: { color: '#64748b', fontSize: 14, textAlign: 'center', marginBottom: 12 },
  secondaryButton: {
    backgroundColor: '#dbeafe',
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 14,
  },
  secondaryButtonText: { color: '#1d4ed8', fontWeight: '700' },
  patientList: { marginTop: 6 },
  patientCard: {
    backgroundColor: '#ffffff',
    borderRadius: 14,
    padding: 16,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOpacity: 0.04,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
    borderWidth: 1,
    borderColor: '#f1f5f9',
  },
  patientHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 10,
  },
  patientName: { fontSize: 18, fontWeight: '700', color: '#0f172a' },
  patientVillage: { fontSize: 13, color: '#475569', marginTop: 3 },
  riskBadge: {
    borderRadius: 999,
    paddingVertical: 5,
    paddingHorizontal: 9,
  },
  riskText: { fontSize: 11, fontWeight: '800', textTransform: 'uppercase' },

  reviewNoticeRow: {
    backgroundColor: '#f0fdf4',
    borderColor: '#bbf7d0',
    borderWidth: 1,
    borderRadius: 8,
    paddingVertical: 6,
    paddingHorizontal: 10,
    marginBottom: 10,
  },
  reviewNoticeText: { fontSize: 12, color: '#166534' },
  reviewStatusBold: { fontWeight: '800' },

  metaRow: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 4 },
  metaLabel: { color: '#64748b', fontSize: 12, fontWeight: '600' },
  metaValue: { color: '#0f172a', fontSize: 12, fontWeight: '600' },
});
