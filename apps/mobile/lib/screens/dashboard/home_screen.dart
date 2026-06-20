import 'package:flutter/material.dart';
import 'dart:ui';
import 'package:provider/provider.dart';
import '../../providers/orchestration_provider.dart';
import '../../providers/auth_provider.dart';
import '../settings_screen.dart';
import '../learning/learning_screen.dart';
import '../projects/projects_list_screen.dart';
import '../notifications/notifications_screen.dart';
import '../../services/localization_service.dart';

import '../../providers/settings_provider.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _currentIndex = 0;
  final List<ChatMessage> _messages = [];
  final TextEditingController _chatController = TextEditingController();

  void _sendMessage() async {
    if (_chatController.text.trim().isEmpty) return;

    final userMessage = _chatController.text.trim();
    setState(() {
      _messages.add(ChatMessage(
        text: userMessage,
        isUser: true,
        timestamp: DateTime.now(),
      ));
    });
    _chatController.clear();

    final orchestration = context.read<OrchestrationProvider>();
    final auth = context.read<AuthProvider>();
    final settings = context.read<SettingsProvider>().settings;

    await orchestration.orchestrateRequirement(
      userMessage,
      auth.token ?? 'GUEST_MODE',
      activeModel: settings.model,
    );

    if (orchestration.lastResult != null && mounted) {
      setState(() {
        final result = orchestration.lastResult!;
        final status = result['status']?.toString().toUpperCase() ?? 'UNKNOWN';
        final answer = (result['answer'] ?? result['message'] ?? 'Requirement analyzed.');
        final sources = (result['sources'] as List<dynamic>?)?.cast<String>() ?? const <String>[];
        final hasAction = status == 'DECIDED' || status == 'COMPLETED';

        _messages.add(ChatMessage(
          text: answer,
          isUser: false,
          timestamp: DateTime.now(),
          hasAction: hasAction,
          result: result,
          sources: sources,
        ));
      });
    }
  }

  void _generateProject() {
    final auth = context.read<AuthProvider>();
    final orchestration = context.read<OrchestrationProvider>();
    orchestration.generateProject(auth.token ?? 'GUEST_MODE');
  }

  @override
  void dispose() {
    _chatController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        elevation: 0,
        title: Text('SupremeAI'.tr(), style: const TextStyle(fontWeight: FontWeight.w900, letterSpacing: 1.5, color: Colors.white)),
        actions: [
          IconButton(
            icon: Icon(context.watch<AuthProvider>().isGuest ? Icons.login : Icons.logout, color: Colors.white70),
            onPressed: () => context.read<AuthProvider>().logout(),
          ),
        ],
      ),
      body: IndexedStack(
        index: _currentIndex,
        children: [
          _buildChatTab(),
          const LearningScreen(),
          const ProjectsListScreen(),
          const NotificationsScreen(),
          const SettingsScreen(),
        ],
      ),
      bottomNavigationBar: _buildBottomNav(),
    );
  }

  Widget _buildBottomNav() {
    return Container(
      decoration: BoxDecoration(
        border: Border(top: BorderSide(color: Colors.white.withValues(alpha: 0.05))),
      ),
      child: NavigationBarTheme(
        data: NavigationBarThemeData(
          indicatorColor: Colors.blueAccent.withValues(alpha: 0.1),
          labelTextStyle: WidgetStateProperty.all(
            const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: Colors.white70),
          ),
        ),
        child: NavigationBar(
          backgroundColor: Colors.black,
          selectedIndex: _currentIndex,
          onDestinationSelected: (index) => setState(() => _currentIndex = index),
          destinations: [
            NavigationDestination(icon: const Icon(Icons.chat_bubble_outline, color: Colors.white54), selectedIcon: const Icon(Icons.chat_bubble, color: Colors.blueAccent), label: 'Chat'.tr()),
            NavigationDestination(icon: const Icon(Icons.psychology_outlined, color: Colors.white54), selectedIcon: const Icon(Icons.psychology, color: Colors.blueAccent), label: 'Skills'.tr()),
            NavigationDestination(icon: const Icon(Icons.hub_outlined, color: Colors.white54), selectedIcon: const Icon(Icons.hub, color: Colors.blueAccent), label: 'Automation'.tr()),
            NavigationDestination(icon: const Icon(Icons.lightbulb_outline, color: Colors.white54), selectedIcon: const Icon(Icons.lightbulb, color: Colors.blueAccent), label: 'Insights'.tr()),
            NavigationDestination(icon: const Icon(Icons.settings_outlined, color: Colors.white54), selectedIcon: const Icon(Icons.settings, color: Colors.blueAccent), label: 'Settings'.tr()),
          ],
        ),
      ),
    );
  }

  Widget _buildChatTab() {
    final orchestration = context.watch<OrchestrationProvider>();
    final auth = context.watch<AuthProvider>();
    
    return Column(
      children: [
        if (auth.isGuest) _buildGuestWarning(),
        Expanded(
          child: _messages.isEmpty
              ? _buildEmptyState()
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: _messages.length,
                  itemBuilder: (context, index) => _buildMessage(_messages[index]),
                ),
        ),
        if (orchestration.isLoading) const LinearProgressIndicator(backgroundColor: Colors.transparent, color: Colors.blueAccent),
        if (orchestration.error != null) _buildErrorBanner(orchestration.error!.message),
        _buildInputArea(orchestration),
      ],
    );
  }

  Widget _buildGuestWarning() {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 16),
      color: Colors.amber.withValues(alpha: 0.05),
      child: Row(
        children: [
          const Icon(Icons.info_outline, size: 16, color: Colors.amberAccent),
          const SizedBox(width: 12),
          Expanded(child: Text('Guest Mode: Limited quota. Login to increase limits.'.tr(), style: const TextStyle(fontSize: 11, color: Colors.amberAccent, fontWeight: FontWeight.bold))),
        ],
      ),
    );
  }

  Widget _buildMessage(ChatMessage message) {
    final isUser = message.isUser;
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 16),
        padding: const EdgeInsets.all(16),
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.8),
        decoration: BoxDecoration(
          color: isUser ? Colors.blueAccent.withValues(alpha: 0.1) : Colors.white.withValues(alpha: 0.03),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: isUser ? Colors.blueAccent.withValues(alpha: 0.2) : Colors.white10),
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(20),
          child: BackdropFilter(
            filter: ImageFilter.blur(sigmaX: 5, sigmaY: 5),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(message.text, style: const TextStyle(color: Colors.white, fontSize: 15, height: 1.4)),
                if (message.hasAction) ...[
                  const SizedBox(height: 16),
                  ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.blueAccent,
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    onPressed: _generateProject,
                    icon: const Icon(Icons.rocket_launch, size: 18),
                    label: Text('Generate Project'.tr()),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.auto_awesome, size: 64, color: Colors.blueAccent.withValues(alpha: 0.3)),
          const SizedBox(height: 24),
          Text('Describe what you want to build...'.tr(), style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Text('AI will analyze and generate your project automatically.'.tr(), textAlign: TextAlign.center, style: const TextStyle(color: Colors.white38, fontSize: 13)),
        ],
      ),
    );
  }

  Widget _buildErrorBanner(String error) {
    return Container(
      padding: const EdgeInsets.all(12),
      margin: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: Colors.redAccent.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(12), border: Border.all(color: Colors.redAccent.withValues(alpha: 0.2))),
      child: Row(
        children: [
          const Icon(Icons.error_outline, color: Colors.redAccent, size: 20),
          const SizedBox(width: 12),
          Expanded(child: Text(error, style: const TextStyle(color: Colors.redAccent, fontSize: 12))),
          IconButton(onPressed: () => context.read<OrchestrationProvider>().clearError(), icon: const Icon(Icons.close, size: 16, color: Colors.redAccent)),
        ],
      ),
    );
  }

  Widget _buildInputArea(OrchestrationProvider orchestration) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.black,
        border: Border(top: BorderSide(color: Colors.white.withValues(alpha: 0.05))),
      ),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _chatController,
              style: const TextStyle(color: Colors.white),
              decoration: InputDecoration(
                hintText: 'Enter your requirement...'.tr(),
                hintStyle: const TextStyle(color: Colors.white24),
                filled: true,
                fillColor: Colors.white.withValues(alpha: 0.03),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide.none),
                contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
              ),
              onSubmitted: (_) => _sendMessage(),
            ),
          ),
          const SizedBox(width: 12),
          Container(
            decoration: BoxDecoration(color: Colors.blueAccent, borderRadius: BorderRadius.circular(16)),
            child: IconButton(
              onPressed: orchestration.isLoading ? null : _sendMessage,
              icon: const Icon(Icons.send, color: Colors.white),
            ),
          ),
        ],
      ),
    );
  }
}

class ChatMessage {
  final String text;
  final bool isUser;
  final DateTime timestamp;
  final bool hasAction;
  final Map<String, dynamic>? result;
  final List<String> sources;

  ChatMessage({
    required this.text,
    required this.isUser,
    required this.timestamp,
    this.hasAction = false,
    this.result,
    this.sources = const <String>[],
  });
}