import { QuickPresets } from './customer/QuickPresets';
import { CodeEditor } from './customer/CodeEditor';
import { ChatPanel } from './customer/ChatPanel';
import type { ChatMessage } from '../types';

interface OperatorStudioProps {
  code: string;
  setCode: (code: string) => void;
  customerMessages: ChatMessage[];
  customerInput: string;
  setCustomerInput: (val: string) => void;
  loading: boolean;
  handleSendCustomer: () => void;
  theme: 'dark' | 'light';
  toggleTheme: () => void;
}

export function OperatorStudio({
  code,
  setCode,
  customerMessages,
  customerInput,
  setCustomerInput,
  loading,
  handleSendCustomer,
  theme,
  toggleTheme
}: OperatorStudioProps) {
   return (
     <div className="flex-1 flex flex-col overflow-hidden">
       <div className="flex-shrink-0 p-4 border-b border-[#00f3ff]/20 flex justify-between items-center">
         <h2 className="text-xl font-bold font-['Space_Grotesk'] tracking-widest uppercase">
           Operator Studio
         </h2>
         <div className="flex items-center gap-2">
           <button
             onClick={toggleTheme}
             className="text-xs font-bold text-[#00f3ff] hover:text-cyan-400 tracking-wider transition-colors"
           >
             {theme === 'dark' ? '🌙 Light Mode' : '☀️ Dark Mode'}
           </button>
         </div>
       </div>
        <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
          <QuickPresets onSelectPreset={setCustomerInput} className="lg:w-64 lg:flex-shrink-0 w-full mb-4 lg:mb-0" />
          <div className="flex-1 flex flex-col gap-4">
            <CodeEditor code={code} onChange={setCode} className="flex-1" />
            <ChatPanel
              messages={customerMessages}
              input={customerInput}
              onInputChange={setCustomerInput}
              onSend={handleSendCustomer}
              loading={loading}
              onSaveToProject={setCode}
              className="flex-1"
            />
          </div>
        </div>
     </div>
   );
}
