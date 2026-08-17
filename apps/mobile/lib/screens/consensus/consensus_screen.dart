import 'package:flutter/material.dart';
import 'dart:ui';
import '../../services/localization_service.dart';
import '../../services/screen_api_service.dart';

class ConsensusScreen extends StatefulWidget {
  const ConsensusScreen({super.key});

  @override
  State<ConsensusScreen> createState() => _ConsensusScreenState();
}

class _ConsensusScreenState extends State<ConsensusScreen> {
  final _api = ScreenApiService();
  bool _loading = true;
  List<Map<String, dynamic>> _sessions = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final data = await _api.ping('consensus');
    if (!mounted) return;
    setState(() {
      _sessions = List<Map<String, dynamic>>.from(data['sessions'] ?? data['data']?['sessions'] ?? const []);
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(backgroundColor: Colors.black, title: Text('consensus.title'.tr(), style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, letterSpacing: 1.5, color: Colors.white))),
      body: _loading ? const Center(child: CircularProgressIndicator(color: Colors.blueAccent)) : ListView(
        padding: const EdgeInsets.all(16.0),
        children: [
          Text('consensus.ongoing_sessions'.tr().toUpperCase(), style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w900, letterSpacing: 2, color: Colors.white54)),
          const SizedBox(height: 16),
          if (_sessions.isEmpty) Center(child: Text('No active consensus sessions.'.tr(), style: const TextStyle(color: Colors.white38))),
          ..._sessions.map((session) => _buildSessionCard(session)),
        ],
      ),
    );
  }

  Widget _buildSessionCard(Map<String, dynamic> session) {
    final title = session['title']?.toString() ?? session['topic']?.toString() ?? 'Consensus Session';
    final subtitle = session['summary']?.toString() ?? session['status']?.toString() ?? 'Pending';
    final isFinalized = session['status']?.toString().toUpperCase() == 'FINALIZED' || session['finalized'] == true;
    final color = isFinalized ? Colors.greenAccent : Colors.orangeAccent;
    final icon = isFinalized ? Icons.psychology : Icons.how_to_vote;

    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.03), borderRadius: BorderRadius.circular(20), border: Border.all(color: Colors.white10)),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: BackdropFilter(filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10), child: Padding(
          padding: const EdgeInsets.all(20),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Container(padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: color.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(16)), child: Icon(icon, color: color, size: 28)),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: const TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 6),
                    Text(subtitle, style: TextStyle(color: isFinalized ? Colors.white70 : color, fontSize: 13, fontWeight: isFinalized ? FontWeight.normal : FontWeight.w600)),
                  ],
                ),
              ),
              if (!isFinalized) const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.orangeAccent))
              else Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(color: color.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(8), border: Border.all(color: color.withValues(alpha: 0.3))),
                child: Text('consensus.finalized'.tr().toUpperCase(), style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.bold)),
              ),
            ],
          ),
        )),
      ),
    );
  }
}
