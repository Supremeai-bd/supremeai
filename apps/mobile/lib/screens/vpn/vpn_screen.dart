import 'package:flutter/material.dart';
import 'dart:ui';
import '../../services/localization_service.dart';
import '../../services/screen_api_service.dart';

class VpnScreen extends StatefulWidget {
  const VpnScreen({super.key});

  @override
  State<VpnScreen> createState() => _VpnScreenState();
}

class _VpnScreenState extends State<VpnScreen> {
  final _api = ScreenApiService();
  bool _connecting = false;
  String? _activeNode;
  String _status = 'initializing';
  List<Map<String, dynamic>> _nodes = const [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    final data = await _api.ping('vpn');
    if (!mounted) return;
    setState(() {
      _status = data['status']?.toString() ?? 'offline';
      _nodes = List<Map<String, dynamic>>.from(data['nodes'] ?? data['data']?['nodes'] ?? const []);
      _loading = false;
      _activeNode = _nodes.indexWhere((n) => n['connected'] == true || n['active'] == true) >= 0 ? _nodes.firstWhere((n) => n['connected'] == true || n['active'] == true, orElse: () => const {})['name'] : null;
    });
  }

  Future<void> _connect(String name) async {
    setState(() => _connecting = true);
    final result = await _api.action('vpn', {'action': 'connect', 'node': name});
    if (!mounted) return;
    setState(() {
      _connecting = false;
      _activeNode = name;
      _status = result['status'] ?? 'connected';
    });
    await _refresh();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        elevation: 0,
        title: Text('vpn.title'.tr(), style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, letterSpacing: 1.5, color: Colors.white)),
        actions: [
          IconButton(onPressed: _refresh, icon: const Icon(Icons.refresh, color: Colors.white70)),
        ],
      ),
      body: _loading ? const Center(child: CircularProgressIndicator(color: Colors.blueAccent)) : SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildStatusHeader(),
            const SizedBox(height: 32),
            Text('vpn.status'.tr().toUpperCase(), style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w900, letterSpacing: 2, color: Colors.white54)),
            const SizedBox(height: 16),
            ...(_nodes.isEmpty ? [_buildEmptyNodesTile()] : _nodes.map((node) => _buildNodeCard(node))),
          ],
        ),
      ),
    );
  }

  Widget _buildStatusHeader() {
    final connected = _activeNode != null;
    final iconColor = connected ? Colors.greenAccent : Colors.blueAccent;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: LinearGradient(colors: [Colors.blueAccent.withValues(alpha: 0.1), Colors.purpleAccent.withValues(alpha: 0.05)], begin: Alignment.topLeft, end: Alignment.bottomRight),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: Colors.blueAccent.withValues(alpha: 0.2)),
      ),
      child: Column(
        children: [
          Icon(Icons.security, color: iconColor, size: 48),
          const SizedBox(height: 16),
          Text('${'vpn.secure_gateway'.tr()} (${_status.toUpperCase()})', style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold), textAlign: TextAlign.center),
          const SizedBox(height: 8),
          Text('vpn.description'.tr(), style: const TextStyle(color: Colors.white54, fontSize: 13, height: 1.5), textAlign: TextAlign.center),
        ],
      ),
    );
  }

  Widget _buildNodeCard(Map<String, dynamic> node) {
    final name = node['name']?.toString() ?? 'Unknown';
    final connected = node['connected'] == true || node['active'] == true;
    final statusText = connected ? 'vpn.connected'.tr() : 'vpn.disconnected'.tr();
    final color = connected ? Colors.greenAccent : Colors.white24;
    final icon = connected ? Icons.vpn_lock : Icons.lock_outline;
    final isCurrentConnecting = _connecting && _activeNode == name;

    return GestureDetector(
      onTap: _connecting ? null : () => _connect(name),
      child: Container(
        margin: const EdgeInsets.only(bottom: 16),
        decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.03), borderRadius: BorderRadius.circular(20), border: Border.all(color: Colors.white10)),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(20),
          child: BackdropFilter(filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10), child: Padding(
            padding: const EdgeInsets.all(20),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(color: color.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(16)),
                  child: isCurrentConnecting
                      ? const SizedBox(
                          width: 28,
                          height: 28,
                          child: CircularProgressIndicator(color: Colors.blueAccent, strokeWidth: 2),
                        )
                      : Icon(icon, color: color, size: 28),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(name, style: const TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 4),
                      Text(node['latency']?.toString() ?? 'Unknown latency', style: const TextStyle(color: Colors.white38, fontSize: 12)),
                    ],
                  ),
                ),
                Text(statusText, style: TextStyle(color: color, fontWeight: FontWeight.w900, fontSize: 14)),
              ],
            ),
          )),
        ),
      ),
    );
  }

  Widget _buildEmptyNodesTile() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.03), borderRadius: BorderRadius.circular(20), border: Border.all(color: Colors.white10)),
      child: Center(child: Text('No VPN nodes configured'.tr(), style: const TextStyle(color: Colors.white54))),
    );
  }
}
