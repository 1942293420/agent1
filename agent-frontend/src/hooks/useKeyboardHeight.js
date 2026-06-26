import { useState, useEffect } from 'react';

/**
 * useKeyboardHeight — detects iOS/Android keyboard height
 * Uses visualViewport API to calculate the on-screen keyboard overlap.
 * Returns keyboard height in pixels (0 when keyboard is hidden).
 */
export default function useKeyboardHeight() {
  const [keyboardHeight, setKeyboardHeight] = useState(0);

  useEffect(() => {
    if (typeof window === 'undefined' || !window.visualViewport) return;

    const handler = () => {
      const height = window.innerHeight - window.visualViewport.height;
      setKeyboardHeight(height > 0 ? height : 0);
    };

    window.visualViewport.addEventListener('resize', handler);
    window.visualViewport.addEventListener('scroll', handler);
    handler(); // initial check
    return () => {
      window.visualViewport.removeEventListener('resize', handler);
      window.visualViewport.removeEventListener('scroll', handler);
    };
  }, []);

  return keyboardHeight;
}
