import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { useIsMobile } from '../../hooks/useIsMobile';
import aboutContent from '../../about.md?raw';

export function AboutModal() {
  const [isOpen, setIsOpen] = useState(false);
  const isMobile = useIsMobile();

  // Lock body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = '';
      };
    }
  }, [isOpen]);

  return (
    <>
      {/* Floating info button */}
      <button
        onClick={() => setIsOpen(true)}
        className="fixed top-4 right-4 z-[1000] p-0 bg-transparent transition-all"
        aria-label="About"
      >
        <svg
          className="w-12 h-12 text-white/70 hover:text-white drop-shadow-lg transition-colors"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      </button>

      {/* Modal overlay */}
      {isOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[1002] p-0 sm:p-4">
          <div
            className={`bg-white flex flex-col shadow-2xl ${
              isMobile
                ? 'w-full h-full rounded-none'
                : 'rounded-xl w-full max-w-2xl max-h-[80vh]'
            }`}
          >
            {/* Header */}
            <div className="flex justify-between items-center p-3 sm:p-4 border-b">
              <h2 className="text-lg sm:text-xl font-bold text-gray-800">
                About
              </h2>
              <button
                onClick={() => setIsOpen(false)}
                className="p-3 hover:bg-gray-100 active:bg-gray-200 rounded-lg transition-colors flex-shrink-0"
                aria-label="Close"
              >
                <svg
                  className="w-6 h-6 text-gray-500"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 p-4 sm:p-6 overflow-y-auto">
              <div className="prose prose-sm sm:prose max-w-none prose-headings:text-gray-800 prose-p:text-gray-600 prose-a:text-kite prose-a:no-underline hover:prose-a:underline prose-strong:text-gray-700 prose-li:text-gray-600">
                <ReactMarkdown>{aboutContent}</ReactMarkdown>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
