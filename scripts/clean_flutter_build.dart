#!/usr/bin/env dart
// Script to clean Flutter build artifacts and fix common build issues
// Addresses the FileSystemException with URI encoding issues

import 'dart:io';
import 'dart:convert';

Future<void> main() async {
  print('🔧 SupremeAI Mobile - Flutter Build Cleanup Script');
  print('==================================================');
  
  final projectDir = Directory('apps/mobile');
  if (!await projectDir.exists()) {
    print('❌ Mobile app directory not found at apps/mobile');
    return;
  }

  print('📁 Changing to mobile directory...');
  Directory.current = projectDir.path;

  print('\n🧹 Cleaning build artifacts...');
  await _runCommand('flutter clean');
  
  print('\n🗑️  Removing .dart_tool directory...');
  final dartToolDir = Directory('.dart_tool');
  if (await dartToolDir.exists()) {
    await dartToolDir.delete(recursive: true);
    print('✅ Removed .dart_tool directory');
  }

  print('\n🗑️  Removing build directory...');
  final buildDir = Directory('build');
  if (await buildDir.exists()) {
    await buildDir.delete(recursive: true);
    print('✅ Removed build directory');
  }

  print('\n🔄 Getting fresh dependencies...');
  await _runCommand('flutter pub get');
  
  print('\n🔄 Upgrading dependencies...');
  await _runCommand('flutter pub upgrade');

  print('\n🔍 Checking for problematic files...');
  await _checkForSpecialCharacters();

  print('\n📝 Updating pubspec.yaml to ensure correct format...');
  await _fixPubspecFormat();

  print('\n✅ Cleanup process completed!');
  print('\n🚀 You can now try building again:');
  print('   flutter build apk --release');
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

Future<void> _checkForSpecialCharacters() async {
  print('   🔍 Scanning for special characters in file paths...');
  
  final libDir = Directory('lib');
  if (await libDir.exists()) {
    await for (final entity in libDir.list(recursive: true)) {
      if (entity.path.contains('#') || 
          entity.path.contains('%') || 
          entity.path.contains('+') ||
          entity.path.contains(' ')) {
        print('⚠️  Found potentially problematic file: ${entity.path}');
      }
    }
  }
}

Future<void> _fixPubspecFormat() async {
  final pubspecFile = File('pubspec.yaml');
  if (!await pubspecFile.exists()) {
    print('   ⚠️  pubspec.yaml not found');
    return;
  }
  
  String content = await pubspecFile.readAsString();
  
  // Ensure proper formatting
  content = content.replaceAll('\t', '  '); // Replace tabs with spaces
  
  // Write back the corrected content
  await pubspecFile.writeAsString(content);
  print('   ✅ Fixed pubspec.yaml formatting');
  
  // Also make sure to run pub get again after fixing formatting
  await _runCommand('flutter pub get');
}