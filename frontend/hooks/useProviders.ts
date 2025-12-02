'use client';

import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import type { LLMProvider, LLMProviderCreate, LLMProviderUpdate } from '@/lib/types';

interface UseProvidersReturn {
  providers: LLMProvider[];
  defaultProvider: LLMProvider | null;
  selectedProvider: LLMProvider | null;
  isLoading: boolean;
  error: string | null;
  loadProviders: () => Promise<void>;
  createProvider: (data: LLMProviderCreate) => Promise<LLMProvider>;
  updateProvider: (id: number, data: LLMProviderUpdate) => Promise<LLMProvider>;
  deleteProvider: (id: number) => Promise<void>;
  setDefaultProvider: (id: number) => Promise<void>;
  selectProvider: (provider: LLMProvider | null) => void;
}

export function useProviders(): UseProvidersReturn {
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [defaultProvider, setDefaultProvider] = useState<LLMProvider | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<LLMProvider | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadProviders = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const [providersResponse, defaultProviderResponse] = await Promise.all([
        api.getProviders(),
        api.getDefaultProvider(),
      ]);

      setProviders(providersResponse.providers);
      setDefaultProvider(defaultProviderResponse);

      // If no provider is selected, use the default
      if (!selectedProvider && defaultProviderResponse) {
        setSelectedProvider(defaultProviderResponse);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load providers');
    } finally {
      setIsLoading(false);
    }
  }, [selectedProvider]);

  // Load providers on mount
  useEffect(() => {
    loadProviders();
  }, []);

  const createProvider = useCallback(async (data: LLMProviderCreate): Promise<LLMProvider> => {
    try {
      setError(null);
      const provider = await api.createProvider(data);

      // Refresh list
      await loadProviders();

      return provider;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create provider';
      setError(message);
      throw err;
    }
  }, [loadProviders]);

  const updateProvider = useCallback(async (id: number, data: LLMProviderUpdate): Promise<LLMProvider> => {
    try {
      setError(null);
      const provider = await api.updateProvider(id, data);

      // Update local state
      setProviders((prev) =>
        prev.map((p) => (p.id === id ? provider : p))
      );

      // Update default if this is now default
      if (provider.is_default) {
        setDefaultProvider(provider);
      }

      // Update selected if this was selected
      if (selectedProvider?.id === id) {
        setSelectedProvider(provider);
      }

      return provider;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update provider';
      setError(message);
      throw err;
    }
  }, [selectedProvider]);

  const deleteProvider = useCallback(async (id: number): Promise<void> => {
    try {
      setError(null);
      await api.deleteProvider(id);

      // Remove from local state
      setProviders((prev) => prev.filter((p) => p.id !== id));

      // Clear default if this was default
      if (defaultProvider?.id === id) {
        setDefaultProvider(null);
      }

      // Clear selected if this was selected
      if (selectedProvider?.id === id) {
        setSelectedProvider(null);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete provider';
      setError(message);
      throw err;
    }
  }, [defaultProvider, selectedProvider]);

  const setDefaultProviderHandler = useCallback(async (id: number): Promise<void> => {
    try {
      setError(null);
      const provider = await api.setDefaultProvider(id);

      // Update all providers to reflect new default
      setProviders((prev) =>
        prev.map((p) => ({
          ...p,
          is_default: p.id === id,
        }))
      );

      setDefaultProvider(provider);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to set default provider';
      setError(message);
      throw err;
    }
  }, []);

  const selectProvider = useCallback((provider: LLMProvider | null) => {
    setSelectedProvider(provider);
  }, []);

  return {
    providers,
    defaultProvider,
    selectedProvider,
    isLoading,
    error,
    loadProviders,
    createProvider,
    updateProvider,
    deleteProvider,
    setDefaultProvider: setDefaultProviderHandler,
    selectProvider,
  };
}

export default useProviders;
