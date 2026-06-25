import React, { useState } from 'react';
import { useAuth } from './AuthContext';
import App from './App';
import LoginPage from './components/LoginPage';
import RegisterPage from './components/RegisterPage';

export default function AppShell() {
  const { user, checking, login } = useAuth();
  const [showRegister, setShowRegister] = useState(false);

  if (checking) {
    return <div style={{minHeight:'100dvh',display:'flex',alignItems:'center',justifyContent:'center',background:'#0f1724',color:'#8ba0b8',fontFamily:'Inter,system-ui,sans-serif',fontSize:14}}>加载中...</div>;
  }

  if (!user) {
    if (showRegister) return <RegisterPage onBack={() => setShowRegister(false)} />;
    return <LoginPage onLogin={login} onGoRegister={() => setShowRegister(true)} />;
  }

  // key forces remount when user changes (e.g. logout → login as different user)
  return <App key={user.id} />;
}
