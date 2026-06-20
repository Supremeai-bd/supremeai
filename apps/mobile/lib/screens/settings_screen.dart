import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../providers/settings_provider.dart';
import '../../services/localization_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _modelController = TextEditingController();
  final _smallModelController = TextEditingController();
  bool _fullAuthority = false;
  bool _externalDirectory = false;
  String _shareMode = 'manual';
  String _themeMode = 'dark';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      final auth = context.read<AuthProvider>();
      final settingsProvider = context.read<SettingsProvider>();
      await settingsProvider.loadFromBackend(authToken: auth.token);
      _bind(settingsProvider.settings);
    });
  }

  void _bind(SupremeAISettings settings) {
    _modelController.text = settings.model;
    _smallModelController.text = settings.smallModel;
    _fullAuthority = settings.fullAuthority;
    _externalDirectory = settings.enableExternalDirectory;
    _shareMode = settings.shareMode;
    _themeMode = settings.themeMode;
  }

  @override
  void dispose() {
    _modelController.dispose();
    _smallModelController.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final auth = context.read<AuthProvider>();
    final provider = context.read<SettingsProvider>();
    final current = provider.settings;

    provider.update(current.copyWith(
      model: _modelController.text.trim(),
      smallModel: _smallModelController.text.trim(),
      fullAuthority: _fullAuthority,
      shareMode: _shareMode,
      enableExternalDirectory: _externalDirectory,
      themeMode: _themeMode,
    ));

    if (_fullAuthority) provider.setFullAuthority(true);
    final ok = await provider.saveToBackend(authToken: auth.token);
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      backgroundColor: ok ? Colors.greenAccent : Colors.redAccent,
      content: Text(ok ? 'Settings saved'.tr() : 'Save failed'.tr(), style: const TextStyle(color: Colors.black, fontWeight: FontWeight.bold)),
    ));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        elevation: 0,
        title: Text('settings.title'.tr(), style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, letterSpacing: 1.5, color: Colors.white)),
      ),
      body: Consumer<SettingsProvider>(
        builder: (context, settingsProvider, _) {
          if (settingsProvider.isLoading && settingsProvider.settings.model.isEmpty) {
            return const Center(child: CircularProgressIndicator(color: Colors.blueAccent));
          }

          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              _buildSection('AI Models'.tr(), [
                _buildTextField(_modelController, 'Primary model', 'gemini-1.5-pro'),
                const SizedBox(height: 16),
                _buildTextField(_smallModelController, 'Small model', 'gemini-1.5-flash'),
              ]),
              const SizedBox(height: 24),
              _buildSection('App Settings'.tr(), [
                _buildDropdown('Share mode', _shareMode, ['manual', 'auto', 'disabled'], (v) => setState(() => _shareMode = v!)),
                const SizedBox(height: 16),
                _buildSwitchTile('Full authority mode', 'Allow all core tools without confirmation', _fullAuthority, (v) => setState(() => _fullAuthority = v)),
                _buildSwitchTile('External directory access', 'Access directories outside workspace', _externalDirectory, (v) => setState(() => _externalDirectory = v)),
                const SizedBox(height: 16),
                _buildDropdown('Theme', _themeMode, ['system', 'light', 'dark'], (v) => setState(() => _themeMode = v!)),
              ]),
              if (settingsProvider.error != null) ...[
                const SizedBox(height: 16),
                Text(settingsProvider.error!, style: const TextStyle(color: Colors.redAccent, fontSize: 12)),
              ],
              const SizedBox(height: 32),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.blueAccent,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  ),
                  onPressed: settingsProvider.isLoading ? null : _save,
                  icon: const Icon(Icons.save),
                  label: Text(settingsProvider.isLoading ? 'Saving...'.tr() : 'settings.save_changes'.tr()),
                ),
              ),
            ],
          );
        },
      ),
    );
  }

  Widget _buildSection(String title, List<Widget> children) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.03),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title.toUpperCase(), style: const TextStyle(color: Colors.white54, fontSize: 12, fontWeight: FontWeight.w900, letterSpacing: 2)),
          const SizedBox(height: 20),
          ...children,
        ],
      ),
    );
  }

  Widget _buildTextField(TextEditingController controller, String label, String hint) {
    return TextField(
      controller: controller,
      style: const TextStyle(color: Colors.white),
      decoration: InputDecoration(
        labelText: label,
        labelStyle: const TextStyle(color: Colors.white38),
        hintText: hint,
        hintStyle: const TextStyle(color: Colors.white12),
        filled: true,
        fillColor: Colors.black,
        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: Colors.white10)),
        focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: Colors.blueAccent)),
      ),
    );
  }

  Widget _buildDropdown(String label, String value, List<String> items, ValueChanged<String?> onChanged) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(color: Colors.white70, fontSize: 13, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          decoration: BoxDecoration(
            color: Colors.black,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: Colors.white10),
          ),
          child: DropdownButtonHideUnderline(
            child: DropdownButton<String>(
              value: value,
              dropdownColor: Colors.black,
              style: const TextStyle(color: Colors.white),
              isExpanded: true,
              items: items.map((e) => DropdownMenuItem(value: e, child: Text(e))).toList(),
              onChanged: onChanged,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildSwitchTile(String title, String subtitle, bool value, ValueChanged<bool> onChanged) {
    return SwitchListTile(
      contentPadding: EdgeInsets.zero,
      title: Text(title, style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.bold)),
      subtitle: Text(subtitle, style: const TextStyle(color: Colors.white38, fontSize: 11)),
      value: value,
      activeThumbColor: Colors.blueAccent,
      onChanged: onChanged,
    );
  }
}