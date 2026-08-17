// Simple health + stats endpoints for emulator stability

const allowedOrigins = [
  'https://supremeai-dashboard.web.app',
  'http://localhost:5173',
  'https://studio.supremeai.com',
];

const getAllowedOrigin = (req) => {
  const origin = req.get('origin');
  return origin && (allowedOrigins.includes(origin) || origin.includes('supremeai'))
    ? origin
    : 'https://supremeai-dashboard.web.app';
};

exports.healthCheck = (req, res) => {
  const allowedOrigin = getAllowedOrigin(req);
  res.set('Access-Control-Allow-Origin', allowedOrigin);
  res.json({ status: 'ok', timestamp: new Date().toISOString(), mode: 'emulator' });
};

exports.getProviderHealthStats = (req, res) => {
  const allowedOrigin = getAllowedOrigin(req);
  res.set('Access-Control-Allow-Origin', allowedOrigin);
  res.json({
    success: true,
    data: {
      total: 2,
      active: 2,
      error: 0,
      rotating: 0,
      lastCheck: new Date().toISOString()
    }
  });
};
