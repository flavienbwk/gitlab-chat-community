'use client';

import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import type { Conversation, Message } from '@/lib/types';

interface UseChatReturn {
  messages: Message[];
  conversations: Conversation[];
  currentConversation: Conversation | null;
  isLoading: boolean;
  error: string | null;
  sendMessage: (content: string) => Promise<void>;
  selectConversation: (id: string) => Promise<void>;
  createNewConversation: () => void;
  deleteConversation: (id: string) => Promise<void>;
  clearHistory: () => Promise<void>;
  refreshConversations: () => Promise<void>;
}

export function useChat(): UseChatReturn {
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversation, setCurrentConversation] = useState<Conversation | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load conversations on mount
  useEffect(() => {
    refreshConversations();
  }, []);

  const refreshConversations = useCallback(async () => {
    try {
      const response = await api.getConversations();
      setConversations(response.conversations);
    } catch (err) {
      console.error('Failed to load conversations:', err);
    }
  }, []);

  const selectConversation = useCallback(async (id: string) => {
    try {
      setIsLoading(true);
      setError(null);

      const detail = await api.getConversation(id);
      setCurrentConversation({
        id: detail.id,
        title: detail.title,
        created_at: detail.created_at,
        updated_at: detail.updated_at,
        message_count: detail.messages.length,
      });
      setMessages(detail.messages);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load conversation');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const createNewConversation = useCallback(() => {
    setCurrentConversation(null);
    setMessages([]);
    setError(null);
  }, []);

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isLoading) return;

    setIsLoading(true);
    setError(null);

    // Add user message immediately
    const userMessage: Message = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);

    // Add placeholder for assistant response
    const assistantMessage: Message = {
      id: `temp-assistant-${Date.now()}`,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, assistantMessage]);

    // Track title for new conversations (title event comes before done event)
    let pendingTitle: string | null = null;

    try {
      // Use streaming API
      await api.sendMessageStream(
        content,
        currentConversation?.id,
        // onToken
        (token) => {
          setMessages((prev) => {
            const lastMessage = prev[prev.length - 1];
            if (lastMessage?.role === 'assistant') {
              // Create new array with updated last message (immutable update)
              return [
                ...prev.slice(0, -1),
                { ...lastMessage, content: lastMessage.content + token }
              ];
            }
            return prev;
          });
        },
        // onTitle
        (title) => {
          pendingTitle = title;
          // Update current conversation title immediately if we have one
          setCurrentConversation((prev) =>
            prev ? { ...prev, title } : prev
          );
        },
        // onDone
        (conversationId) => {
          if (!currentConversation) {
            // Set the new conversation as current with the title
            setCurrentConversation({
              id: conversationId,
              title: pendingTitle,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
              message_count: 2,
            });
          }
          // Refresh sidebar to show the new/updated conversation
          refreshConversations();
        },
        // onError
        (errorMsg) => {
          setError(errorMsg);
        }
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message');
      // Remove the placeholder assistant message on error
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setIsLoading(false);
    }
  }, [currentConversation, isLoading, refreshConversations]);

  const deleteConversation = useCallback(async (id: string) => {
    try {
      await api.deleteConversation(id);

      // If deleting current conversation, clear it
      if (currentConversation?.id === id) {
        createNewConversation();
      }

      await refreshConversations();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete conversation');
    }
  }, [currentConversation, createNewConversation, refreshConversations]);

  const clearHistory = useCallback(async () => {
    try {
      await api.clearConversations();
      setConversations([]);
      createNewConversation();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to clear history');
    }
  }, [createNewConversation]);

  return {
    messages,
    conversations,
    currentConversation,
    isLoading,
    error,
    sendMessage,
    selectConversation,
    createNewConversation,
    deleteConversation,
    clearHistory,
    refreshConversations,
  };
}

export default useChat;
