import Link from 'next/link';
import ProviderManager from '@/components/ProviderManager';

export default function SettingsPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-4">
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="flex items-center gap-2 text-gray-600 hover:text-gray-900"
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
                  d="M10 19l-7-7m0 0l7-7m-7 7h18"
                />
              </svg>
              <span className="hidden sm:inline">Back to Chat</span>
            </Link>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
        <div className="mb-6 sm:mb-8">
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Settings</h1>
          <p className="text-sm sm:text-base text-gray-600 mt-1">
            Configure your LLM providers and application settings.
          </p>
        </div>

        {/* Provider Manager */}
        <div className="bg-white rounded-xl border border-gray-200 p-4 sm:p-6">
          <ProviderManager />
        </div>

        {/* Info Section */}
        <div className="mt-6 sm:mt-8 bg-blue-50 rounded-xl border border-blue-200 p-4 sm:p-6">
          <h3 className="text-sm font-medium text-blue-800 mb-2">About LLM Providers</h3>
          <div className="text-xs sm:text-sm text-blue-700 space-y-2">
            <p>
              <strong>OpenAI:</strong> Use models like GPT-4o, GPT-4-turbo, or GPT-3.5-turbo.
              Requires an OpenAI API key.
            </p>
            <p>
              <strong>Anthropic:</strong> Use Claude models like claude-sonnet-4-20250514 or claude-3-opus.
              Requires an Anthropic API key.
            </p>
            <p>
              <strong>Custom:</strong> Use any OpenAI-compatible API endpoint (e.g., Azure OpenAI,
              local LLMs via vLLM/Ollama, or other providers).
            </p>
            <p className="mt-3">
              <strong>Host Country:</strong> Specify where your data is processed for compliance
              with data sovereignty requirements (GDPR, etc.).
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
