'use client';

import { useProjects } from '@/hooks/useProjects';
import IndexingStatus from './IndexingStatus';

export default function ProjectSelector() {
  const {
    projects,
    vectorCounts,
    isLoading,
    isRefreshing,
    error,
    refreshProjects,
    toggleProjectSelection,
    indexProject,
    syncProject,
    stopIndexing,
    clearIndex,
  } = useProjects();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
        <p className="font-medium">Error loading projects</p>
        <p className="text-sm mt-1">{error}</p>
        <button
          onClick={refreshProjects}
          className="mt-3 text-sm text-red-600 hover:text-red-800 underline"
        >
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Actions bar */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-600">
          {projects.filter((p) => p.is_selected).length} of {projects.length}{' '}
          projects selected
        </p>
        <button
          onClick={refreshProjects}
          disabled={isRefreshing}
          className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
        >
          <svg
            className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          {isRefreshing ? 'Refreshing...' : 'Refresh from GitLab'}
        </button>
      </div>

      {/* Project grid */}
      {projects.length === 0 ? (
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
              d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
            />
          </svg>
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            No projects found
          </h3>
          <p className="text-gray-600 mb-4">
            Click &quot;Refresh from GitLab&quot; to fetch your accessible projects.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((project) => (
            <div
              key={project.id}
              className={`bg-white rounded-lg border-2 p-4 transition-all ${
                project.is_selected
                  ? 'border-blue-500 ring-1 ring-blue-500'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              {/* Header */}
              <div className="flex items-start justify-between gap-2 mb-3">
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium text-gray-900 truncate">
                    {project.name}
                  </h3>
                  <p className="text-xs text-gray-500 truncate">
                    {project.path_with_namespace}
                  </p>
                </div>
                <input
                  type="checkbox"
                  checked={project.is_selected}
                  onChange={() => toggleProjectSelection(project.id)}
                  className="mt-1 h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                />
              </div>

              {/* Description */}
              {project.description && (
                <p className="text-sm text-gray-600 mb-3 line-clamp-2">
                  {project.description}
                </p>
              )}

              {/* Vector count badge */}
              {vectorCounts[project.gitlab_id] > 0 && (
                <div className="flex items-center gap-1 text-xs text-gray-500 mb-2">
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
                  </svg>
                  <span>{vectorCounts[project.gitlab_id].toLocaleString()} vectors</span>
                </div>
              )}

              {/* Last indexed time */}
              {project.last_indexed_at && (
                <div className="text-xs text-gray-400 mb-2">
                  Last indexed: {new Date(project.last_indexed_at).toLocaleDateString()}
                </div>
              )}

              {/* Status & Actions */}
              <div className="flex items-center justify-between pt-3 border-t border-gray-100">
                <IndexingStatus
                  status={project.indexing_status}
                  error={project.indexing_error}
                  isIndexed={project.is_indexed}
                  size="sm"
                />

                <div className="flex items-center gap-2">
                  {project.indexing_status === 'indexing' || project.indexing_status === 'syncing' ? (
                    <button
                      onClick={() => stopIndexing(project.id)}
                      className="text-xs font-medium text-red-600 hover:text-red-800"
                    >
                      Stop
                    </button>
                  ) : (
                    <>
                      {project.is_indexed ? (
                        <>
                          <button
                            onClick={() => syncProject(project.id)}
                            className="text-xs font-medium text-blue-600 hover:text-blue-800"
                            title="Quick sync: only fetch new/updated content"
                          >
                            Sync
                          </button>
                          <button
                            onClick={() => indexProject(project.id)}
                            className="text-xs font-medium text-gray-500 hover:text-gray-700"
                            title="Full re-index: fetch all content"
                          >
                            Full
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={() => indexProject(project.id)}
                          className="text-xs font-medium text-blue-600 hover:text-blue-800"
                        >
                          Index
                        </button>
                      )}
                      {project.is_indexed && (
                        <button
                          onClick={() => {
                            if (confirm('Are you sure you want to clear all indexed data for this project?')) {
                              clearIndex(project.id);
                            }
                          }}
                          className="text-xs font-medium text-gray-400 hover:text-red-600"
                          title="Clear indexed data"
                        >
                          Clear
                        </button>
                      )}
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
