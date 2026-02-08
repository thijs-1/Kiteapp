import { useState, useEffect } from 'react';

const STORAGE_KEY = 'kiteapp_menu_seen';

interface MenuCalloutProps {
  onDismiss: () => void;
}

export function MenuCallout({ onDismiss }: MenuCalloutProps) {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // Check if user has already seen/used the menu
    const hasSeenMenu = localStorage.getItem(STORAGE_KEY);
    if (!hasSeenMenu) {
      // Small delay before showing for better UX
      const timer = setTimeout(() => setIsVisible(true), 500);
      return () => clearTimeout(timer);
    }
  }, []);

  if (!isVisible) return null;

  const handleDismiss = () => {
    setIsVisible(false);
    onDismiss();
  };

  return (
    <div
      className="fixed top-4 left-20 z-[1001] animate-fade-in hover:animate-none"
      style={{ animationFillMode: 'forwards' }}
      onClick={handleDismiss}
    >
      {/* Arrow pointing left */}
      <div className="absolute left-0 top-1/2 -translate-x-full -translate-y-1/2">
        <div className="w-0 h-0 border-t-8 border-b-8 border-r-8 border-t-transparent border-b-transparent border-r-kite" />
      </div>

      {/* Callout bubble */}
      <div className="bg-kite text-white px-4 py-2 rounded-lg shadow-lg cursor-pointer hover:bg-kite-dark transition-colors">
        <span className="font-semibold whitespace-nowrap">Start here</span>
      </div>
    </div>
  );
}

export function markMenuAsSeen() {
  localStorage.setItem(STORAGE_KEY, 'true');
}

export function hasSeenMenu(): boolean {
  return localStorage.getItem(STORAGE_KEY) === 'true';
}
