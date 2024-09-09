import React from 'react';
import { marked } from 'marked';
import { FaSpinner } from 'react-icons/fa';

interface ResultProps {
  result: string;
  isLoading: boolean;
}

const Result: React.FC<ResultProps> = ({ result, isLoading }) => {
  return (
    <div className="result">
      {isLoading ? (
        <div className="loading">
          <FaSpinner className="spinner" /> Analyzing...
        </div>
      ) : (
        <div dangerouslySetInnerHTML={{ __html: marked(result) }} />
      )}
    </div>
  );
}

export default Result;