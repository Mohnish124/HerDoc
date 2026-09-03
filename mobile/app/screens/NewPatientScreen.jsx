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

import { insertPatient } from '../db';

function generatePatientUuid() {
  if (typeof Crypto.randomUUID === 'function') {
    return Crypto.randomUUID();
  }

  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }

  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (character) => {
    const random = Math.random() * 16 | 0;
    const value = character === 'x' ? random : (random & 0x3) | 0x8;
    return value.toString(16);
  });
}

export default function NewPatientScreen({ navigation, user }) {
  const [form, setForm] = useState({ name: '', age: '', village: '', edd: '', phone: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const workerId = user?.id || null;

  const canSubmit = useMemo(() => {
    return !saving && workerId && form.name.trim() && form.village.trim() && form.edd.trim() && form.age.trim();
  }, [saving, workerId, form]);

  const updateField = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }));
    setError('');
  };

  const validate = () => {
    if (!workerId) {
      return 'No active worker is available to attach this patient.';
    }

    if (!form.name.trim()) {
      return 'Name is required.';
    }

    const age = Number(form.age);
    if (!Number.isFinite(age) || age <= 0 || age > 120) {
      return 'Age must be a valid number greater than zero.';
    }

    if (!form.village.trim()) {
      return 'Village is required.';
    }

    if (!form.edd.trim()) {
      return 'EDD is required.';
    }

    const eddDate = new Date(form.edd);
    if (Number.isNaN(eddDate.getTime())) {
      return 'EDD must be a valid date in YYYY-MM-DD format.';
    }

    if (form.phone.trim()) {
      const trimmedPhone = form.phone.replace(/\D/g, '');
      if (trimmedPhone.length < 7 || trimmedPhone.length > 15) {
        return 'Phone must contain 7-15 digits when provided.';
      }
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
      const uuid = generatePatientUuid();
      const record = insertPatient({
        id: uuid,
        worker_id: workerId,
        name: form.name.trim(),
        age: Number(form.age),
        village: form.village.trim(),
        edd: form.edd.trim(),
        phone: form.phone.trim() || null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      });

      if (!record) {
        throw new Error('The patient could not be saved locally.');
      }

      navigation?.goBack?.();
    } catch (saveError) {
      setError(saveError?.message || 'Unable to save patient locally.');
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
          <Text style={styles.title}>New patient</Text>
          <Text style={styles.subtitle}>Saved locally on this device. No network call is required.</Text>

          {error ? (
            <View style={styles.errorCard}>
              <Text style={styles.errorText}>{error}</Text>
            </View>
          ) : null}

          <Text style={styles.label}>Name</Text>
          <TextInput
            value={form.name}
            onChangeText={(value) => updateField('name', value)}
            placeholder="Full name"
            style={styles.input}
            autoCapitalize="words"
            autoCorrect={false}
          />

          <Text style={styles.label}>Age</Text>
          <TextInput
            value={form.age}
            onChangeText={(value) => updateField('age', value.replace(/[^0-9]/g, ''))}
            placeholder="e.g. 28"
            keyboardType="number-pad"
            style={styles.input}
          />

          <Text style={styles.label}>Village</Text>
          <TextInput
            value={form.village}
            onChangeText={(value) => updateField('village', value)}
            placeholder="Village name"
            style={styles.input}
            autoCapitalize="words"
          />

          <Text style={styles.label}>EDD</Text>
          <TextInput
            value={form.edd}
            onChangeText={(value) => updateField('edd', value)}
            placeholder="YYYY-MM-DD"
            style={styles.input}
            keyboardType="default"
          />

          <Text style={styles.label}>Phone (optional)</Text>
          <TextInput
            value={form.phone}
            onChangeText={(value) => updateField('phone', value.replace(/[^0-9]/g, ''))}
            placeholder="Optional mobile number"
            keyboardType="phone-pad"
            style={styles.input}
          />

          <Pressable
            onPress={handleSubmit}
            disabled={!canSubmit}
            style={({ pressed }) => [styles.submitButton, (!canSubmit || saving) && styles.submitButtonDisabled, pressed && canSubmit && styles.submitButtonPressed]}
          >
            {saving ? (
              <View style={styles.buttonInner}>
                <ActivityIndicator color="#ffffff" size="small" />
                <Text style={styles.submitButtonText}>Saving…</Text>
              </View>
            ) : (
              <Text style={styles.submitButtonText}>Save patient</Text>
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
  content: { padding: 20, paddingBottom: 36 },
  title: { fontSize: 28, fontWeight: '800', color: '#0f172a', marginBottom: 6 },
  subtitle: { fontSize: 14, color: '#475569', marginBottom: 18 },
  label: { fontSize: 13, fontWeight: '700', color: '#0f172a', marginBottom: 8, marginTop: 14 },
  input: {
    backgroundColor: '#ffffff',
    borderColor: '#dbeafe',
    borderWidth: 1,
    borderRadius: 12,
    paddingVertical: 12,
    paddingHorizontal: 14,
    fontSize: 15,
    color: '#0f172a',
  },
  errorCard: {
    backgroundColor: '#fef2f2',
    borderRadius: 12,
    padding: 12,
    marginBottom: 14,
  },
  errorText: { color: '#b91c1c', fontSize: 14, fontWeight: '600' },
  submitButton: {
    marginTop: 22,
    backgroundColor: '#2563eb',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  submitButtonDisabled: { backgroundColor: '#93c5fd' },
  submitButtonPressed: { opacity: 0.9 },
  submitButtonText: { color: '#ffffff', fontSize: 16, fontWeight: '700' },
  buttonInner: { flexDirection: 'row', alignItems: 'center', gap: 8 },
});
