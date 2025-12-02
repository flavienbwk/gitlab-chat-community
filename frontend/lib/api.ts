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
  LLMProvider,
  LLMProviderCreate,
  LLMProviderUpdate,
  Project,
  ProjectListResponse,
  ProviderListResponse,
  RefreshProjectsResponse,
  SelectProjectResponse,
  VectorCountsResponse,
} from './types';

// In production (nginx), API is on same origin. In development, use configured URL.
const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

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
    onError: (error: string) => void = () => {},
    providerId?: number
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
        provider_id: providerId,
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

    // Helper to process a single SSE event
    const processEvent = (event: string) => {
      if (!event.trim()) return;

      const lines = event.split(/\r?\n/);
      let eventType = 'message';
      const dataLines: string[] = [];

      for (const line of lines) {
        if (line.startsWith('event:')) {
          eventType = line.slice(6).trim();
        } else if (line.startsWith('data:')) {
          // Preserve the space after "data: " if present
          let lineData = line.slice(5);
          if (lineData.startsWith(' ')) {
            lineData = lineData.slice(1);
          }
          dataLines.push(lineData);
        }
      }

      // Join multiple data lines with newlines (per SSE spec)
      const data = dataLines.join('\n');

      if (data === '[DONE]') return;

      switch (eventType) {
        case 'message':
          // Empty data represents a newline from the LLM
          onToken(data === '' ? '\n' : data);
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
    };

    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        // Process any remaining data in buffer when stream ends
        if (buffer.trim()) {
          processEvent(buffer);
        }
        break;
      }

      buffer += decoder.decode(value, { stream: true });

      // Process complete events (SSE events are separated by double newlines)
      // Handle both \r\n and \n line endings
      const events = buffer.split(/\r?\n\r?\n/);
      buffer = events.pop() || ''; // Keep incomplete event in buffer

      for (const event of events) {
        processEvent(event);
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
   * Trigger full indexing for a project
   */
  async indexProject(id: number): Promise<IndexProjectResponse> {
    return fetchApi<IndexProjectResponse>(`/api/projects/${id}/index`, {
      method: 'POST',
    });
  },

  /**
   * Trigger incremental sync for a project (faster than full index)
   */
  async syncProject(id: number): Promise<IndexProjectResponse> {
    return fetchApi<IndexProjectResponse>(`/api/projects/${id}/sync`, {
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

  /**
   * Get vector counts per project from Qdrant
   */
  async getVectorCounts(): Promise<VectorCountsResponse> {
    return fetchApi<VectorCountsResponse>('/api/projects/vector-counts');
  },

  // =====================
  // LLM Provider endpoints
  // =====================

  /**
   * Get all LLM providers
   */
  async getProviders(): Promise<ProviderListResponse> {
    return fetchApi<ProviderListResponse>('/api/providers');
  },

  /**
   * Get the default LLM provider
   */
  async getDefaultProvider(): Promise<LLMProvider | null> {
    return fetchApi<LLMProvider | null>('/api/providers/default');
  },

  /**
   * Get a specific provider
   */
  async getProvider(id: number): Promise<LLMProvider> {
    return fetchApi<LLMProvider>(`/api/providers/${id}`);
  },

  /**
   * Create a new LLM provider
   */
  async createProvider(data: LLMProviderCreate): Promise<LLMProvider> {
    return fetchApi<LLMProvider>('/api/providers', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  /**
   * Update an LLM provider
   */
  async updateProvider(id: number, data: LLMProviderUpdate): Promise<LLMProvider> {
    return fetchApi<LLMProvider>(`/api/providers/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  /**
   * Delete an LLM provider
   */
  async deleteProvider(id: number): Promise<{ status: string; provider_id: number }> {
    return fetchApi(`/api/providers/${id}`, {
      method: 'DELETE',
    });
  },

  /**
   * Set a provider as default
   */
  async setDefaultProvider(id: number): Promise<LLMProvider> {
    return fetchApi<LLMProvider>(`/api/providers/${id}/set-default`, {
      method: 'POST',
    });
  },
};

export default api;
