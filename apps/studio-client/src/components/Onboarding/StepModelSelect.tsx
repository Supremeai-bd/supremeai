
const models = [
  { id: 'gpt-4o', name: 'GPT-4o (OpenAI)', cost: 'High', speed: 'Fast' },
  { id: 'llama-3-70b-versatile', name: 'Llama 3 70B (Groq)', cost: 'Free', speed: 'Blazing' },
  { id: 'claude-3-5-sonnet', name: 'Claude 3.5 Sonnet', cost: 'High', speed: 'Fast' },
];

const StepModelSelect = ({ data, updateData, nextStep, prevStep }: any) => {
  return (
    <div className="flex flex-col space-y-4 animate-fadeIn">
      <h3 className="text-xl font-semibold">Step 2: Choose your default brain</h3>
      <p className="text-gray-400 text-sm">You can always change this later. SupremeAI will route tasks to the best model automatically.</p>
      
      <div className="space-y-3 mt-4">
        {models.map(model => (
          <div 
            key={model.id}
            onClick={() => updateData({ model: model.id })}
            className={`cursor-pointer p-4 rounded-lg border transition-all ${
              data.model === model.id 
                ? 'bg-blue-600/20 border-blue-500 shadow-sm shadow-blue-500/20' 
                : 'bg-gray-700/50 border-gray-600 hover:border-gray-500'
            }`}
          >
            <div className="flex justify-between items-center">
              <span className="font-medium text-gray-100">{model.name}</span>
              <div className="flex space-x-2 text-xs">
                <span className="px-2 py-1 bg-gray-800 rounded-md text-gray-300">{model.speed}</span>
                <span className="px-2 py-1 bg-gray-800 rounded-md text-gray-300">{model.cost}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="flex justify-between pt-6">
        <button 
          onClick={prevStep}
          className="px-6 py-2 text-gray-400 hover:text-white transition-colors"
        >
          Back
        </button>
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

export default StepModelSelect;
