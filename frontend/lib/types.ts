/**
 * Type definitions for the GitLab Chat frontend
 */

// Project types
export interface Project {
  id: number;
  gitlab_id: number;
  name: string;
  path_with_namespace: string;
  description: string | null;
  default_branch: string;
  is_indexed: boolean;
  is_selected: boolean;
  indexing_status: 'pending' | 'indexing' | 'completed' | 'error' | 'stopped';
  indexing_error: string | null;
}

export interface ProjectListResponse {
  projects: Project[];
  total: number;
}

export interface IndexingStatusResponse {
  status: string;
  error: string | null;
  is_indexed: boolean;
}

// Conversation types
export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ConversationDetail extends Omit<Conversation, 'message_count'> {
  messages: Message[];
}

export interface ConversationListResponse {
  conversations: Conversation[];
  total: number;
}

// Chat types
export interface ChatRequest {
  message: string;
  conversation_id?: string;
}

export interface ChatResponse {
  conversation_id: string;
  message: string;
  title?: string;
}

// SSE event types
export interface SSEEvent {
  event: 'message' | 'title' | 'done' | 'error';
  data: string;
}

// API response types
export interface RefreshProjectsResponse {
  status: string;
  total: number;
  created: number;
  updated: number;
}

export interface SelectProjectResponse {
  status: string;
  project_id: number;
}

export interface IndexProjectResponse {
  status: string;
  project_id: number;
  task_id?: string;
  message?: string;
}

export interface DeleteConversationResponse {
  status: string;
  conversation_id: string;
}

export interface ClearConversationsResponse {
  status: string;
  message: string;
}

export interface VectorCountsResponse {
  counts: Record<number, number>;
  total: number;
}
