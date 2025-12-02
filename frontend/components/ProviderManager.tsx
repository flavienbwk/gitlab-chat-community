'use client';

import { useState } from 'react';
import { useProviders } from '@/hooks/useProviders';
import type { LLMProvider, LLMProviderCreate, ProviderType } from '@/lib/types';
import { HOST_COUNTRIES } from '@/lib/types';

interface ProviderFormData {
  name: string;
  provider_type: ProviderType;
  api_key: string;
  model_id: string;
  base_url: string;
  host_country: string;
  is_default: boolean;
}

const INITIAL_FORM_DATA: ProviderFormData = {
  name: '',
  provider_type: 'openai',
  api_key: '',
  model_id: '',
  base_url: '',
  host_country: '',
  is_default: false,
};

// Country flag emoji helper
function getCountryFlag(code: string): string {
  const codePoints = code
    .toUpperCase()
    .split('')
    .map((char) => 127397 + char.charCodeAt(0));
  return String.fromCodePoint(...codePoints);
}

export default function ProviderManager() {
  const {
    providers,
    isLoading,
    error,
    loadProviders,
    createProvider,
    updateProvider,
    deleteProvider,
    setDefaultProvider,
  } = useProviders();

  const [showForm, setShowForm] = useState(false);
  const [editingProvider, setEditingProvider] = useState<LLMProvider | null>(null);
  const [formData, setFormData] = useState<ProviderFormData>(INITIAL_FORM_DATA);
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    const { name, value, type } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? (e.target as HTMLInputElement).checked : value,
    }));
  };

  const handleEdit = (provider: LLMProvider) => {
    setEditingProvider(provider);
    setFormData({
      name: provider.name,
      provider_type: provider.provider_type,
      api_key: '', // Don't populate API key for security
      model_id: provider.model_id,
      base_url: provider.base_url || '',
      host_country: provider.host_country || '',
      is_default: provider.is_default,
    });
    setShowForm(true);
    setFormError(null);
  };

  const handleCancel = () => {
    setShowForm(false);
    setEditingProvider(null);
    setFormData(INITIAL_FORM_DATA);
    setFormError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setIsSubmitting(true);

    try {
      if (editingProvider) {
        // Update existing provider
        const updateData: Record<string, unknown> = {
          name: formData.name,
          provider_type: formData.provider_type,
          model_id: formData.model_id,
          base_url: formData.base_url || undefined,
          host_country: formData.host_country || undefined,
          is_default: formData.is_default,
        };

        // Only include API key if provided
        if (formData.api_key) {
          updateData.api_key = formData.api_key;
        }

        await updateProvider(editingProvider.id, updateData);
      } else {
        // Create new provider
        if (!formData.api_key) {
          setFormError('API key is required');
          setIsSubmitting(false);
          return;
        }

        const createData: LLMProviderCreate = {
          name: formData.name,
          provider_type: formData.provider_type,
          api_key: formData.api_key,
          model_id: formData.model_id,
          base_url: formData.base_url || undefined,
          host_country: formData.host_country || undefined,
          is_default: formData.is_default,
        };

        await createProvider(createData);
      }

      handleCancel();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to save provider');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (provider: LLMProvider) => {
    if (!confirm(`Are you sure you want to delete "${provider.name}"?`)) {
      return;
    }

    try {
      await deleteProvider(provider.id);
    } catch (err) {
      // Error is handled by the hook
    }
  };

  const handleSetDefault = async (provider: LLMProvider) => {
    try {
      await setDefaultProvider(provider.id);
    } catch (err) {
      // Error is handled by the hook
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">LLM Providers</h2>
          <p className="text-sm text-gray-600">
            Manage your AI model endpoints. The default provider is used for chat.
          </p>
        </div>
        <button
          onClick={() => {
            setShowForm(true);
            setEditingProvider(null);
            setFormData(INITIAL_FORM_DATA);
          }}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Add Provider
        </button>
      </div>

      {/* Error banner */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
          {error}
        </div>
      )}

      {/* Provider Form Modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <div className="fixed inset-0 bg-black/30" onClick={handleCancel} />
            <div className="relative bg-white rounded-xl shadow-xl max-w-lg w-full p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                {editingProvider ? 'Edit Provider' : 'Add New Provider'}
              </h3>

              {formError && (
                <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">
                  {formError}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Name */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Name
                  </label>
                  <input
                    type="text"
                    name="name"
                    value={formData.name}
                    onChange={handleInputChange}
                    placeholder="e.g., OpenAI GPT-4"
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>

                {/* Provider Type */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Provider Type
                  </label>
                  <select
                    name="provider_type"
                    value={formData.provider_type}
                    onChange={handleInputChange}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  >
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic</option>
                    <option value="custom">Custom (OpenAI-compatible)</option>
                  </select>
                </div>

                {/* API Key */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    API Key {editingProvider && <span className="text-gray-500">(leave blank to keep current)</span>}
                  </label>
                  <input
                    type="password"
                    name="api_key"
                    value={formData.api_key}
                    onChange={handleInputChange}
                    placeholder={editingProvider ? '••••••••' : 'sk-...'}
                    required={!editingProvider}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>

                {/* Model ID */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Model ID
                  </label>
                  <input
                    type="text"
                    name="model_id"
                    value={formData.model_id}
                    onChange={handleInputChange}
                    placeholder={
                      formData.provider_type === 'anthropic'
                        ? 'e.g., claude-sonnet-4-20250514'
                        : 'e.g., gpt-4o'
                    }
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>

                {/* Base URL (for custom providers) */}
                {(formData.provider_type === 'custom' || formData.provider_type === 'openai') && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Base URL <span className="text-gray-500">(optional)</span>
                    </label>
                    <input
                      type="url"
                      name="base_url"
                      value={formData.base_url}
                      onChange={handleInputChange}
                      placeholder="https://api.example.com/v1"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                    <p className="mt-1 text-xs text-gray-500">
                      For custom or self-hosted OpenAI-compatible endpoints
                    </p>
                  </div>
                )}

                {/* Host Country */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Host Country <span className="text-gray-500">(for data sovereignty)</span>
                  </label>
                  <select
                    name="host_country"
                    value={formData.host_country}
                    onChange={handleInputChange}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  >
                    <option value="">Not specified</option>
                    {HOST_COUNTRIES.map((country) => (
                      <option key={country.code} value={country.code}>
                        {getCountryFlag(country.code)} {country.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Default checkbox */}
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="is_default"
                    name="is_default"
                    checked={formData.is_default}
                    onChange={handleInputChange}
                    className="h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                  />
                  <label htmlFor="is_default" className="text-sm text-gray-700">
                    Set as default provider
                  </label>
                </div>

                {/* Actions */}
                <div className="flex justify-end gap-3 pt-4">
                  <button
                    type="button"
                    onClick={handleCancel}
                    className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  >
                    {isSubmitting ? 'Saving...' : editingProvider ? 'Update' : 'Create'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Provider List */}
      {providers.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
          <svg
            className="w-12 h-12 mx-auto text-gray-400 mb-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
            />
          </svg>
          <h3 className="text-lg font-medium text-gray-900 mb-2">No providers configured</h3>
          <p className="text-gray-600 mb-4">
            Add an LLM provider to start chatting with your GitLab data.
          </p>
          <button
            onClick={() => setShowForm(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Add Provider
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {providers.map((provider) => (
            <div
              key={provider.id}
              className={`bg-white rounded-lg border-2 p-4 ${
                provider.is_default
                  ? 'border-blue-500 ring-1 ring-blue-500'
                  : 'border-gray-200'
              }`}
            >
              {/* Header */}
              <div className="flex items-start justify-between gap-2 mb-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="font-medium text-gray-900 truncate">
                      {provider.name}
                    </h3>
                    {provider.is_default && (
                      <span className="px-2 py-0.5 bg-blue-100 text-blue-800 text-xs rounded-full">
                        Default
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-500">
                    {provider.provider_type === 'openai' && 'OpenAI'}
                    {provider.provider_type === 'anthropic' && 'Anthropic'}
                    {provider.provider_type === 'custom' && 'Custom'}
                    {' • '}
                    <span className="font-mono">{provider.model_id}</span>
                  </p>
                </div>
              </div>

              {/* Host Country Badge */}
              {provider.host_country && (
                <div className="flex items-center gap-1.5 text-sm text-gray-600 mb-3">
                  <span className="text-lg">{getCountryFlag(provider.host_country)}</span>
                  <span>
                    Hosted in{' '}
                    {HOST_COUNTRIES.find((c) => c.code === provider.host_country)?.name ||
                      provider.host_country}
                  </span>
                </div>
              )}

              {/* Base URL if set */}
              {provider.base_url && (
                <p className="text-xs text-gray-500 mb-3 truncate" title={provider.base_url}>
                  {provider.base_url}
                </p>
              )}

              {/* Actions */}
              <div className="flex items-center justify-end gap-2 pt-3 border-t border-gray-100">
                {!provider.is_default && (
                  <button
                    onClick={() => handleSetDefault(provider)}
                    className="text-xs font-medium text-blue-600 hover:text-blue-800"
                  >
                    Set Default
                  </button>
                )}
                <button
                  onClick={() => handleEdit(provider)}
                  className="text-xs font-medium text-gray-600 hover:text-gray-800"
                >
                  Edit
                </button>
                <button
                  onClick={() => handleDelete(provider)}
                  className="text-xs font-medium text-red-600 hover:text-red-800"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
