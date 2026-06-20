import 'package:flutter/material.dart';
import 'dart:ui';
import '../../services/localization_service.dart';

class ProjectsListScreen extends StatefulWidget {
  const ProjectsListScreen({super.key});

  @override
  State<ProjectsListScreen> createState() => _ProjectsListScreenState();
}

class _ProjectsListScreenState extends State<ProjectsListScreen> {
  String _selectedTask = 'REVERSE_ENGINEER';
  final TextEditingController _urlController = TextEditingController();
  final TextEditingController _instructionController = TextEditingController();

  final List<Map<String, String>> _taskTypes = [
    {'id': 'REVERSE_ENGINEER', 'key': 'projects.reverse_engineer', 'icon': '🔎'},
    {'id': 'DATA_EXTRACTION', 'key': 'projects.data_extraction', 'icon': '📊'},
    {'id': 'AUTOMATION', 'key': 'projects.automation', 'icon': '🤖'},
    {'id': 'SECURITY_AUDIT', 'key': 'projects.security_audit', 'icon': '🛡️'},
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      extendBodyBehindAppBar: true,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        flexibleSpace: ClipRect(
          child: BackdropFilter(
            filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
            child: Container(color: Colors.black.withValues(alpha: 0.5)),
          ),
        ),
        title: Text('projects.title'.tr().toUpperCase(), 
          style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w900, letterSpacing: 2, color: Colors.white)
        ),
      ),
      body: Container(
        decoration: BoxDecoration(
          gradient: RadialGradient(
            center: Alignment.topLeft,
            radius: 1.5,
            colors: [Colors.blueAccent.withValues(alpha: 0.1), Colors.black],
          ),
        ),
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 120, 20, 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildSectionHeader('projects.target_website'),
              const SizedBox(height: 12),
              _buildGlassInput(
                controller: _urlController,
                hint: 'projects.hint_url'.tr(),
                icon: Icons.language,
              ),
              const SizedBox(height: 24),
              _buildSectionHeader('projects.neural_task'),
              const SizedBox(height: 12),
              GridView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 2,
                  crossAxisSpacing: 12,
                  mainAxisSpacing: 12,
                  childAspectRatio: 2.2,
                ),
                itemCount: _taskTypes.length,
                itemBuilder: (context, index) {
                  final task = _taskTypes[index];
                  final isSelected = _selectedTask == task['id'];
                  return GestureDetector(
                    onTap: () => setState(() => _selectedTask = task['id']!),
                    child: _buildGlassCard(
                      isSelected: isSelected,
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const SizedBox(width: 12),
                          Text(task['icon']!, style: const TextStyle(fontSize: 18)),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(task['key']!.tr(), 
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(
                                color: isSelected ? Colors.white : Colors.white60,
                                fontWeight: isSelected ? FontWeight.w900 : FontWeight.bold,
                                fontSize: 11,
                              )
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                },
              ),
              const SizedBox(height: 24),
              _buildSectionHeader('projects.instructions'),
              const SizedBox(height: 12),
              _buildGlassInput(
                controller: _instructionController,
                hint: 'projects.hint_instructions'.tr(),
                icon: Icons.psychology_alt,
                maxLines: 4,
              ),
              const SizedBox(height: 32),
              _buildPrimaryButton(),
              const SizedBox(height: 40),
              _buildSectionHeader('projects.suggestions'),
              const SizedBox(height: 12),
              _buildSuggestionCard(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSectionHeader(String key) {
    return Text(
      key.tr().toUpperCase(),
      style: const TextStyle(
        color: Colors.white38,
        fontSize: 10,
        fontWeight: FontWeight.bold,
        letterSpacing: 1.5,
      ),
    );
  }

  Widget _buildGlassCard({required Widget child, bool isSelected = false}) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(20),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
        child: Container(
          decoration: BoxDecoration(
            color: isSelected 
              ? Colors.blueAccent.withValues(alpha: 0.15) 
              : Colors.white.withValues(alpha: 0.05),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: isSelected 
                ? Colors.blueAccent.withValues(alpha: 0.5) 
                : Colors.white.withValues(alpha: 0.1),
              width: 1.5,
            ),
          ),
          child: child,
        ),
      ),
    );
  }

  Widget _buildGlassInput({
    required TextEditingController controller,
    required String hint,
    required IconData icon,
    int maxLines = 1,
  }) {
    return _buildGlassCard(
      child: TextField(
        controller: controller,
        maxLines: maxLines,
        style: const TextStyle(color: Colors.white, fontSize: 14),
        decoration: InputDecoration(
          hintText: hint,
          hintStyle: const TextStyle(color: Colors.white24, fontSize: 14),
          prefixIcon: Icon(icon, color: Colors.white24, size: 20),
          border: InputBorder.none,
          contentPadding: const EdgeInsets.all(16),
        ),
      ),
    );
  }

  Widget _buildPrimaryButton() {
    return Container(
      width: double.infinity,
      height: 60,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        gradient: const LinearGradient(
          colors: [Colors.blueAccent, Colors.indigoAccent],
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.blueAccent.withValues(alpha: 0.3),
            blurRadius: 20,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: ElevatedButton(
        onPressed: () {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('projects.initiating'.tr()),
              backgroundColor: Colors.blueAccent,
            )
          );
        },
        style: ElevatedButton.styleFrom(
          backgroundColor: Colors.transparent,
          shadowColor: Colors.transparent,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        ),
        child: Text('projects.initiate'.tr().toUpperCase(), 
          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w900, letterSpacing: 1.5)
        ),
      ),
    );
  }

  Widget _buildSuggestionCard() {
    return _buildGlassCard(
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [Colors.amber.withValues(alpha: 0.1), Colors.transparent],
          ),
        ),
        child: Row(
          children: [
            const Icon(Icons.lightbulb, color: Colors.amber, size: 24),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('projects.alternative'.tr().toUpperCase(), 
                    style: const TextStyle(color: Colors.amber, fontSize: 10, fontWeight: FontWeight.bold)
                  ),
                  const SizedBox(height: 4),
                  Text('projects.suggestion_desc'.tr(), 
                    style: const TextStyle(color: Colors.white70, fontSize: 11)
                  ),
                ],
              ),
            ),
            TextButton(
              onPressed: () {},
              child: Text('projects.use'.tr().toUpperCase(), style: const TextStyle(color: Colors.amber, fontWeight: FontWeight.bold, fontSize: 11)),
            ),
          ],
        ),
      ),
    );
  }
}

