// CORS
 GLOBAL CORS (for 127.0.0.1 emulator + future) ============
const allowedOrigins = [
    'http://127.0.0.1:3000',
    'http://127.0.0.1:5173',
    'http://127.0.0.1:5000',
    'http://127.0.0.1:3000',
    'http://127.0.0.1:5173',
    'http://127.0.0.1:5000'
];

const allowCors = (handler) => async (req, res) => {
    const origin = req.headers.origin;
    const allowedOrigin = (origin && (allowedOrigins.includes(origin) || origin.includes('supremeai'))) ? origin : 'https://supremeai-dashboard.web.app';

    res.set('Access-Control-Allow-Origin', allowedOrigin);
    res.set('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
    res.set('Access-Control-Allow-Headers', 'Content-Type, Authorization, x-api-key');
    res.set('Vary', 'Origin');

    if (req.method === 'OPTIONS') {
        return res.status(204).send('');
    }
    return handler(req, res);
};

