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
import './image-display.scss';

export interface ImageDisplayProps {
  src: string;
  alt?: string;
  caption?: string;
}

export const ImageDisplay = ({ src, alt = '', caption }: ImageDisplayProps) => {
  const [isZoomed, setIsZoomed] = useState(false);
  const [loading, setLoading] = useState(true);

  return (
    <div className="image-display">
      <div className={`image-container ${isZoomed ? 'zoomed' : ''}`}>
        <img
          src={src}
          alt={alt}
          onClick={() => setIsZoomed(!isZoomed)}
          onLoad={() => setLoading(false)}
          style={{ display: loading ? 'none' : 'block' }}
        />
        {loading && (
          <div className="loading-indicator">
            <div className="spinner"></div>
          </div>
        )}
      </div>
      {caption && <p className="image-caption">{caption}</p>}
    </div>
  );
};