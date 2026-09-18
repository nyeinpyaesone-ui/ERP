import { useState, useCallback } from 'react';
import api from '../api/axios';

export function useSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [total, setTotal] = useState(0);
  const [facets, setFacets] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const search = useCallback(async (options = {}) => {
    if (!query.trim()) {
      setResults([]);
      setTotal(0);
      setFacets({});
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({
        q: query,
        limit: 20,
        offset: 0,
      });

      if (options.types) {
        params.append('types', options.types);
      }

      const response = await api.get(`/search/?${params.toString()}`);

      setResults(response.data.results || []);
      setTotal(response.data.total || 0);
      setFacets(response.data.facets || {});
    } catch (err) {
      setError(err.message || 'Search failed');
      setResults([]);
      setTotal(0);
      setFacets({});
    } finally {
      setLoading(false);
    }
  }, [query]);

  const clearSearch = useCallback(() => {
    setResults([]);
    setTotal(0);
    setFacets({});
    setError(null);
  }, []);

  return {
    query,
    setQuery,
    results,
    total,
    facets,
    loading,
    error,
    search,
    clearSearch,
  };
}