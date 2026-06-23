// ============================================================================
// component >> OnboardingWizard.tsx
// project >> SupremeAI 2.0
// purpose >> User onboarding
// module >> src
// ============================================================================
import StepApiKey from './StepApiKey';
import StepModelSelect from './StepModelSelect';
import StepFirstChat from './StepFirstChat';

const OnboardingWizard = () => {
  const [step, setStep] = useState(1);
  const [onboardingData, setOnboardingData] = useState({
    apiKey: '',
    model: 'gpt-4o',
    firstPrompt: ''
  });

  const nextStep = () => setStep((prev) => prev + 1);
  const prevStep = () => setStep((prev) => prev - 1);

  const handleUpdate = (data: Partial<typeof onboardingData>) => {
    setOnboardingData((prev) => ({ ...prev, ...data }));
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-900 text-white p-6">
      <div className="max-w-xl w-full bg-gray-800 rounded-xl shadow-xl p-8 border border-gray-700">
        <h2 className="text-3xl font-bold mb-6 text-center text-blue-400">Welcome to SupremeAI 2.0</h2>
        
        {/* Progress Bar */}
        <div className="flex justify-between mb-8">
          {[1, 2, 3].map((num) => (
            <div key={num} className={`w-1/3 h-2 rounded-full mx-1 ${step >= num ? 'bg-blue-500' : 'bg-gray-600'}`} />
          ))}
        </div>

        {/* Steps */}
        {step === 1 && <StepApiKey data={onboardingData} updateData={handleUpdate} nextStep={nextStep} />}
        {step === 2 && <StepModelSelect data={onboardingData} updateData={handleUpdate} nextStep={nextStep} prevStep={prevStep} />}
        {step === 3 && <StepFirstChat data={onboardingData} updateData={handleUpdate} prevStep={prevStep} />}
      </div>
    </div>
  );
};

export default OnboardingWizard;
