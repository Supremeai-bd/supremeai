import {  } from 'react';

interface LoginViewProps {
  adminEmail: string;
  setAdminEmail: (val: string) => void;
  adminPassword: string;
  setAdminPassword: (val: string) => void;
  otpRequired: boolean;
  totpSetupRequired: boolean;
  provisioningUri: string;
  totpSecret: string;
  adminOtp: string;
  setAdminOtp: (val: string) => void;
  adminError: string;
  handleAdminLogin: () => void;
  handleAdminOtpVerify: () => void;
}

export function LoginView({
  adminEmail,
  setAdminEmail,
  adminPassword,
  setAdminPassword,
  otpRequired,
  totpSetupRequired,
  provisioningUri,
  totpSecret,
  adminOtp,
  setAdminOtp,
  adminError,
  handleAdminLogin,
  handleAdminOtpVerify,
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
        
        {!otpRequired ? (
          <div className="flex flex-col gap-3.5">
            <input
              type="email"
              placeholder="Enter Admin Email..."
              value={adminEmail}
              onChange={e => setAdminEmail(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleAdminLogin()}
              className="w-full text-center bg-[#07090f] border border-slate-800 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-[#00f3ff] transition-all font-mono"
            />
            <input
              type="password"
              placeholder="Enter Admin Password..."
              value={adminPassword}
              onChange={e => setAdminPassword(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleAdminLogin()}
              className="w-full text-center bg-[#07090f] border border-slate-800 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-[#00f3ff] transition-all font-mono"
            />
            {adminError && <div className="text-[#ff4d4f] text-xs mt-1 font-mono">{adminError}</div>}
          </div>
        ) : (
          <OtpSection
            totpSetupRequired={totpSetupRequired}
            provisioningUri={provisioningUri}
            totpSecret={totpSecret}
            adminOtp={adminOtp}
            setAdminOtp={setAdminOtp}
            adminError={adminError}
            handleAdminOtpVerify={handleAdminOtpVerify}
          />
        )}
        
        <button
          onClick={otpRequired ? handleAdminOtpVerify : handleAdminLogin}
          className="cyber-button w-full uppercase py-3 text-xs tracking-wider font-mono font-bold"
        >
          {otpRequired ? "Verify OTP & Authorize" : "Sign In & Continue"}
        </button>
      </div>
    </div>
  );
}

function OtpSection({
  totpSetupRequired,
  provisioningUri,
  totpSecret,
  adminOtp,
  setAdminOtp,
  adminError,
  handleAdminOtpVerify,
}: {
  totpSetupRequired: boolean;
  provisioningUri: string;
  totpSecret: string;
  adminOtp: string;
  setAdminOtp: (val: string) => void;
  adminError: string;
  handleAdminOtpVerify: () => void;
}) {
  return (
    <div className="flex flex-col gap-4 items-center">
      {totpSetupRequired && provisioningUri && (
        <div className="flex flex-col items-center gap-2.5 p-3.5 bg-cyan-950/20 border border-cyan-800/20 rounded-xl max-w-xs">
          <div className="text-[11px] text-[#00f3ff] font-bold font-mono">Scan this QR Code in Authenticator:</div>
          <img 
            src={`https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${encodeURIComponent(provisioningUri)}`} 
            alt="Google Authenticator QR Code"
            className="border-2 border-[#00f3ff] rounded-lg bg-white p-1"
          />
          <div className="text-[10px] text-slate-400 font-mono text-center">
            Or enter manual key: <br />
            <span className="text-white font-bold select-all">{totpSecret}</span>
          </div>
        </div>
      )}
      <input
        type="text"
        placeholder="Enter 6-digit OTP Code..."
        value={adminOtp}
        onChange={e => setAdminOtp(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && handleAdminOtpVerify()}
        className="w-full text-center bg-[#07090f] border border-slate-800 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-[#00f3ff] transition-all font-mono tracking-widest text-lg"
        maxLength={6}
      />
      {adminError && <div className="text-[#ff4d4f] text-xs mt-1 font-mono">{adminError}</div>}
      <div className="text-[10px] text-slate-500 font-mono text-center">
        {!totpSetupRequired ? "Enter the 6-digit code from your Google Authenticator app." : "Confirm code to activate and authorize your account."}
      </div>
    </div>
  );
}