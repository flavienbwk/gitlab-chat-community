'use client';

import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import type { Project } from '@/lib/types';

interface UseProjectsReturn {
  projects: Project[];
  selectedProjects: Project[];
  isLoading: boolean;
  isRefreshing: boolean;
  error: string | null;
  refreshProjects: () => Promise<void>;
  selectProject: (id: number) => Promise<void>;
  deselectProject: (id: number) => Promise<void>;
  toggleProjectSelection: (id: number) => Promise<void>;
  indexProject: (id: number) => Promise<void>;
  stopIndexing: (id: number) => Promise<void>;
  clearIndex: (id: number) => Promise<void>;
  getProjectStatus: (id: number) => Promise<void>;
}

export function useProjects(): UseProjectsReturn {
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Computed selected projects
  const selectedProjects = projects.filter((p) => p.is_selected);

  // Load projects on mount
  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await api.getProjects();
      setProjects(response.projects);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load projects');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const refreshProjects = useCallback(async () => {
    try {
      setIsRefreshing(true);
      setError(null);

      // Refresh from GitLab
      await api.refreshProjects();

      // Reload the list
      const response = await api.getProjects();
      setProjects(response.projects);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to refresh projects');
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  const selectProject = useCallback(async (id: number) => {
    try {
      setError(null);
      await api.selectProject(id);

      // Update local state
      setProjects((prev) =>
        prev.map((p) => (p.id === id ? { ...p, is_selected: true } : p))
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to select project');
    }
  }, []);

  const deselectProject = useCallback(async (id: number) => {
    try {
      setError(null);
      await api.deselectProject(id);

      // Update local state
      setProjects((prev) =>
        prev.map((p) => (p.id === id ? { ...p, is_selected: false } : p))
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to deselect project');
    }
  }, []);

  const toggleProjectSelection = useCallback(
    async (id: number) => {
      const project = projects.find((p) => p.id === id);
      if (!project) return;

      if (project.is_selected) {
        await deselectProject(id);
      } else {
        await selectProject(id);
      }
    },
    [projects, selectProject, deselectProject]
  );

  const indexProject = useCallback(async (id: number) => {
    try {
      setError(null);

      // Update local state to show indexing
      setProjects((prev) =>
        prev.map((p) =>
          p.id === id ? { ...p, indexing_status: 'indexing' as const } : p
        )
      );

      await api.indexProject(id);

      // Poll for status updates
      const pollStatus = async () => {
        try {
          const status = await api.getIndexingStatus(id);

          setProjects((prev) =>
            prev.map((p) =>
              p.id === id
                ? {
                    ...p,
                    indexing_status: status.status as Project['indexing_status'],
                    is_indexed: status.is_indexed,
                    indexing_error: status.error,
                  }
                : p
            )
          );

          // Continue polling if still indexing
          if (status.status === 'indexing') {
            setTimeout(pollStatus, 3000);
          }
        } catch (err) {
          console.error('Failed to poll indexing status:', err);
        }
      };

      // Start polling after a short delay
      setTimeout(pollStatus, 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start indexing');

      // Revert status on error
      setProjects((prev) =>
        prev.map((p) =>
          p.id === id ? { ...p, indexing_status: 'error' as const } : p
        )
      );
    }
  }, []);

  const getProjectStatus = useCallback(async (id: number) => {
    try {
      const status = await api.getIndexingStatus(id);

      setProjects((prev) =>
        prev.map((p) =>
          p.id === id
            ? {
                ...p,
                indexing_status: status.status as Project['indexing_status'],
                is_indexed: status.is_indexed,
                indexing_error: status.error,
              }
            : p
        )
      );
    } catch (err) {
      console.error('Failed to get project status:', err);
    }
  }, []);

  const stopIndexing = useCallback(async (id: number) => {
    try {
      setError(null);
      await api.stopIndexing(id);

      // Update local state
      setProjects((prev) =>
        prev.map((p) =>
          p.id === id
            ? { ...p, indexing_status: 'stopped' as const, indexing_error: 'Indexing stopped by user' }
            : p
        )
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to stop indexing');
    }
  }, []);

  const clearIndex = useCallback(async (id: number) => {
    try {
      setError(null);
      await api.clearIndex(id);

      // Update local state
      setProjects((prev) =>
        prev.map((p) =>
          p.id === id
            ? { ...p, indexing_status: 'pending' as const, is_indexed: false, indexing_error: null }
            : p
        )
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to clear index');
    }
  }, []);

  return {
    projects,
    selectedProjects,
    isLoading,
    isRefreshing,
    error,
    refreshProjects,
    selectProject,
    deselectProject,
    toggleProjectSelection,
    indexProject,
    stopIndexing,
    clearIndex,
    getProjectStatus,
  };
}

export default useProjects;
