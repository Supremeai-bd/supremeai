// Simple health + stats endpoints for emulator stability

exports.healthCheck = (req, res) => {
  res.set('Access-Control-Allow-Origin', '*');
  res.json({ status: 'ok', timestamp: new Date().toISOString(), mode: 'emulator' });
};

exports.getProviderHealthStats = (req, res) => {
  res.set('Access-Control-Allow-Origin', '*');
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
