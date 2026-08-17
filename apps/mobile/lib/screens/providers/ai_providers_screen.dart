import 'package:flutter/material.dart';
import 'dart:ui';
import '../../services/localization_service.dart';
import '../../services/api_service.dart';

class AiProvidersScreen extends StatelessWidget {
  const AiProvidersScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final apiService = ApiService();

    final defaultProviders = [
      {'name': 'OpenAI', 'status': 'providers.online'.tr(), 'model': 'gpt-4o-mini', 'color': Colors.greenAccent},
      {'name': 'SupremeAI Light', 'status': 'providers.online'.tr(), 'model': 'supremeai-1.5-flash', 'color': Colors.greenAccent},
      {'name': 'Anthropic', 'status': 'providers.online'.tr(), 'model': 'claude-3-5-haiku', 'color': Colors.greenAccent},
      {'name': 'Groq', 'status': 'providers.online'.tr(), 'model': 'llama3-8b-8192', 'color': Colors.greenAccent},
    ];

    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        title: Text('providers.title'.tr(),
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, letterSpacing: 1.5, color: Colors.white)
        ),
      ),
      body: FutureBuilder<List<Map<String, dynamic>>>(
        future: apiService.getConfiguredProviders(),
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator(color: Colors.blueAccent));
          }

          final fetchedList = snapshot.data ?? [];
          final displayProviders = fetchedList.isEmpty ? defaultProviders : fetchedList.map((p) {
            final active = p['status']?.toString().toLowerCase() == 'active' || p['status']?.toString().toLowerCase() == 'online';
            return {
              'name': p['name']?.toString() ?? 'Unknown',
              'status': active ? 'providers.online'.tr() : 'providers.offline'.tr(),
              'model': p['model']?.toString() ?? p['activeModel']?.toString() ?? 'Dynamic',
              'color': active ? Colors.greenAccent : Colors.redAccent,
            };
          }).toList();

          return ListView.builder(
            padding: const EdgeInsets.all(16.0),
            itemCount: displayProviders.length,
            itemBuilder: (context, index) {
              final p = displayProviders[index];
              return _buildProviderCard(
                context,
                p['name'] as String,
                p['model'] as String,
                p['status'] as String,
                p['color'] as Color,
              );
            },
          );
        }
      ),
    );
  }

  Widget _buildProviderCard(BuildContext context, String name, String model, String status, Color color) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.03),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.white10),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Icon(Icons.cloud_done_rounded, color: color, size: 28),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(name, style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 6),
                      Text('${'providers.model'.tr()}: $model', style: const TextStyle(color: Colors.white54, fontSize: 13, fontWeight: FontWeight.w600)),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: color.withValues(alpha: 0.3)),
                  ),
                  child: Text(status.toUpperCase(), style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.bold)),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
