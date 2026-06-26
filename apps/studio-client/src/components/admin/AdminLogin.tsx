import {  } from 'react';

interface LoginViewProps {
  adminPassword: string;
  setAdminPassword: (val: string) => void;
  adminError: string;
  handleAdminLogin: () => void;
  otpRequired: boolean;
  adminOtp: string;
  setAdminOtp: (val: string) => void;
}

export function LoginView({
  adminPassword,
  setAdminPassword,
  adminError,
  handleAdminLogin,
  otpRequired,
  adminOtp,
  setAdminOtp,
}: LoginViewProps) {
  return (
    <div className="flex-1 flex items-center justify-center p-6">
      <div className="w-full max-w-md glass-card text-center flex flex-col gap-6 relative overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-[#00f3ff] to-[#bc13fe]"></div>
        <div>
          <span className="text-5xl block mb-2 drop-shadow-[0_0_12px_#bc13fe]">👑</span>
          <h2 className="text-xl font-bold font-['Space_Grotesk'] tracking-widest uppercase">
            SupremeAI <span className="text-[#00f3ff]">Admin Gate</span>
          </h2>
          <p className="text-slate-400 text-xs mt-1">Authorized access only. Authentication protocol required.</p>
        </div>
        
        <div className="flex flex-col gap-3.5">
          <input
            type="password"
            placeholder="Enter Authentication Code..."
            value={adminPassword}
            onChange={e => setAdminPassword(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleAdminLogin()}
            className="w-full text-center bg-[#07090f] border border-slate-800 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-[#00f3ff] transition-all font-mono tracking-widest"
          />
          {otpRequired && (
            <input
              type="text"
              placeholder="Enter 6-digit OTP"
              value={adminOtp}
              onChange={e => setAdminOtp(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleAdminLogin()}
              className="w-full text-center bg-[#07090f] border border-slate-800 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-[#00f3ff] transition-all font-mono tracking-widest"
            />
          )}
          {adminError && <div className="text-[#ff4d4f] text-xs mt-1 font-mono">{adminError}</div>}
        </div>
        
        <button
          onClick={handleAdminLogin}
          className="cyber-button w-full uppercase py-3 text-xs tracking-wider font-mono font-bold"
        >
          {otpRequired ? 'Verify OTP' : 'Authorize Access'}
        </button>
      </div>
    </div>
  );
}