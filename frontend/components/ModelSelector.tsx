'use client';

import { useState, useRef, useEffect } from 'react';
import type { LLMProvider } from '@/lib/types';
import { HOST_COUNTRIES } from '@/lib/types';

interface ModelSelectorProps {
  providers: LLMProvider[];
  selectedProvider: LLMProvider | null;
  onSelect: (provider: LLMProvider | null) => void;
  isLoading?: boolean;
}

// Country flag emoji helper
function getCountryFlag(code: string): string {
  const codePoints = code
    .toUpperCase()
    .split('')
    .map((char) => 127397 + char.charCodeAt(0));
  return String.fromCodePoint(...codePoints);
}

export default function ModelSelector({
  providers,
  selectedProvider,
  onSelect,
  isLoading = false,
}: ModelSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  if (providers.length === 0) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
          />
        </svg>
        <span>No model configured</span>
      </div>
    );
  }

  const getProviderIcon = (type: string) => {
    switch (type) {
      case 'openai':
        return (
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
            <path d="M22.282 9.821a5.985 5.985 0 00-.516-4.91 6.046 6.046 0 00-6.51-2.9A6.065 6.065 0 0012 .002a6.133 6.133 0 00-5.855 4.287 6.004 6.004 0 00-4.13 2.91 6.054 6.054 0 00.754 7.103 5.985 5.985 0 00.516 4.91 6.046 6.046 0 006.51 2.9A6.065 6.065 0 0012 24a6.133 6.133 0 005.855-4.287 6.004 6.004 0 004.13-2.91 6.054 6.054 0 00-.754-7.103zM12 22.43a4.604 4.604 0 01-2.92-1.037c.037-.02.102-.057.144-.082l4.852-2.8a.786.786 0 00.397-.68v-6.845l2.05 1.184a.072.072 0 01.04.056v5.66a4.55 4.55 0 01-4.563 4.544zm-9.823-4.28a4.536 4.536 0 01-.542-3.062c.036.02.1.057.144.082l4.852 2.8a.787.787 0 00.793 0l5.927-3.423v2.368a.072.072 0 01-.029.062L8.41 19.79a4.55 4.55 0 01-6.233-1.64zM.98 7.935a4.517 4.517 0 012.4-1.988v5.76a.773.773 0 00.397.68l5.927 3.423-2.05 1.184a.072.072 0 01-.068.006l-4.912-2.838A4.55 4.55 0 01.98 7.935zm17.142 4.088l-5.927-3.423 2.05-1.184a.072.072 0 01.068-.006l4.912 2.838a4.55 4.55 0 01-.722 8.014v-5.56a.773.773 0 00-.38-.68zm2.04-3.071c-.036-.02-.1-.057-.144-.082l-4.852-2.8a.787.787 0 00-.793 0l-5.927 3.423V7.125a.072.072 0 01.029-.062l4.912-2.832a4.55 4.55 0 016.775 4.72zm-12.828 4.22l-2.05-1.184a.072.072 0 01-.04-.056V6.273a4.55 4.55 0 017.484-3.46 4.78 4.78 0 00-.144.082l-4.852 2.8a.786.786 0 00-.397.68v6.798zm1.11-2.39l2.64-1.525 2.64 1.525v3.05l-2.64 1.525-2.64-1.525v-3.05z" />
          </svg>
        );
      case 'anthropic':
        return (
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
            <path d="M17.304 3H13.5l5.25 18h3.75L17.304 3zM6.696 3H3l5.25 18h3.75L6.696 3z" />
          </svg>
        );
      default:
        return (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
            />
          </svg>
        );
    }
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={isLoading}
        className="flex items-center gap-1 sm:gap-2 px-2 sm:px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors disabled:opacity-50"
      >
        {selectedProvider ? (
          <>
            <span className="text-gray-600">{getProviderIcon(selectedProvider.provider_type)}</span>
            <span className="font-medium text-gray-700 max-w-[80px] sm:max-w-[150px] truncate hidden xs:inline">
              {selectedProvider.name}
            </span>
            {selectedProvider.host_country && (
              <span className="text-sm hidden sm:inline" title={`Hosted in ${HOST_COUNTRIES.find(c => c.code === selectedProvider.host_country)?.name || selectedProvider.host_country}`}>
                {getCountryFlag(selectedProvider.host_country)}
              </span>
            )}
          </>
        ) : (
          <span className="text-gray-500 text-xs sm:text-sm">Select</span>
        )}
        <svg
          className={`w-4 h-4 text-gray-500 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute top-full right-0 sm:left-0 sm:right-auto mt-1 w-64 sm:w-72 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-50 max-h-[70vh] overflow-y-auto">
          {providers.map((provider) => (
            <button
              key={provider.id}
              onClick={() => {
                onSelect(provider);
                setIsOpen(false);
              }}
              className={`w-full px-3 py-2 text-left hover:bg-gray-50 flex items-start gap-3 ${
                selectedProvider?.id === provider.id ? 'bg-blue-50' : ''
              }`}
            >
              <span className="text-gray-600 mt-0.5">{getProviderIcon(provider.provider_type)}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-gray-900 truncate">{provider.name}</span>
                  {provider.is_default && (
                    <span className="px-1.5 py-0.5 bg-blue-100 text-blue-700 text-xs rounded">
                      Default
                    </span>
                  )}
                  {provider.host_country && (
                    <span className="text-sm" title={`Hosted in ${HOST_COUNTRIES.find(c => c.code === provider.host_country)?.name || provider.host_country}`}>
                      {getCountryFlag(provider.host_country)}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2 text-xs text-gray-500">
                  <span className="font-mono">{provider.model_id}</span>
                </div>
                {provider.host_country && (
                  <div className="text-xs text-gray-400 mt-0.5">
                    Data processed in {HOST_COUNTRIES.find(c => c.code === provider.host_country)?.name || provider.host_country}
                  </div>
                )}
              </div>
              {selectedProvider?.id === provider.id && (
                <svg className="w-5 h-5 text-blue-600 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path
                    fillRule="evenodd"
                    d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                    clipRule="evenodd"
                  />
                </svg>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
