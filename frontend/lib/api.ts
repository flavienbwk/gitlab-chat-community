/**
 * API client for the GitLab Chat backend
 */

import type {
  ChatRequest,
  ChatResponse,
  ClearConversationsResponse,
  Conversation,
  ConversationDetail,
  ConversationListResponse,
  DeleteConversationResponse,
  IndexingStatusResponse,
  IndexProjectResponse,
  Project,
  ProjectListResponse,
  RefreshProjectsResponse,
  SelectProjectResponse,
} from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Generic fetch wrapper with error handling
 */
async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}

/**
 * API client
 */
export const api = {
  // =====================
  // Chat endpoints
  // =====================

  /**
   * Send a chat message and receive a streaming response
   */
  async sendMessageStream(
    message: string,
    conversationId?: string,
    onToken: (token: string) => void = () => {},
    onTitle: (title: string) => void = () => {},
    onDone: (conversationId: string) => void = () => {},
    onError: (error: string) => void = () => {}
  ): Promise<void> {
    const url = `${API_BASE}/api/chat`;

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify({
        message,
        conversation_id: conversationId,
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `API error: ${response.status}`);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) {
      throw new Error('No response body');
    }

    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });

      // Process complete events (SSE events are separated by double newlines)
      // Handle both \r\n and \n line endings
      const events = buffer.split(/\r?\n\r?\n/);
      buffer = events.pop() || ''; // Keep incomplete event in buffer

      for (const event of events) {
        if (!event.trim()) continue;

        const lines = event.split(/\r?\n/);
        let eventType = 'message';
        let data = '';

        for (const line of lines) {
          if (line.startsWith('event:')) {
            eventType = line.slice(6).trim();
          } else if (line.startsWith('data:')) {
            // Preserve the space after "data: " if present
            data = line.slice(5);
            if (data.startsWith(' ')) {
              data = data.slice(1);
            }
          }
        }

        if (data === '[DONE]') continue;

        switch (eventType) {
          case 'message':
            onToken(data);
            break;
          case 'title':
            onTitle(data);
            break;
          case 'done':
            onDone(data);
            break;
          case 'error':
            onError(data);
            break;
        }
      }
    }
  },

  /**
   * Send a chat message and receive a non-streaming response
   */
  async sendMessage(
    message: string,
    conversationId?: string
  ): Promise<ChatResponse> {
    return fetchApi<ChatResponse>('/api/chat/sync', {
      method: 'POST',
      body: JSON.stringify({
        message,
        conversation_id: conversationId,
      }),
    });
  },

  // =====================
  // Conversation endpoints
  // =====================

  /**
   * Get all conversations
   */
  async getConversations(): Promise<ConversationListResponse> {
    return fetchApi<ConversationListResponse>('/api/conversations');
  },

  /**
   * Get a specific conversation with messages
   */
  async getConversation(id: string): Promise<ConversationDetail> {
    return fetchApi<ConversationDetail>(`/api/conversations/${id}`);
  },

  /**
   * Delete a conversation
   */
  async deleteConversation(id: string): Promise<DeleteConversationResponse> {
    return fetchApi<DeleteConversationResponse>(`/api/conversations/${id}`, {
      method: 'DELETE',
    });
  },

  /**
   * Clear all conversations
   */
  async clearConversations(): Promise<ClearConversationsResponse> {
    return fetchApi<ClearConversationsResponse>('/api/conversations', {
      method: 'DELETE',
    });
  },

  // =====================
  // Project endpoints
  // =====================

  /**
   * Get all projects
   */
  async getProjects(): Promise<ProjectListResponse> {
    return fetchApi<ProjectListResponse>('/api/projects');
  },

  /**
   * Refresh project list from GitLab
   */
  async refreshProjects(): Promise<RefreshProjectsResponse> {
    return fetchApi<RefreshProjectsResponse>('/api/projects/refresh', {
      method: 'POST',
    });
  },

  /**
   * Get a specific project
   */
  async getProject(id: number): Promise<Project> {
    return fetchApi<Project>(`/api/projects/${id}`);
  },

  /**
   * Select a project for querying
   */
  async selectProject(id: number): Promise<SelectProjectResponse> {
    return fetchApi<SelectProjectResponse>(`/api/projects/${id}/select`, {
      method: 'POST',
    });
  },

  /**
   * Deselect a project
   */
  async deselectProject(id: number): Promise<SelectProjectResponse> {
    return fetchApi<SelectProjectResponse>(`/api/projects/${id}/deselect`, {
      method: 'POST',
    });
  },

  /**
   * Trigger indexing for a project
   */
  async indexProject(id: number): Promise<IndexProjectResponse> {
    return fetchApi<IndexProjectResponse>(`/api/projects/${id}/index`, {
      method: 'POST',
    });
  },

  /**
   * Get indexing status for a project
   */
  async getIndexingStatus(id: number): Promise<IndexingStatusResponse> {
    return fetchApi<IndexingStatusResponse>(`/api/projects/${id}/status`);
  },

  /**
   * Get selected projects
   */
  async getSelectedProjects(): Promise<ProjectListResponse> {
    return fetchApi<ProjectListResponse>('/api/projects/selected/list');
  },

  /**
   * Stop indexing for a project
   */
  async stopIndexing(id: number): Promise<{ status: string; project_id: number; revoked_tasks?: number; message?: string }> {
    return fetchApi(`/api/projects/${id}/stop-indexing`, {
      method: 'POST',
    });
  },

  /**
   * Clear indexed data for a project
   */
  async clearIndex(id: number): Promise<{ status: string; project_id: number; message?: string }> {
    return fetchApi(`/api/projects/${id}/clear-index`, {
      method: 'POST',
    });
  },
};

export default api;
