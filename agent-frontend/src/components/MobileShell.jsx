import React from 'react';
import BottomNav from './BottomNav';

/**
 * MobileShell — mobile layout container
 * Wraps content with safe-area padding and bottom navigation bar.
 * Uses 100dvh for proper iOS Safari viewport handling.
 */
export default function MobileShell({ children }) {
  return (
    <div className="mobile-shell">
      <div className="mobile-safe-top" />
      <main className="mobile-content">
        {children}
      </main>
      <BottomNav />
      <div className="mobile-safe-bottom" />
    </div>
  );
}
