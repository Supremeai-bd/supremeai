#!/usr/bin/env dart
// Script to fix URI encoding issues in Flutter build
// Addresses: FileSystemException(uri=org-dartlang-untranslatable-uri:package%3Asupreme_ai%2Fscreens%2Fchat_screen.dart; message=StandardFileSystem only supports file:* and data:* URIs)

import 'dart:io';
import 'dart:convert';

Future<void> main() async {
  print('🔧 SupremeAI Mobile - URI Encoding Fix Script');
  print('===============================================');
  
  final projectDir = Directory('apps/mobile');
  if (!await projectDir.exists()) {
    print('❌ Mobile app directory not found at apps/mobile');
    return;
  }

  print('📁 Changing to mobile directory...');
  Directory.current = projectDir.path;

  print('\n🔍 Analyzing project structure...');
  await _analyzeProjectStructure();

  print('\n🔍 Checking import statements for encoding issues...');
  await _checkImportStatements();

  print('\n🔧 Fixing potential URI encoding issues...');
  await _fixUriIssues();

  print('\n🔄 Refreshing dependencies...');
  await _runCommand('flutter pub get');

  print('\n✅ URI encoding fix process completed!');
  print('\n🚀 Try building again with:');
  print('   flutter build apk --release');
}

Future<void> _analyzeProjectStructure() async {
  final libDir = Directory('lib');
  if (await libDir.exists()) {
    print('   Found lib directory, scanning for files...');
    await for (final entity in libDir.list(recursive: true)) {
      if (entity is File && entity.path.endsWith('.dart')) {
        // Count the file but don't process yet
      }
    }
  }
}

Future<void> _checkImportStatements() async {
  final libDir = Directory('lib');
  if (await libDir.exists()) {
    await for (final entity in libDir.list(recursive: true)) {
      if (entity is File && entity.path.endsWith('.dart')) {
        try {
          final content = await entity.readAsString();
          
          // Look for any incorrectly encoded URIs
          if (content.contains('%3A') || content.contains('%2F')) {
            print('⚠️  Found encoded URI in ${entity.path}');
            print('   This may be causing the build error');
          }
          
          // Look for any incorrect package name references
          if (content.contains('supreme_ai') && !content.contains('supremeai_mobile')) {
            print('⚠️  Found potential incorrect package reference in ${entity.path}');
          }
        } catch (e) {
          print('⚠️  Could not read file ${entity.path}: $e');
        }
      }
    }
  }
}

Future<void> _fixUriIssues() async {
  print('   📝 Ensuring correct package name in all files...');
  
  final libDir = Directory('lib');
  if (await libDir.exists()) {
    await for (final entity in libDir.list(recursive: true)) {
      if (entity is File && entity.path.endsWith('.dart')) {
        try {
          String content = await entity.readAsString();
          
          // Fix any incorrectly encoded URIs
          content = content.replaceAll('%3A', ':');
          content = content.replaceAll('%2F', '/');
          
          // Ensure correct package name is used
          content = content.replaceAll(
            RegExp(r'package:supreme_ai/'), 
            'package:supremeai_mobile/'
          );
          
          // Write back the fixed content
          await entity.writeAsString(content);
        } catch (e) {
          print('⚠️  Could not fix file ${entity.path}: $e');
        }
      }
    }
  }
  
  // Also check the pubspec.yaml
  final pubspecFile = File('pubspec.yaml');
  if (await pubspecFile.exists()) {
    String content = await pubspecFile.readAsString();
    
    // Make sure the name field is properly formatted
    if (!content.contains('name: supremeai_mobile')) {
      print('⚠️  Package name may need verification in pubspec.yaml');
    }
  }
  
  print('   ✅ Applied URI encoding fixes');
}

Future<void> _runCommand(String command) async {
  print('   Executing: $command');
  final process = await Process.start(
    command.split(' ')[0], 
    command.split(' ').skip(1).toList(),
    runInShell: true,
    workingDirectory: Directory.current.path
  );
  
  final stdout = await process.stdout.transform(utf8.decoder).join();
  final stderr = await process.stderr.transform(utf8.decoder).join();
  final exitCode = await process.exitCode;
  
  if (exitCode != 0) {
    print('⚠️  Command failed with exit code $exitCode');
    if (stderr.isNotEmpty) {
      print('   stderr: $stderr');
    }
  } else {
    print('   ✅ Command succeeded');
  }
}