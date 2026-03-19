import { useState, useEffect, useRef } from 'react';

export function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(() => {
    if (typeof window === 'undefined') return false;
    const hasTouchCapability = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
    return hasTouchCapability && window.innerWidth < 768;
  });

  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const checkMobile = () => {
      // Debounce to avoid excessive re-renders during resize drag
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => {
        const hasTouchCapability = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
        const isSmallScreen = window.innerWidth < 768;
        setIsMobile(hasTouchCapability && isSmallScreen);
      }, 100);
    };

    checkMobile();
    window.addEventListener('resize', checkMobile);

    // Handle orientation changes explicitly (some browsers fire this separately)
    const mql = window.matchMedia('(orientation: portrait)');
    const handleOrientationChange = () => checkMobile();
    mql.addEventListener('change', handleOrientationChange);

    return () => {
      window.removeEventListener('resize', checkMobile);
      mql.removeEventListener('change', handleOrientationChange);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  return isMobile;
}
