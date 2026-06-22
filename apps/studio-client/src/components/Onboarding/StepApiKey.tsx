import React from 'react';

const StepApiKey = ({ data, updateData, nextStep }: any) => {
  return (
    <div className="flex flex-col space-y-4 animate-fadeIn">
      <h3 className="text-xl font-semibold">Step 1: Connect your preferred API</h3>
      <p className="text-gray-400 text-sm">To ensure zero-cost operations, SupremeAI connects to your existing accounts (OpenRouter, Groq, Google, etc).</p>
      
      <div className="space-y-2 mt-4">
        <label className="block text-sm font-medium text-gray-300">OpenRouter API Key (Recommended)</label>
        <input 
          type="password" 
          placeholder="sk-or-v1-..."
          className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
          value={data.apiKey}
          onChange={(e) => updateData({ apiKey: e.target.value })}
        />
      </div>

      <div className="flex justify-end pt-6">
        <button 
          onClick={nextStep}
          className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium shadow-lg shadow-blue-500/30"
        >
          Next
        </button>
      </div>
    </div>
  );
};

export default StepApiKey;
