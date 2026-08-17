#!/usr/bin/env dart
// Script to fix package name inconsistencies that cause build failures
// Addresses the issue where 'supremeai_mobile' gets incorrectly processed as 'supreme_ai'

import 'dart:io';
import 'dart:convert';

Future<void> main() async {
  print('🔧 SupremeAI Mobile - Package Name Fix Script');
  print('==============================================');

  final projectDir = Directory('apps/mobile');
  if (!await projectDir.exists()) {
    print('❌ Mobile app directory not found at apps/mobile');
    return;
  }

  print('📁 Changing to mobile directory...');
  Directory.current = projectDir.path;

  print('\n🔍 Verifying package name in pubspec.yaml...');
  await _verifyPackageName();

  print('\n🔍 Checking all Dart imports...');
  await _checkAllImports();

  print('\n🧹 Cleaning potential build artifacts...');
  await _cleanBuildArtifacts();

  print('\n✅ Package name fix process completed!');
  print('\n💡 Next steps:');
  print('   1. If Flutter is available, run:');
  print('      flutter clean');
  print('      flutter pub get');
  print('      flutter build apk --release');
  print('\n   2. If building on CI/CD, ensure the build environment has:');
  print('      - Correct Flutter installation');
  print('      - Properly configured environment variables');
  print('      - Fresh checkout without build artifacts');
}

Future<void> _verifyPackageName() async {
  final pubspecFile = File('pubspec.yaml');
  if (!await pubspecFile.exists()) {
    print('   ⚠️  pubspec.yaml not found');
    return;
  }

  final content = await pubspecFile.readAsString();
  final lines = LineSplitter().convert(content);

  bool foundCorrectName = false;
  for (final line in lines) {
    if (line.startsWith('name:')) {
      if (line.contains('supremeai_mobile')) {
        print('   ✅ Package name is correct: supremeai_mobile');
        foundCorrectName = true;
      } else {
        print('   ⚠️  Unexpected package name found: $line');
      }
      break;
    }
  }

  if (!foundCorrectName) {
    print('   ❌ Package name verification failed');
  }
}

Future<void> _checkAllImports() async {
  final libDir = Directory('lib');
  if (!await libDir.exists()) {
    print('   ⚠️  lib directory not found');
    return;
  }

  int totalFiles = 0;
  int filesWithCorrectImports = 0;

  await for (final entity in libDir.list(recursive: true)) {
    if (entity is File && entity.path.endsWith('.dart')) {
      totalFiles++;

      final content = await entity.readAsString();
      final hasCorrectImport = content.contains("package:supremeai_mobile/");
      final hasIncorrectImport = content.contains("package:supreme_ai/");

      if (hasIncorrectImport) {
        print('   ❌ Found incorrect import in ${entity.path}');
        // Fix the import
        String fixedContent = content.replaceAll(
          RegExp(r"package:supreme_ai/"),
          "package:supremeai_mobile/"
        );

        await entity.writeAsString(fixedContent);
        print('      🔧 Fixed import in ${entity.path}');
      } else if (hasCorrectImport) {
        filesWithCorrectImports++;
      }
    }
  }

  print('   ✅ Checked $totalFiles Dart files, $filesWithCorrectImports have correct imports');
}

Future<void> _cleanBuildArtifacts() async {
  // Clean potential build artifacts that might cache incorrect paths
  final directoriesToDelete = [
    '.dart_tool',
    'build',
    '.flutter-plugins',
    '.flutter-plugins-dependencies',
    'android/.gradle',
    'ios/.symlinks',
  ];

  for (final dirName in directoriesToDelete) {
    final dir = Directory(dirName);
    if (await dir.exists()) {
      try {
        await dir.delete(recursive: true);
        print('   🗑️  Deleted $dirName directory');
      } catch (e) {
        print('   ⚠️  Could not delete $dirName: $e');
      }
    }
  }

  // Also delete any potential cached files with incorrect naming
  final cacheFiles = [
    '.packages',
    'Flutter.podspec',
  ];

  for (final fileName in cacheFiles) {
    final file = File(fileName);
    if (await file.exists()) {
      try {
        await file.delete();
        print('   🗑️  Deleted $fileName');
      } catch (e) {
        print('   ⚠️  Could not delete $fileName: $e');
      }
    }
  }

  print('   ✅ Cleaned potential build artifacts');
}
