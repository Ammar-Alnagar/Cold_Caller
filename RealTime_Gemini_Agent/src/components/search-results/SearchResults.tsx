/**
 * Copyright 2024 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 */
import { useState } from 'react';
import './search-results.scss';

export interface SearchResult {
  title: string;
  snippet: string;
  url: string;
  thumbnail?: string;
}

interface SearchResultsProps {
  results: SearchResult[];
  onResultClick?: (result: SearchResult) => void;
}

export const SearchResults = ({ results, onResultClick }: SearchResultsProps) => {
  const [page, setPage] = useState(0);
  const resultsPerPage = 5;

  const paginatedResults = results.slice(
    page * resultsPerPage,
    (page + 1) * resultsPerPage
  );

  const totalPages = Math.ceil(results.length / resultsPerPage);

  return (
    <div className="search-results">
      {paginatedResults.map((result, index) => (
        <div 
          key={index} 
          className="result-item"
          onClick={() => onResultClick?.(result)}
        >
          {result.thumbnail && (
            <img src={result.thumbnail} alt="" className="result-thumbnail" />
          )}
          <div className="result-content">
            <h3>{result.title}</h3>
            <p>{result.snippet}</p>
            <a href={result.url} target="_blank" rel="noopener noreferrer">
              {result.url}
            </a>
          </div>
        </div>
      ))}
      
      {totalPages > 1 && (
        <div className="pagination">
          <button 
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
          >
            Previous
          </button>
          <span>{page + 1} of {totalPages}</span>
          <button 
            onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
            disabled={page === totalPages - 1}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
};