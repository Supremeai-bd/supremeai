// SupremeAI Integration Module for Studio (Open WebUI Engine)
export * from './audioFx';
export * from './controlPlane';
export * from './types';

export const SUPREMEAI_CONFIG = {
  name: 'SupremeAI Studio',
  version: '2.0.0',
  mcpControlPlaneUrl: import.meta.env.VITE_MCP_CONTROL_PLANE_URL || 'https://supremeai-mcp-tower.onrender.com/mcp',
  gatewayUrl: import.meta.env.VITE_GATEWAY_URL || 'https://supremeai-gateway.onrender.com',
};

