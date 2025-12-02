'use client';

import type { Project } from '@/lib/types';

interface IndexingStatusProps {
  status: Project['indexing_status'];
  error?: string | null;
  isIndexed?: boolean;
  size?: 'sm' | 'md';
}

export default function IndexingStatus({
  status,
  error,
  isIndexed,
  size = 'md',
}: IndexingStatusProps) {
  const sizeClasses = size === 'sm' ? 'text-xs px-2 py-0.5' : 'text-sm px-2.5 py-1';

  const getStatusConfig = () => {
    switch (status) {
      case 'indexing':
        return {
          label: 'Indexing...',
          bgColor: 'bg-yellow-100',
          textColor: 'text-yellow-800',
          icon: (
            <svg
              className="w-3.5 h-3.5 animate-spin"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
          ),
        };
      case 'syncing':
        return {
          label: 'Syncing...',
          bgColor: 'bg-blue-100',
          textColor: 'text-blue-800',
          icon: (
            <svg
              className="w-3.5 h-3.5 animate-spin"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
          ),
        };
      case 'completed':
        return {
          label: 'Indexed',
          bgColor: 'bg-green-100',
          textColor: 'text-green-800',
          icon: (
            <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                clipRule="evenodd"
              />
            </svg>
          ),
        };
      case 'error':
        return {
          label: 'Error',
          bgColor: 'bg-red-100',
          textColor: 'text-red-800',
          icon: (
            <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                clipRule="evenodd"
              />
            </svg>
          ),
        };
      case 'stopped':
        return {
          label: 'Stopped',
          bgColor: 'bg-orange-100',
          textColor: 'text-orange-800',
          icon: (
            <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 7a1 1 0 00-1 1v4a1 1 0 001 1h4a1 1 0 001-1V8a1 1 0 00-1-1H8z"
                clipRule="evenodd"
              />
            </svg>
          ),
        };
      case 'pending':
      default:
        return {
          label: 'Not indexed',
          bgColor: 'bg-gray-100',
          textColor: 'text-gray-600',
          icon: (
            <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z"
                clipRule="evenodd"
              />
            </svg>
          ),
        };
    }
  };

  const config = getStatusConfig();

  return (
    <div className="inline-flex flex-col items-start gap-1">
      <span
        className={`inline-flex items-center gap-1.5 rounded-full font-medium ${sizeClasses} ${config.bgColor} ${config.textColor}`}
        title={error || undefined}
      >
        {config.icon}
        {config.label}
      </span>
      {error && status === 'error' && (
        <span className="text-xs text-red-600 max-w-xs truncate" title={error}>
          {error}
        </span>
      )}
    </div>
  );
}
