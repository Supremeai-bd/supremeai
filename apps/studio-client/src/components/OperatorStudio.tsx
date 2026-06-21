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
}

export function OperatorStudio({
  code,
  setCode,
  customerMessages,
  customerInput,
  setCustomerInput,
  loading,
  handleSendCustomer
}: OperatorStudioProps) {
  return (
    <div className="flex-1 flex flex-row overflow-hidden">
      <QuickPresets onSelectPreset={setCustomerInput} />
      <CodeEditor code={code} onChange={setCode} />
      <ChatPanel
        messages={customerMessages}
        input={customerInput}
        onInputChange={setCustomerInput}
        onSend={handleSendCustomer}
        loading={loading}
      />
    </div>
  );
}
