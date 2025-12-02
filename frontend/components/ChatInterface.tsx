'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useChat } from '@/hooks/useChat';
import { useProjects } from '@/hooks/useProjects';
import { useProviders } from '@/hooks/useProviders';
import ConversationHistory from './ConversationHistory';
import MessageInput from './MessageInput';
import MessageList from './MessageList';
import ModelSelector from './ModelSelector';

export default function ChatInterface() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const {
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
  } = useChat();

  const { selectedProjects } = useProjects();
  const { providers, selectedProvider, selectProvider, isLoading: providersLoading } = useProviders();

  // Wrap sendMessage to include the selected provider
  const handleSendMessage = async (content: string) => {
    await sendMessage(content, selectedProvider?.id);
  };

  // Close sidebar when selecting a conversation on mobile
  const handleSelectConversation = (id: string) => {
    selectConversation(id);
    setSidebarOpen(false);
  };

  // Close sidebar when creating new conversation on mobile
  const handleNewConversation = () => {
    createNewConversation();
    setSidebarOpen(false);
  };

  return (
    <div className="flex h-full bg-gray-50">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div
        className={`fixed inset-y-0 left-0 z-50 w-72 bg-white border-r border-gray-200 flex flex-col transform transition-transform duration-300 ease-in-out lg:relative lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Logo & New Chat */}
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-orange-400 to-purple-600 flex items-center justify-center">
                <svg
                  className="w-5 h-5 text-white"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M22.65 14.39L12 22.13 1.35 14.39a.84.84 0 01-.3-.94l1.22-3.78 2.44-7.51A.42.42 0 014.82 2a.43.43 0 01.58 0 .42.42 0 01.11.18l2.44 7.49h8.1l2.44-7.51A.42.42 0 0118.6 2a.43.43 0 01.58 0 .42.42 0 01.11.18l2.44 7.51L23 13.45a.84.84 0 01-.35.94z" />
                </svg>
              </div>
              <span className="font-semibold text-gray-900">GitLab Chat</span>
            </div>
            {/* Close button for mobile */}
            <button
              onClick={() => setSidebarOpen(false)}
              className="lg:hidden p-1 text-gray-500 hover:text-gray-700"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <button
            onClick={handleNewConversation}
            className="w-full px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center justify-center gap-2"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 4v16m8-8H4"
              />
            </svg>
            New Chat
          </button>
        </div>

        {/* Conversation History */}
        <ConversationHistory
          conversations={conversations}
          currentId={currentConversation?.id}
          onSelect={handleSelectConversation}
          onDelete={deleteConversation}
        />

        {/* Footer Actions */}
        <div className="p-4 border-t border-gray-200 space-y-2">
          <Link
            href="/projects"
            className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded-lg transition-colors"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
              />
            </svg>
            Manage Projects
            {selectedProjects.length > 0 && (
              <span className="ml-auto bg-blue-100 text-blue-800 text-xs px-2 py-0.5 rounded-full">
                {selectedProjects.length}
              </span>
            )}
          </Link>

          <Link
            href="/settings"
            className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded-lg transition-colors"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
            Settings
            {providers.length > 0 && (
              <span className="ml-auto bg-green-100 text-green-800 text-xs px-2 py-0.5 rounded-full">
                {providers.length}
              </span>
            )}
          </Link>

          <button
            onClick={clearHistory}
            className="flex items-center gap-2 w-full px-3 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors"
          >
            <svg
              className="w-5 h-5"
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
            Clear History
          </button>

          <div className="pt-3 mt-3 border-t border-gray-100 text-center">
            <span className="text-xs text-gray-400">
              Built by{' '}
              <a
                href="https://berwick.io"
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-500 hover:text-blue-600 transition-colors"
              >
                Flavien Berwick
              </a>
            </span>
          </div>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="bg-white border-b border-gray-200 px-4 sm:px-6 py-4">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3 min-w-0">
              {/* Mobile menu button */}
              <button
                onClick={() => setSidebarOpen(true)}
                className="lg:hidden p-2 -ml-2 text-gray-500 hover:text-gray-700"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>

              <div className="min-w-0">
                <h1 className="text-lg font-semibold text-gray-900 truncate">
                  {currentConversation?.title || 'New Conversation'}
                </h1>
                {selectedProjects.length > 0 && (
                  <p className="text-sm text-gray-500 hidden sm:block">
                    Searching in {selectedProjects.length} project
                    {selectedProjects.length !== 1 ? 's' : ''}
                  </p>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2 sm:gap-4 flex-shrink-0">
              {/* Model Selector */}
              <ModelSelector
                providers={providers}
                selectedProvider={selectedProvider}
                onSelect={selectProvider}
                isLoading={providersLoading}
              />

              {selectedProjects.length === 0 && (
                <Link
                  href="/projects"
                  className="hidden sm:block text-sm text-blue-600 hover:text-blue-800 whitespace-nowrap"
                >
                  Select projects
                </Link>
              )}
            </div>
          </div>
        </header>

        {/* Error Banner */}
        {error && (
          <div className="bg-red-50 border-b border-red-200 px-4 sm:px-6 py-3 text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* Messages */}
        <MessageList messages={messages} isLoading={isLoading} />

        {/* Input */}
        <MessageInput
          onSend={handleSendMessage}
          isLoading={isLoading}
          placeholder={
            providers.length === 0
              ? 'Configure a model in Settings first...'
              : selectedProjects.length === 0
              ? 'Select projects first to enable chat...'
              : 'Ask about issues, merge requests, or code...'
          }
        />
      </div>
    </div>
  );
}
