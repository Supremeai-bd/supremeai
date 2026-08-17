import 'dart:convert';
import 'package:flutter/material.dart';

class JsonDropzone extends StatefulWidget {
  final Function(Map<String, dynamic> jsonContent) onFileLoaded;

  const JsonDropzone({super.key, required this.onFileLoaded});

  @override
  State<JsonDropzone> createState() => _JsonDropzoneState();
}

class _JsonDropzoneState extends State<JsonDropzone> {
  String? _statusText;
  final bool _isHovering = false;

  // Zero-Trust: Handle files directly in memory (RAM).
  // Device caches are completely bypassed for absolute credential isolation.
  // বাংলা মন্তব্য: জিরো-ট্রাস্ট হ্যান্ডলিং - ক্রেডেনশিয়াল ফোল্ডার বা লোকাল স্টোরেজে ক্যাশ না করে র‍্যামে রিড করা হচ্ছে।
  void _handleTextInput(String rawText) {
    try {
      final parsedJson = jsonDecode(rawText);
      if (parsedJson is Map<String, dynamic>) {
        if (parsedJson.containsKey('project_id') && parsedJson.containsKey('private_key')) {
          widget.onFileLoaded(parsedJson);
          setState(() {
            _statusText = "GCP Service Account JSON validated successfully.";
          });
        } else {
          setState(() {
            _statusText = "Error: Invalid GCP service account structure.";
          });
        }
      } else {
        setState(() {
          _statusText = "Error: JSON must be a key-value object.";
        });
      }
    } catch (e) {
      setState(() {
        _statusText = "Error: Failed to parse JSON text.";
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        GestureDetector(
          onTap: () {
            // Dropzone simulating selection text area popup for mobile compatibility
            _showPasteDialog(context);
          },
          child: Container(
            height: 180,
            decoration: BoxDecoration(
              color: _isHovering ? theme.colorScheme.primary.withValues(alpha: 0.08) : theme.colorScheme.surface,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: _isHovering ? theme.colorScheme.primary : theme.colorScheme.outline.withValues(alpha: 0.5),
                width: 2,
              ),
            ),
            child: Center(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      Icons.cloud_upload_outlined,
                      size: 48,
                      color: theme.colorScheme.primary,
                    ),
                    const SizedBox(height: 12),
                    Text(
                      "Upload Service Account JSON",
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      "Tap here to paste GCP Service Account JSON contents",
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
        if (_statusText != null) ...[
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: _statusText!.startsWith("Error")
                  ? theme.colorScheme.error.withValues(alpha: 0.1)
                  : theme.colorScheme.primary.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              _statusText!,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: _statusText!.startsWith("Error") ? theme.colorScheme.error : theme.colorScheme.primary,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ],
    );
  }

  void _showPasteDialog(BuildContext context) {
    final textController = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text("Paste Service Account JSON"),
        content: TextField(
          controller: textController,
          maxLines: 8,
          decoration: const InputDecoration(
            hintText: '{\n  "type": "service_account",\n  "project_id": "...",\n  "private_key": "..."\n}',
            border: OutlineInputBorder(),
          ),
          style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text("Cancel"),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(ctx);
              _handleTextInput(textController.text);
            },
            child: const Text("Validate"),
          ),
        ],
      ),
    );
  }
}
