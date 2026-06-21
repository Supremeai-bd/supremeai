import { useState } from 'react';
import { Card, Badge } from '../ui';
import { Smartphone, Tablet, RefreshCw } from 'lucide-react';

interface MobileSimulatorProps {
  html?: string;
  url?: string;
}

const DEVICES = [
  { id: 'iphone', name: 'iPhone 15', width: 390, height: 844, icon: Smartphone },
  { id: 'pixel', name: 'Pixel 8', width: 412, height: 915, icon: Smartphone },
  { id: 'ipad', name: 'iPad Pro', width: 1024, height: 1366, icon: Tablet },
];

type Orientation = 'portrait' | 'landscape';

export function MobileSimulator({ html, url = 'https://supremeai.web.app' }: MobileSimulatorProps) {
  const [selectedDevice, setSelectedDevice] = useState(DEVICES[0]);
  const [orientation, setOrientation] = useState<Orientation>('portrait');

  const currentWidth = orientation === 'portrait' ? selectedDevice.width : selectedDevice.height;
  const currentHeight = orientation === 'portrait' ? selectedDevice.height : selectedDevice.width;

  return (
    <div className="flex-grow p-6 overflow-y-auto bg-[#030508]">
      <div className="flex items-center justify-between mb-6 pb-2 border-b border-[#00f3ff]/15">
        <h2 className="text-lg font-bold font-['Space_Grotesk'] tracking-widest text-[#00f3ff] uppercase">
          📱 Mobile Simulator
        </h2>
      </div>

      <div className="flex gap-2 mb-6">
        {DEVICES.map(device => (
          <button
            key={device.id}
            onClick={() => setSelectedDevice(device)}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs font-mono transition-all ${
              selectedDevice.id === device.id
                ? 'border-[#00f3ff]/50 bg-[#00f3ff]/10 text-[#00f3ff]'
                : 'border-slate-800 text-slate-400 hover:border-slate-700'
            }`}
          >
            <device.icon size={14} />
            {device.name}
          </button>
        ))}
        <button
          onClick={() => setOrientation(o => (o === 'portrait' ? 'landscape' : 'portrait'))}
          className="flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-800 text-slate-400 hover:text-white text-xs font-mono transition-colors"
        >
          <RefreshCw size={14} /> Rotate
        </button>
      </div>

      <Card>
        <div className="flex justify-center">
          <div
            className="border-4 border-slate-700 rounded-[2.5rem] p-2 bg-slate-900 shadow-2xl transition-all duration-300"
            style={{
              width: Math.min(currentWidth / 3, 400),
              height: Math.min(currentHeight / 3, 700),
            }}
          >
            <div className="w-full h-full rounded-[2rem] overflow-hidden bg-white relative">
              <div className="absolute top-0 left-1/2 -translate-x-1/2 w-1/3 h-6 bg-slate-900 rounded-b-xl z-10" />
              {html ? (
                <iframe srcDoc={html} title={selectedDevice.name} className="w-full h-full" sandbox="allow-scripts allow-forms" />
              ) : (
                <iframe src={url} title={selectedDevice.name} className="w-full h-full" sandbox="allow-scripts allow-forms" />
              )}
            </div>
          </div>
        </div>
        <div className="mt-4 flex items-center justify-between">
          <Badge variant="info">{selectedDevice.name}</Badge>
          <span className="text-[10px] text-slate-500 font-mono">
            {currentWidth} x {currentHeight} • {orientation}
          </span>
        </div>
      </Card>
    </div>
  );
}
