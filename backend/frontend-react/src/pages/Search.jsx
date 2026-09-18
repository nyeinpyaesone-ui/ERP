import React, { useState, useEffect } from 'react';
import { Search as SearchIcon, Loader2, Filter, X } from 'lucide-react';
import { useSearch } from '../hooks/useSearch';

const entityTypes = [
  { value: 'all', label: 'All' },
  { value: 'customers', label: 'Customers' },
  { value: 'products', label: 'Products' },
  { value: 'orders', label: 'Orders' },
  { value: 'invoices', label: 'Invoices' },
  { value: 'employees', label: 'Employees' },
  { value: 'projects', label: 'Projects' },
  { value: 'tickets', label: 'Tickets' },
  { value: 'documents', label: 'Documents' },
];

export default function Search() {
  const { query, setQuery, results, total, facets, loading, error, search, clearSearch } = useSearch();
  const [selectedType, setSelectedType] = useState('all');
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (query.trim()) {
        search({ types: selectedType !== 'all' ? selectedType : undefined });
      } else {
        clearSearch();
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [query, selectedType, search, clearSearch]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim()) {
      search({ types: selectedType !== 'all' ? selectedType : undefined });
    }
  };

  const renderResults = () => {
    if (loading) {
      return (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
        </div>
      );
    }

    if (error) {
      return (
        <div className="text-center py-12 text-red-600">
          Error: {error}
        </div>
      );
    }

    if (!query.trim()) {
      return (
        <div className="text-center py-12 text-gray-500">
          <SearchIcon className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>Enter a search query to find records across all modules</p>
        </div>
      );
    }

    if (total === 0) {
      return (
        <div className="text-center py-12 text-gray-500">
          <SearchIcon className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>No results found for "{query}"</p>
        </div>
      );
    }

    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between text-sm text-gray-500">
          <span>{total} result{total !== 1 ? 's' : ''}</span>
          {facets && Object.keys(facets).length > 0 && (
            <div className="flex gap-4 text-xs">
              {Object.entries(facets).map(([type, count]) => (
                <span key={type} className="px-2 py-1 bg-gray-100 rounded">
                  {type}: {count}
                </span>
              ))}
            </div>
          )}
        </div>

        {results.map((result, index) => (
          <div
            key={`${result.type}-${result.id}-${index}`}
            className="p-4 border rounded-lg hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
                <SearchIcon className="w-5 h-5 text-blue-600" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h4 className="font-medium text-gray-900 truncate">{result.title || result.name || 'Untitled'}</h4>
                  <span className="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded capitalize">
                    {result.type}
                  </span>
                </div>
                <p className="mt-1 text-sm text-gray-500 truncate">
                  {result.description || result.email || result.phone || 'No description'}
                </p>
                <div className="mt-2 flex items-center gap-2 text-xs text-gray-400">
                  {result.metadata && Object.entries(result.metadata).map(([k, v]) => (
                    <span key={k}>{k}: {v}</span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Global Search</h1>
        <p className="text-gray-500 mt-1">Search across all modules and entities</p>
      </div>

      <form onSubmit={handleSubmit} className="relative">
        <div className="relative">
          <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search customers, products, orders, invoices..."
            className="w-full pl-12 pr-12 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-lg"
            autoFocus
          />
          {query && (
            <button
              type="button"
              onClick={() => setQuery('')}
              className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>
      </form>

      <div className="flex items-center gap-4">
        <div className="relative">
          <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
            className="pl-10 pr-8 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent appearance-none bg-white"
          >
            {entityTypes.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>

        <button
          type="button"
          onClick={() => setShowFilters(!showFilters)}
          className="px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50"
        >
          {showFilters ? 'Hide' : 'Show'} Filters
        </button>
      </div>

      {showFilters && (
        <div className="p-4 bg-gray-50 rounded-lg border">
          <p className="text-sm text-gray-600">Advanced filters coming soon...</p>
        </div>
      )}

      <div className="mt-6">{renderResults()}</div>
    </div>
  );
}