import React, { useMemo, useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import * as Crypto from 'expo-crypto';

import { getPatientById, insertRiskFlag, insertVisit, listPatientVisits } from '../db';
import { predictMaternalRisk } from '../services/inference';
import { calculateTrendAdjustment } from '../services/trend_engine';

function generateUuid() {
  if (typeof Crypto.randomUUID === 'function') {
    return Crypto.randomUUID();
  }

  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }

  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (character) => {
    const random = (Math.random() * 16) | 0;
    const value = character === 'x' ? random : (random & 0x3) | 0x8;
    return value.toString(16);
  });
}

export default function NewVisitScreen({ navigation, route, user }) {
  const patientId = route?.params?.patientId;
  const patientName = route?.params?.patientName || 'Patient';
  const workerId = user?.id || null;

  const [form, setForm] = useState({
    systolic_bp: '120',
    diastolic_bp: '80',
    blood_sugar: '90',
    body_temp_c: '37.0',
    heart_rate: '75',
  });

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const updateField = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }));
    setError('');
  };

  const adjustNumeric = (field, delta, step = 1, isFloat = false) => {
    setForm((current) => {
      const parsed = isFloat ? parseFloat(current[field]) || 0 : parseInt(current[field], 10) || 0;
      const nextVal = isFloat ? (parsed + delta * step).toFixed(1) : String(Math.max(0, parsed + delta * step));
      return { ...current, [field]: nextVal };
    });
    setError('');
  };

  const canSubmit = useMemo(() => {
    return (
      !saving &&
      patientId &&
      workerId &&
      form.systolic_bp.trim() &&
      form.diastolic_bp.trim() &&
      form.blood_sugar.trim() &&
      form.body_temp_c.trim() &&
      form.heart_rate.trim()
    );
  }, [saving, patientId, workerId, form]);

  const validate = () => {
    if (!patientId) {
      return 'No patient record selected for this visit.';
    }
    if (!workerId) {
      return 'No active worker account found to log this visit.';
    }

    const sys = Number(form.systolic_bp);
    if (!Number.isFinite(sys) || sys < 50 || sys > 260) {
      return 'Systolic BP must be between 50 and 260 mmHg.';
    }

    const dia = Number(form.diastolic_bp);
    if (!Number.isFinite(dia) || dia < 30 || dia > 180) {
      return 'Diastolic BP must be between 30 and 180 mmHg.';
    }

    if (dia >= sys) {
      return 'Diastolic BP must be lower than Systolic BP.';
    }

    const bs = Number(form.blood_sugar);
    if (!Number.isFinite(bs) || bs < 20 || bs > 500) {
      return 'Blood sugar must be a valid number between 20 and 500 mg/dL.';
    }

    const temp = Number(form.body_temp_c);
    if (!Number.isFinite(temp) || temp < 30.0 || temp > 45.0) {
      return 'Body temperature must be between 30.0 and 45.0 °C.';
    }

    const hr = Number(form.heart_rate);
    if (!Number.isFinite(hr) || hr < 30 || hr > 220) {
      return 'Heart rate must be between 30 and 220 bpm.';
    }

    return '';
  };

  const handleSubmit = async () => {
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setSaving(true);
    setError('');

    try {
      const now = new Date();
      const visitUuid = generateUuid();
      const visitDate = now.toISOString().split('T')[0];

      // 1. Fetch prior visits for trend analysis (before saving new visit)
      const priorVisits = listPatientVisits(patientId) || [];

      // 2. Save new visit record locally to SQLite
      const currentVisitData = {
        id: visitUuid,
        patient_id: patientId,
        worker_id: workerId,
        visit_date: visitDate,
        systolic_bp: Number(form.systolic_bp),
        diastolic_bp: Number(form.diastolic_bp),
        blood_sugar: Number(form.blood_sugar),
        body_temp_c: Number(form.body_temp_c),
        heart_rate: Number(form.heart_rate),
        created_locally_at: now.toISOString(),
        created_at: now.toISOString(),
      };

      const visitRecord = insertVisit(currentVisitData);
      if (!visitRecord) {
        throw new Error('Failed to save visit vitals locally.');
      }

      // 3. Fetch patient demographic age
      const patient = getPatientById(patientId);
      const patientAge = patient?.age || 25;

      // 4. Run on-device raw ML model inference
      const rawPrediction = predictMaternalRisk({
        age: patientAge,
        systolic_bp: Number(form.systolic_bp),
        diastolic_bp: Number(form.diastolic_bp),
        blood_sugar: Number(form.blood_sugar),
        body_temp: Number(form.body_temp_c),
        heart_rate: Number(form.heart_rate),
      });

      // 5. Evaluate multi-visit trend adjustment
      const trendResult = calculateTrendAdjustment(
        currentVisitData,
        priorVisits,
        rawPrediction.risk_level,
      );

      // 6. Save risk flag locally to SQLite
      const flagUuid = generateUuid();
      insertRiskFlag({
        id: flagUuid,
        visit_id: visitUuid,
        model_risk_level: trendResult.model_risk_level,
        trend_adjusted_level: trendResult.trend_adjusted_level,
        trend_reason: trendResult.trend_reason,
        created_at: now.toISOString(),
      });

      // 7. Navigate to Risk Result screen
      navigation?.replace?.('Risk Result', {
        patientId,
        patientName,
        riskLevel: trendResult.trend_adjusted_level,
        modelRiskLevel: trendResult.model_risk_level,
        trendReason: trendResult.trend_reason,
        escalated: trendResult.escalated,
        action: trendResult.action,
        vitals: form,
      });
    } catch (saveErr) {
      setError(saveErr?.message || 'Unable to save visit locally.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <KeyboardAvoidingView
        style={styles.container}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <Text style={styles.title}>New visit vitals</Text>
          <Text style={styles.subtitle}>Recording vitals for {patientName} (offline-first)</Text>

          {error ? (
            <View style={styles.errorCard}>
              <Text style={styles.errorText}>{error}</Text>
            </View>
          ) : null}

          {/* Blood Pressure Steppers */}
          <View style={styles.vitalsSection}>
            <Text style={styles.sectionHeader}>Blood Pressure (mmHg)</Text>
            <View style={styles.dualRow}>
              {/* Systolic */}
              <View style={styles.halfCol}>
                <Text style={styles.inputLabel}>Systolic</Text>
                <View style={styles.stepperWrap}>
                  <Pressable style={styles.stepBtn} onPress={() => adjustNumeric('systolic_bp', -5)}>
                    <Text style={styles.stepBtnText}>–</Text>
                  </Pressable>
                  <TextInput
                    value={form.systolic_bp}
                    onChangeText={(val) => updateField('systolic_bp', val.replace(/[^0-9]/g, ''))}
                    keyboardType="number-pad"
                    style={styles.stepperInput}
                  />
                  <Pressable style={styles.stepBtn} onPress={() => adjustNumeric('systolic_bp', 5)}>
                    <Text style={styles.stepBtnText}>+</Text>
                  </Pressable>
                </View>
              </View>

              {/* Diastolic */}
              <View style={styles.halfCol}>
                <Text style={styles.inputLabel}>Diastolic</Text>
                <View style={styles.stepperWrap}>
                  <Pressable style={styles.stepBtn} onPress={() => adjustNumeric('diastolic_bp', -5)}>
                    <Text style={styles.stepBtnText}>–</Text>
                  </Pressable>
                  <TextInput
                    value={form.diastolic_bp}
                    onChangeText={(val) => updateField('diastolic_bp', val.replace(/[^0-9]/g, ''))}
                    keyboardType="number-pad"
                    style={styles.stepperInput}
                  />
                  <Pressable style={styles.stepBtn} onPress={() => adjustNumeric('diastolic_bp', 5)}>
                    <Text style={styles.stepBtnText}>+</Text>
                  </Pressable>
                </View>
              </View>
            </View>
          </View>

          {/* Blood Sugar */}
          <View style={styles.vitalsSection}>
            <Text style={styles.inputLabel}>Blood Sugar (mg/dL)</Text>
            <View style={styles.stepperWrap}>
              <Pressable style={styles.stepBtn} onPress={() => adjustNumeric('blood_sugar', -5)}>
                <Text style={styles.stepBtnText}>–</Text>
              </Pressable>
              <TextInput
                value={form.blood_sugar}
                onChangeText={(val) => updateField('blood_sugar', val.replace(/[^0-9]/g, ''))}
                keyboardType="number-pad"
                style={styles.stepperInput}
              />
              <Pressable style={styles.stepBtn} onPress={() => adjustNumeric('blood_sugar', 5)}>
                <Text style={styles.stepBtnText}>+</Text>
              </Pressable>
            </View>
          </View>

          {/* Body Temperature */}
          <View style={styles.vitalsSection}>
            <Text style={styles.inputLabel}>Body Temperature (°C)</Text>
            <View style={styles.stepperWrap}>
              <Pressable style={styles.stepBtn} onPress={() => adjustNumeric('body_temp_c', -1, 0.2, true)}>
                <Text style={styles.stepBtnText}>–</Text>
              </Pressable>
              <TextInput
                value={form.body_temp_c}
                onChangeText={(val) => updateField('body_temp_c', val)}
                keyboardType="decimal-pad"
                style={styles.stepperInput}
              />
              <Pressable style={styles.stepBtn} onPress={() => adjustNumeric('body_temp_c', 1, 0.2, true)}>
                <Text style={styles.stepBtnText}>+</Text>
              </Pressable>
            </View>
          </View>

          {/* Heart Rate */}
          <View style={styles.vitalsSection}>
            <Text style={styles.inputLabel}>Heart Rate (bpm)</Text>
            <View style={styles.stepperWrap}>
              <Pressable style={styles.stepBtn} onPress={() => adjustNumeric('heart_rate', -5)}>
                <Text style={styles.stepBtnText}>–</Text>
              </Pressable>
              <TextInput
                value={form.heart_rate}
                onChangeText={(val) => updateField('heart_rate', val.replace(/[^0-9]/g, ''))}
                keyboardType="number-pad"
                style={styles.stepperInput}
              />
              <Pressable style={styles.stepBtn} onPress={() => adjustNumeric('heart_rate', 5)}>
                <Text style={styles.stepBtnText}>+</Text>
              </Pressable>
            </View>
          </View>

          <Pressable
            onPress={handleSubmit}
            disabled={!canSubmit || saving}
            style={({ pressed }) => [
              styles.submitButton,
              (!canSubmit || saving) && styles.submitButtonDisabled,
              pressed && canSubmit && styles.submitButtonPressed,
            ]}
          >
            {saving ? (
              <View style={styles.buttonInner}>
                <ActivityIndicator color="#ffffff" size="small" />
                <Text style={styles.submitButtonText}>Analyzing vitals…</Text>
              </View>
            ) : (
              <Text style={styles.submitButtonText}>Save visit & check risk</Text>
            )}
          </Pressable>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#f8fafc' },
  container: { flex: 1 },
  content: { padding: 20, paddingBottom: 40 },
  title: { fontSize: 26, fontWeight: '800', color: '#0f172a', marginBottom: 4 },
  subtitle: { fontSize: 14, color: '#64748b', marginBottom: 18 },
  errorCard: { backgroundColor: '#fef2f2', borderRadius: 12, padding: 12, marginBottom: 14 },
  errorText: { color: '#b91c1c', fontSize: 14, fontWeight: '600' },

  vitalsSection: { marginBottom: 18 },
  sectionHeader: { fontSize: 14, fontWeight: '700', color: '#0f172a', marginBottom: 10 },
  inputLabel: { fontSize: 13, fontWeight: '700', color: '#475569', marginBottom: 8 },
  dualRow: { flexDirection: 'row', gap: 12 },
  halfCol: { flex: 1 },

  stepperWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#ffffff',
    borderColor: '#cbd5e1',
    borderWidth: 1,
    borderRadius: 14,
    overflow: 'hidden',
  },
  stepBtn: {
    backgroundColor: '#f1f5f9',
    width: 48,
    height: 52,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepBtnText: { fontSize: 24, fontWeight: '700', color: '#1e293b' },
  stepperInput: {
    flex: 1,
    height: 52,
    fontSize: 20,
    fontWeight: '700',
    textAlign: 'center',
    color: '#0f172a',
  },

  submitButton: {
    marginTop: 24,
    backgroundColor: '#2563eb',
    borderRadius: 14,
    paddingVertical: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  submitButtonDisabled: { backgroundColor: '#93c5fd' },
  submitButtonPressed: { opacity: 0.9 },
  submitButtonText: { color: '#ffffff', fontSize: 17, fontWeight: '700' },
  buttonInner: { flexDirection: 'row', alignItems: 'center', gap: 8 },
});
