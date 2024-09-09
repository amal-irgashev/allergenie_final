import React, { useState } from 'react';
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { ImageIcon, Scan, Send, Sparkles } from "lucide-react";
import { marked } from 'marked';

const ChatInterface: React.FC = () => {
  const [query, setQuery] = useState('');
  const [response, setResponse] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleCheck = async () => {
    if (query.trim()) {
      setIsLoading(true);
      try {
        const res = await fetch('/api/ask', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: query }),
        });
        
        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }
        
        const data = await res.json();
        if (data && data.result) {
          setResponse(data.result);
        } else {
          throw new Error('Unexpected response structure');
        }
      } catch (error) {
        console.error('Error:', error);
        setResponse(`An error occurred while processing your request: ${error.message}`);
      } finally {
        setIsLoading(false);
      }
    }
  };

  const handleImageUpload = () => {
    console.log('Image upload clicked');
    // Implement image upload logic here
  };

  const handleBarcodeScan = () => {
    console.log('Barcode scan clicked');
    // Implement barcode scanning logic here
  };

  // Custom renderer for marked to style links
  const renderer = new marked.Renderer();
  renderer.link = (href, title, text) => {
    return `<a href="${href}" title="${title || ''}" target="_blank" rel="noopener noreferrer" class="font-bold text-blue-600 hover:underline">${text}</a>`;
  };

  marked.setOptions({ renderer });

  return (
    <div className="min-h-screen flex flex-col bg-white text-gray-900">
      <header className="p-6 border-b border-gray-200">
        <h1 className="text-2xl font-semibold flex items-center space-x-2">
          <span role="img" aria-label="Genie" className="text-3xl">🧞</span>
          <span>Allergenie</span>
        </h1>
      </header>

      <main className="flex-grow flex flex-col p-6 max-w-2xl mx-auto w-full">
        <div className="flex-grow flex items-center justify-center mb-6">
          {response ? (
            <div className="w-full p-6 bg-gray-50 rounded-lg border border-gray-200 animate-fade-in-up shadow-md">
              <h3 className="text-lg font-medium mb-4 flex items-center space-x-2 text-blue-600">
                <Sparkles className="w-5 h-5" />
                <span>Allergenie Response:</span>
              </h3>
              <div 
                dangerouslySetInnerHTML={{ __html: marked(response) }} 
                className="text-gray-700 prose prose-sm max-w-none"
              />
            </div>
          ) : (
            <div className="text-center text-gray-500">
              <span role="img" aria-label="Genie lamp" className="text-6xl mb-4 block">🪔</span>
              <p className="text-lg">Enter a product name or ingredients to check for allergens</p>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="flex items-center space-x-2">
            <Input
              placeholder="Enter product name or ingredients..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="flex-grow bg-white border-gray-300 text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:ring-blue-500 rounded-md"
            />
            <Button size="icon" variant="outline" onClick={handleImageUpload} className="text-gray-700 hover:text-blue-500 hover:border-blue-500">
              <ImageIcon className="h-5 w-5" />
              <span className="sr-only">Upload image</span>
            </Button>
            <Button size="icon" variant="outline" onClick={handleBarcodeScan} className="text-gray-700 hover:text-blue-500 hover:border-blue-500">
              <Scan className="h-5 w-5" />
              <span className="sr-only">Scan barcode</span>
            </Button>
          </div>
          <Button 
            onClick={handleCheck} 
            className="w-full bg-black hover:bg-gray-800 text-white transition-all duration-300 ease-in-out py-6 text-lg rounded-md shadow-lg flex items-center justify-center space-x-2"
            disabled={isLoading}
          >
            {isLoading ? (
              <>
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                <span>Checking...</span>
              </>
            ) : (
              <>
                <Send className="w-5 h-5" />
                <span>Check Safety</span>
              </>
            )}
          </Button>
        </div>
      </main>

      <footer className="p-4 text-center text-gray-500 text-sm border-t border-gray-200">
        © 2023 Allergenie. All rights reserved.
      </footer>
    </div>
  );
};

export default ChatInterface;