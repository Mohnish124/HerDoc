import React, { useState } from 'react';
import { Dimensions, Pressable, StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, Line, Polyline, Rect, Text as SvgText } from 'react-native-svg';

const SCREEN_WIDTH = Dimensions.get('window').width;

export default function VitalsTrendChart({ visits = [] }) {
  const [activeMetric, setActiveMetric] = useState('bp'); // 'bp' | 'bs'

  if (!visits || visits.length < 2) {
    return (
      <View style={styles.emptyContainer}>
        <Text style={styles.emptyTitle}>Trend Chart Unavailable</Text>
        <Text style={styles.emptyText}>At least 2 visits are required to visualize physiological trends.</Text>
      </View>
    );
  }

  // Sort visits chronologically (oldest -> newest)
  const chronological = [...visits].sort((a, b) => {
    const timeA = new Date(a.visit_date || a.created_locally_at || 0).getTime();
    const timeB = new Date(b.visit_date || b.created_locally_at || 0).getTime();
    return timeA - timeB;
  });

  const chartWidth = Math.min(SCREEN_WIDTH - 40, 500);
  const chartHeight = 180;
  const padding = { top: 25, bottom: 30, left: 40, right: 20 };
  const innerWidth = chartWidth - padding.left - padding.right;
  const innerHeight = chartHeight - padding.top - padding.bottom;

  const n = chronological.length;

  if (activeMetric === 'bp') {
    // Collect BP values
    const sysVals = chronological.map((v) => Number(v.systolic_bp) || 120);
    const diaVals = chronological.map((v) => Number(v.diastolic_bp) || 80);
    const allVals = [...sysVals, ...diaVals];

    const minY = Math.floor(Math.min(...allVals, 60) / 10) * 10;
    const maxY = Math.ceil(Math.max(...allVals, 150) / 10) * 10;
    const rangeY = maxY - minY || 1;

    const getX = (index) => padding.left + (index / (n - 1)) * innerWidth;
    const getY = (val) => padding.top + innerHeight - ((val - minY) / rangeY) * innerHeight;

    const sysPoints = chronological.map((_, i) => `${getX(i)},${getY(sysVals[i])}`).join(' ');
    const diaPoints = chronological.map((_, i) => `${getX(i)},${getY(diaVals[i])}`).join(' ');

    return (
      <View style={styles.card}>
        <View style={styles.header}>
          <Text style={styles.title}>Vitals Trend Over Time</Text>
          <View style={styles.toggleRow}>
            <Pressable style={[styles.toggleBtn, styles.toggleActive]} onPress={() => setActiveMetric('bp')}>
              <Text style={[styles.toggleText, styles.toggleTextActive]}>Blood Pressure</Text>
            </Pressable>
            <Pressable style={styles.toggleBtn} onPress={() => setActiveMetric('bs')}>
              <Text style={styles.toggleText}>Blood Sugar</Text>
            </Pressable>
          </View>
        </View>

        <View style={styles.legendRow}>
          <View style={styles.legendItem}>
            <View style={[styles.legendDot, { backgroundColor: '#2563eb' }]} />
            <Text style={styles.legendLabel}>Systolic (mmHg)</Text>
          </View>
          <View style={styles.legendItem}>
            <View style={[styles.legendDot, { backgroundColor: '#0284c7' }]} />
            <Text style={styles.legendLabel}>Diastolic (mmHg)</Text>
          </View>
        </View>

        <Svg width={chartWidth} height={chartHeight}>
          {/* Background grid lines */}
          {[minY, (minY + maxY) / 2, maxY].map((val, idx) => {
            const yPos = getY(val);
            return (
              <React.Fragment key={idx}>
                <Line
                  x1={padding.left}
                  y1={yPos}
                  x2={chartWidth - padding.right}
                  y2={yPos}
                  stroke="#e2e8f0"
                  strokeWidth="1"
                  strokeDasharray="4 4"
                />
                <SvgText
                  x={padding.left - 6}
                  y={yPos + 4}
                  fill="#94a3b8"
                  fontSize="10"
                  textAnchor="end"
                  fontWeight="600"
                >
                  {Math.round(val)}
                </SvgText>
              </React.Fragment>
            );
          })}

          {/* Systolic Polyline */}
          <Polyline points={sysPoints} fill="none" stroke="#2563eb" strokeWidth="2.5" />
          {/* Diastolic Polyline */}
          <Polyline points={diaPoints} fill="none" stroke="#0284c7" strokeWidth="2.5" />

          {/* Data Points */}
          {chronological.map((v, i) => {
            const x = getX(i);
            const ySys = getY(sysVals[i]);
            const yDia = getY(diaVals[i]);
            const label = `V${i + 1}`;

            return (
              <React.Fragment key={i}>
                {/* Systolic Point */}
                <Circle cx={x} cy={ySys} r="4.5" fill="#2563eb" stroke="#ffffff" strokeWidth="2" />
                <SvgText x={x} y={ySys - 8} fill="#1e3a8a" fontSize="10" textAnchor="middle" fontWeight="700">
                  {sysVals[i]}
                </SvgText>

                {/* Diastolic Point */}
                <Circle cx={x} cy={yDia} r="4" fill="#0284c7" stroke="#ffffff" strokeWidth="2" />
                <SvgText x={x} y={yDia + 14} fill="#0369a1" fontSize="9" textAnchor="middle" fontWeight="700">
                  {diaVals[i]}
                </SvgText>

                {/* X-axis Label */}
                <SvgText
                  x={x}
                  y={chartHeight - 8}
                  fill="#64748b"
                  fontSize="11"
                  textAnchor="middle"
                  fontWeight="600"
                >
                  {label}
                </SvgText>
              </React.Fragment>
            );
          })}
        </Svg>
      </View>
    );
  }

  // Blood Sugar Metric
  const bsVals = chronological.map((v) => Number(v.blood_sugar) || 90);
  const minBs = Math.floor(Math.min(...bsVals, 60) / 10) * 10;
  const maxBs = Math.ceil(Math.max(...bsVals, 140) / 10) * 10;
  const rangeBs = maxBs - minBs || 1;

  const getX = (index) => padding.left + (index / (n - 1)) * innerWidth;
  const getY = (val) => padding.top + innerHeight - ((val - minBs) / rangeBs) * innerHeight;
  const bsPoints = chronological.map((_, i) => `${getX(i)},${getY(bsVals[i])}`).join(' ');

  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <Text style={styles.title}>Vitals Trend Over Time</Text>
        <View style={styles.toggleRow}>
          <Pressable style={styles.toggleBtn} onPress={() => setActiveMetric('bp')}>
            <Text style={styles.toggleText}>Blood Pressure</Text>
          </Pressable>
          <Pressable style={[styles.toggleBtn, styles.toggleActive]} onPress={() => setActiveMetric('bs')}>
            <Text style={[styles.toggleText, styles.toggleTextActive]}>Blood Sugar</Text>
          </Pressable>
        </View>
      </View>

      <View style={styles.legendRow}>
        <View style={styles.legendItem}>
          <View style={[styles.legendDot, { backgroundColor: '#ea580c' }]} />
          <Text style={styles.legendLabel}>Blood Sugar (mg/dL)</Text>
        </View>
      </View>

      <Svg width={chartWidth} height={chartHeight}>
        {[minBs, (minBs + maxBs) / 2, maxBs].map((val, idx) => {
          const yPos = getY(val);
          return (
            <React.Fragment key={idx}>
              <Line
                x1={padding.left}
                y1={yPos}
                x2={chartWidth - padding.right}
                y2={yPos}
                stroke="#e2e8f0"
                strokeWidth="1"
                strokeDasharray="4 4"
              />
              <SvgText
                x={padding.left - 6}
                y={yPos + 4}
                fill="#94a3b8"
                fontSize="10"
                textAnchor="end"
                fontWeight="600"
              >
                {Math.round(val)}
              </SvgText>
            </React.Fragment>
          );
        })}

        <Polyline points={bsPoints} fill="none" stroke="#ea580c" strokeWidth="2.5" />

        {chronological.map((v, i) => {
          const x = getX(i);
          const y = getY(bsVals[i]);
          const label = `V${i + 1}`;

          return (
            <React.Fragment key={i}>
              <Circle cx={x} cy={y} r="4.5" fill="#ea580c" stroke="#ffffff" strokeWidth="2" />
              <SvgText x={x} y={y - 8} fill="#9a3412" fontSize="10" textAnchor="middle" fontWeight="700">
                {bsVals[i]}
              </SvgText>
              <SvgText
                x={x}
                y={chartHeight - 8}
                fill="#64748b"
                fontSize="11"
                textAnchor="middle"
                fontWeight="600"
              >
                {label}
              </SvgText>
            </React.Fragment>
          );
        })}
      </Svg>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#ffffff',
    borderRadius: 16,
    padding: 16,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    alignItems: 'center',
  },
  header: {
    width: '100%',
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  title: { fontSize: 15, fontWeight: '700', color: '#0f172a' },
  toggleRow: { flexDirection: 'row', backgroundColor: '#f1f5f9', borderRadius: 8, padding: 2 },
  toggleBtn: { paddingVertical: 4, paddingHorizontal: 8, borderRadius: 6 },
  toggleActive: { backgroundColor: '#ffffff', shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 2, elevation: 1 },
  toggleText: { fontSize: 11, fontWeight: '600', color: '#64748b' },
  toggleTextActive: { color: '#0f172a', fontWeight: '700' },

  legendRow: { width: '100%', flexDirection: 'row', justifyContent: 'center', gap: 14, marginBottom: 8 },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  legendDot: { width: 8, height: 8, borderRadius: 4 },
  legendLabel: { fontSize: 11, fontWeight: '600', color: '#64748b' },

  emptyContainer: {
    backgroundColor: '#ffffff',
    borderRadius: 14,
    padding: 16,
    alignItems: 'center',
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  emptyTitle: { fontSize: 14, fontWeight: '700', color: '#475569', marginBottom: 4 },
  emptyText: { fontSize: 12, color: '#94a3b8', textAlign: 'center' },
});
