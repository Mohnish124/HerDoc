import React, { useEffect, useState } from 'react';
import { Alert, Button, Platform, StyleSheet, Text, View } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';

import { initializeDatabase } from './app/db';
import { getIsConnected, subscribeToConnectivityChanges } from './app/services/connectivity';
import {
  clearTokens,
  getSessionUser,
  getStoredTokens,
  loginWorkerOffline,
  loginWorkerOnline,
} from './app/services/auth';
import LoginScreen from './app/screens/LoginScreen';
import HomeScreen from './app/screens/HomeScreen';
import NewPatientScreen from './app/screens/NewPatientScreen';
import NewVisitScreen from './app/screens/NewVisitScreen';
import RiskResultScreen from './app/screens/RiskResultScreen';
import PatientHistoryScreen from './app/screens/PatientHistoryScreen';
import SettingsScreen from './app/screens/SettingsScreen';

const Stack = createStackNavigator();

function AppNavigator({ user, setUser, isConnected, isLoggingIn, setIsLoggingIn }) {
  const signOut = async () => {
    try {
      await clearTokens();
      setUser(null);
    } catch (error) {
      Alert.alert('Sign out failed', error?.message || 'Unable to sign out');
    }
  };

  const handleLogin = async (phone, pin) => {
    if (isLoggingIn) {
      return;
    }
    setIsLoggingIn(true);
    try {
      const result = isConnected
        ? await loginWorkerOnline(phone, pin)
        : await loginWorkerOffline(phone, pin);
      setUser(result.user);
    } finally {
      setIsLoggingIn(false);
    }
  };

  return (
    <NavigationContainer key={user ? 'authenticated' : 'guest'}>
      <Stack.Navigator initialRouteName={user ? 'Home' : 'Login'} screenOptions={{ headerBackTitleVisible: false }}>
        {!user ? (
          <Stack.Screen name="Login" options={{ headerShown: false }}>
            {(props) => (
              <LoginScreen
                {...props}
                isConnected={isConnected}
                isBusy={isLoggingIn}
                onLogin={handleLogin}
              />
            )}
          </Stack.Screen>
        ) : (
          <>
            <Stack.Screen
              name="Home"
              options={({ navigation }) => ({
                title: 'Home',
                headerRight: ({ tintColor }) => (
                  <Button title="Settings" onPress={() => navigation.navigate('Settings')} color={tintColor || '#2563eb'} />
                ),
              })}
            >
              {(props) => <HomeScreen {...props} user={user} />}
            </Stack.Screen>
            <Stack.Screen name="New Patient">
              {(props) => <NewPatientScreen {...props} user={user} />}
            </Stack.Screen>
            <Stack.Screen name="New Visit">
              {(props) => <NewVisitScreen {...props} user={user} />}
            </Stack.Screen>
            <Stack.Screen name="Risk Result" component={RiskResultScreen} />
            <Stack.Screen name="Patient History">
              {(props) => <PatientHistoryScreen {...props} user={user} />}
            </Stack.Screen>
            <Stack.Screen
              name="Settings"
              options={{ title: 'Settings', headerRight: () => (
                <Button title="Logout" onPress={signOut} color="#b91c1c" />
              )}}
            >
              {(props) => <SettingsScreen {...props} user={user} onLogout={signOut} />}
            </Stack.Screen>
          </>
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
}

export default function App() {
  const [user, setUser] = useState(null);
  const [isConnected, setIsConnected] = useState(true);
  const [isReady, setIsReady] = useState(false);
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  useEffect(() => {
    let mounted = true;

    const init = async () => {
      initializeDatabase();

      let connected = true;
      try {
        connected = await getIsConnected();
      } catch {
        connected = true;
      }
      if (!mounted) {
        return;
      }
      setIsConnected(connected);

      try {
        const { accessToken } = await getStoredTokens();
        if (accessToken) {
          const sessionUser = await getSessionUser();
          if (sessionUser && mounted) {
            setUser(sessionUser);
          }
        }
      } catch {
        // Ignore session restore errors; user will re-login manually.
      }
      if (mounted) {
        setIsReady(true);
      }
    };

    init();
    const unsubscribe = subscribeToConnectivityChanges((connected) => {
      if (mounted) {
        setIsConnected(Boolean(connected));
      }
    });

    return () => {
      mounted = false;
      unsubscribe?.();
    };
  }, []);

  if (!isReady) {
    return (
      <View style={styles.loadingContainer}>
        <Text style={styles.loadingTitle}>HerDoc</Text>
        <Text style={styles.loadingSubtitle}>Loading offline storage…</Text>
      </View>
    );
  }

  return (
    <AppNavigator
      user={user}
      setUser={setUser}
      isConnected={isConnected}
      isLoggingIn={isLoggingIn}
      setIsLoggingIn={setIsLoggingIn}
    />
  );
}

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#eef4ff',
    padding: 24,
  },
  loadingTitle: {
    fontSize: 32,
    fontWeight: '800',
    color: '#0f172a',
    letterSpacing: -0.2,
  },
  loadingSubtitle: {
    marginTop: 8,
    color: '#475569',
    fontSize: 14,
  },
});
