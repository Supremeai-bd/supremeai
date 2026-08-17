import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

class CodeEditorScreen extends StatefulWidget {
  const CodeEditorScreen({super.key});

  @override
  _CodeEditorScreenState createState() => _CodeEditorScreenState();
}

class _CodeEditorScreenState extends State<CodeEditorScreen> {
  final TextEditingController _codeController = TextEditingController();
  String _selectedLanguage = 'Dart';
  final bool _isEditing = false;

  @override
  void initState() {
    super.initState();
    _codeController.text = '''void main() {
  print('Hello, SupremeAI!');
  
  // Sample function to demonstrate code editing
  int calculateSum(int a, int b) {
    return a + b;
  }
  
  int result = calculateSum(5, 3);
  print('Result: \$result');
}''';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: const Color(0xFF2563EB),
        foregroundColor: Colors.white,
        title: const Text('Code Editor'),
        centerTitle: true,
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.copy),
            onPressed: () {
              Clipboard.setData(ClipboardData(text: _codeController.text));
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Code copied to clipboard')),
              );
            },
          ),
          PopupMenuButton<String>(
            onSelected: (String result) {
              if (result == 'format') {
                // Format code
              } else if (result == 'analyze') {
                // Analyze code
              } else if (result == 'ai_help') {
                // Get AI help
              }
            },
            itemBuilder: (BuildContext context) => [
              const PopupMenuItem<String>(
                value: 'format',
                child: ListTile(
                  leading: Icon(Icons.format_align_left),
                  title: Text('Format Code'),
                ),
              ),
              const PopupMenuItem<String>(
                value: 'analyze',
                child: ListTile(
                  leading: Icon(Icons.analytics),
                  title: Text('Analyze Code'),
                ),
              ),
              const PopupMenuItem<String>(
                value: 'ai_help',
                child: ListTile(
                  leading: Icon(Icons.smart_toy),
                  title: Text('AI Help'),
                ),
              ),
            ],
          ),
        ],
      ),
      body: Column(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            color: const Color(0xFF0F172A),
            child: Row(
              children: [
                const Text(
                  'main.dart',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 14,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                const Spacer(),
                DropdownButton<String>(
                  value: _selectedLanguage,
                  underline: Container(),
                  dropdownColor: const Color(0xFF1E293B),
                  iconEnabledColor: Colors.white,
                  items: <String>['Dart', 'JavaScript', 'Python', 'Java', 'C++']
                      .map<DropdownMenuItem<String>>((String value) {
                    return DropdownMenuItem<String>(
                      value: value,
                      child: Text(
                        value,
                        style: const TextStyle(color: Colors.white),
                      ),
                    );
                  }).toList(),
                  onChanged: (String? newValue) {
                    setState(() {
                      _selectedLanguage = newValue!;
                    });
                  },
                ),
              ],
            ),
          ),
          Expanded(
            child: Container(
              color: const Color(0xFF1E293B),
              child: SingleChildScrollView(
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: TextField(
                    controller: _codeController,
                    maxLines: null,
                    expands: true,
                    keyboardType: TextInputType.multiline,
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 14,
                      color: Colors.white,
                    ),
                    decoration: const InputDecoration(
                      border: InputBorder.none,
                      contentPadding: EdgeInsets.zero,
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () {
          // Simulate running code
          showDialog(
            context: context,
            builder: (BuildContext context) {
              return AlertDialog(
                title: const Text('Run Code'),
                content: const Text('In the full implementation, this would run the code in a secure sandbox.'),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.of(context).pop(),
                    child: const Text('OK'),
                  ),
                ],
              );
            },
          );
        },
        label: const Text('Run'),
        icon: const Icon(Icons.play_arrow),
        backgroundColor: const Color(0xFF10B981),
      ),
    );
  }
}