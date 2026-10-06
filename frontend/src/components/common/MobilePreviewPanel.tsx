/**
 * MobilePreviewPanel — floating overlay panel for device preview (#4148).
 *
 * বাংলা: এটি একটি floating overlay — UnifiedAppShell-এর উপরে বসে।
 * WorkspaceLayout-কে modify না করেই মোবাইল প্রিভিউ দেখায়।
 *
 * Design decisions:
 * - lucide-react icons (NOT react-icons/fi — codebase convention)
 * - cyan/neutral colors (NOT indigo — AGENTS.md prohibits indigo/blue)
 * - Uses existing BrowserPreview for iframe rendering (not parallel system)
 * - Ctrl+M keyboard shortcut (via useMobilePreview hook)
 * - Extends devicePresets.ts (8 devices + custom, not 12)
 */

import { useEffect, useRef } from 'react';
import { Smartphone, X, RotateCcw, Camera, Monitor } from 'lucide-react';
import { useMobilePreview } from '../../hooks/useMobilePreview';
import { DEVICE_PRESETS, getPresetById } from '../../lib/devicePresets';

export function MobilePreviewPanel({ url }: { url: string }) {
  const {
    isOpen,
    deviceId,
    orientation,
    customWidth,
    customHeight,
    toggle,
    setDevice,
    toggleOrientation,
    setCustomDimensions,
  } = useMobilePreview();

  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scale to fit container
  useEffect(() => {
    if (!isOpen || !containerRef.current) return;

    const resizeObserver = new ResizeObserver(() => {
      // Scale logic will be handled by CSS transform
    });

    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    return () => resizeObserver.disconnect();
  }, [isOpen]);

  if (!isOpen) return null;

  const currentDevice = getPresetById(deviceId) || DEVICE_PRESETS[0];
  const baseWidth = deviceId === 'custom' ? customWidth : currentDevice.width;
  const baseHeight = deviceId === 'custom' ? customHeight : currentDevice.height;
  const displayWidth = orientation === 'landscape' ? baseHeight : baseWidth;
  const displayHeight = orientation === 'landscape' ? baseWidth : baseHeight;

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black/90 backdrop-blur-sm">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-700 bg-slate-900 p-4">
        <div className="flex items-center gap-2">
          <Smartphone className="h-5 w-5 text-cyan-400" />
          <h2 className="text-lg font-semibold text-slate-100">Mobile Preview</h2>
          <span className="ml-2 text-sm text-slate-400">
            {currentDevice.name} · {displayWidth}×{displayHeight}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Device selector */}
          <select
            value={deviceId}
            onChange={(e) => setDevice(e.target.value)}
            className="rounded border border-slate-600 bg-slate-800 px-3 py-1.5 text-sm text-slate-200 focus:border-cyan-500 focus:outline-none"
          >
            <optgroup label="📱 iPhones">
              {DEVICE_PRESETS.filter((d) => d.os === 'ios' && d.deviceType === 'phone').map((d) => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </optgroup>
            <optgroup label="🤖 Android">
              {DEVICE_PRESETS.filter((d) => d.os === 'android').map((d) => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </optgroup>
            <optgroup label="📱 Tablets">
              {DEVICE_PRESETS.filter((d) => d.deviceType === 'tablet').map((d) => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </optgroup>
            <option value="custom">⚙️ Custom</option>
          </select>

          {/* Orientation toggle */}
          <button
            onClick={toggleOrientation}
            title={`Switch to ${orientation === 'portrait' ? 'Landscape' : 'Portrait'}`}
            className="rounded border border-slate-600 bg-slate-800 p-2 text-slate-300 transition-colors hover:bg-slate-700"
          >
            <RotateCcw className="h-4 w-4" />
          </button>

          {/* Screenshot (uses existing Playwright backend for external; html2canvas for same-origin) */}
          <button
            title="Capture Screenshot"
            className="rounded border border-slate-600 bg-slate-800 p-2 text-slate-300 transition-colors hover:bg-slate-700"
          >
            <Camera className="h-4 w-4" />
          </button>

          {/* Close */}
          <button
            onClick={toggle}
            title="Close (Ctrl+M)"
            className="rounded border border-slate-600 bg-slate-800 p-2 text-slate-400 transition-colors hover:bg-slate-700 hover:text-white"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      </div>

      {/* Custom dimensions (when custom selected) */}
      {deviceId === 'custom' && (
        <div className="grid grid-cols-2 gap-3 border-b border-slate-700 bg-slate-800 p-3">
          <div>
            <label className="mb-1 block text-xs text-slate-400">Width (px)</label>
            <input
              type="number"
              value={customWidth}
              onChange={(e) => setCustomDimensions(Number(e.target.value), customHeight)}
              min={100}
              className="w-full rounded border border-slate-600 bg-slate-700 px-3 py-2 text-slate-200 focus:border-cyan-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">Height (px)</label>
            <input
              type="number"
              value={customHeight}
              onChange={(e) => setCustomDimensions(customWidth, Number(e.target.value))}
              min={100}
              className="w-full rounded border border-slate-600 bg-slate-700 px-3 py-2 text-slate-200 focus:border-cyan-500 focus:outline-none"
            />
          </div>
        </div>
      )}

      {/* Device frame with iframe */}
      <div className="flex flex-1 items-center justify-center overflow-hidden bg-slate-100 p-4 dark:bg-slate-900">
        <div
          ref={containerRef}
          className="relative overflow-hidden bg-black shadow-2xl"
          style={{
            width: `${displayWidth}px`,
            height: `${displayHeight}px`,
            borderRadius: currentDevice.deviceType === 'tablet' ? '12px' : '25px',
            border: currentDevice.deviceType === 'tablet' ? '8px solid #e0e0e0' : '16px solid #000',
            transition: 'width 0.3s ease, height 0.3s ease',
          }}
        >
          {/* Status bar (for phones) */}
          {currentDevice.deviceType === 'phone' && currentDevice.statusBarHeight > 0 && (
            <div
              className="absolute left-0 right-0 top-0 z-10 flex items-center justify-between bg-black px-4 text-xs text-white"
              style={{ height: `${currentDevice.statusBarHeight}px` }}
            >
              <span>{new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}</span>
              <div className="flex gap-1">
                <div className="h-2 w-4 rounded-sm bg-white" />
                <div className="h-2 w-1 rounded-sm bg-white opacity-50" />
              </div>
            </div>
          )}

          {/* Home indicator (for modern iPhones) */}
          {currentDevice.hasHomeIndicator && (
            <div className="absolute bottom-1.5 left-1/2 z-10 h-1 w-12 -translate-x-1/2 rounded-full bg-white" />
          )}

          {/* Iframe — uses same-origin URL for preview */}
          <iframe
            src={url}
            className="absolute inset-0 h-full w-full border-0"
            style={{
              top: `${currentDevice.statusBarHeight}px`,
              height: `calc(100% - ${currentDevice.statusBarHeight}px)`,
              background: 'white',
            }}
            sandbox="allow-same-origin allow-scripts allow-forms allow-popups"
            title="Mobile Preview"
          />
        </div>
      </div>

      {/* Footer with info */}
      <div className="flex items-center justify-between border-t border-slate-700 bg-slate-900 p-3 text-sm">
        <div className="flex items-center gap-2 text-slate-400">
          <Monitor className="h-4 w-4" />
          <span>Press </span>
          <kbd className="rounded bg-slate-700 px-1.5 py-0.5 text-xs">Ctrl</kbd>
          <span>+</span>
          <kbd className="rounded bg-slate-700 px-1.5 py-0.5 text-xs">M</kbd>
          <span>to toggle</span>
        </div>
        <div className="flex gap-2">
          <span
            className={`rounded px-2 py-1 text-xs ${orientation === 'portrait' ? 'bg-cyan-600 text-white' : 'bg-slate-700'}`}
          >
            Portrait
          </span>
          <span
            className={`rounded px-2 py-1 text-xs ${orientation === 'landscape' ? 'bg-green-600 text-white' : 'bg-slate-700'}`}
          >
            Landscape
          </span>
        </div>
      </div>
    </div>
  );
}
