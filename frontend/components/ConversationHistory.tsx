'use client';

import type { Conversation } from '@/lib/types';

interface ConversationHistoryProps {
  conversations: Conversation[];
  currentId?: string;
  onSelect: (id: string) => void;
  onDelete?: (id: string) => void;
}

export default function ConversationHistory({
  conversations,
  currentId,
  onSelect,
  onDelete,
}: ConversationHistoryProps) {
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) {
      return 'Today';
    } else if (days === 1) {
      return 'Yesterday';
    } else if (days < 7) {
      return `${days} days ago`;
    } else {
      return date.toLocaleDateString();
    }
  };

  if (conversations.length === 0) {
    return (
      <div className="flex-1 p-4 text-center text-gray-500 text-sm">
        No conversations yet
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      {conversations.map((conversation) => (
        <div
          key={conversation.id}
          className={`group relative px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors ${
            currentId === conversation.id ? 'bg-blue-50 border-r-2 border-blue-600' : ''
          }`}
          onClick={() => onSelect(conversation.id)}
        >
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <h3
                className={`text-sm font-medium truncate ${
                  currentId === conversation.id ? 'text-blue-900' : 'text-gray-900'
                }`}
              >
                {conversation.title || 'New Conversation'}
              </h3>
              <p className="text-xs text-gray-500 mt-0.5">
                {formatDate(conversation.updated_at)} &middot;{' '}
                {conversation.message_count} messages
              </p>
            </div>

            {onDelete && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(conversation.id);
                }}
                className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-500 transition-all"
                title="Delete conversation"
              >
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                  />
                </svg>
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
