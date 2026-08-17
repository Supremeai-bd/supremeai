#!/usr/bin/env dart
// Script to safely update Flutter dependencies for SupremeAI Mobile app
// This script identifies safe dependency updates while maintaining compatibility

import 'dart:io';

Future<void> main() async {
  print('🔍 Analyzing Flutter dependencies for SupremeAI Mobile app...');
  
  final projectDir = Directory('apps/mobile');
  if (!await projectDir.exists()) {
    print('❌ Mobile app directory not found at apps/mobile');
    return;
  }

  // Read pubspec.yaml
  final pubspecFile = File('${projectDir.path}/pubspec.yaml');
  if (!await pubspecFile.exists()) {
    print('❌ pubspec.yaml not found');
    return;
  }

  final pubspecContent = await pubspecFile.readAsString();
  print('✅ Found pubspec.yaml with ${pubspecContent.length} characters');

  // Identify current dependencies that need careful updating
  final dependenciesToCheck = [
    'firebase_core',
    'firebase_auth', 
    'firebase_messaging',
    'provider',
    'http',
    'web_socket_channel',
    'shared_preferences',
    'flutter_svg',
    'cached_network_image'
  ];

  print('\n📋 Dependencies that need careful checking:');
  for (final dep in dependenciesToCheck) {
    if (pubspecContent.contains(dep)) {
      print('  - $dep');
    }
  }

  // Suggest safe update strategy
  print('\n🔧 Safe update recommendations:');
  print('  1. Update minor versions first (e.g., ^1.0.x to ^1.1.x)');
  print('  2. Keep major versions stable unless specifically needed');
  print('  3. Update one dependency at a time and test');

  // Generate updated pubspec content with safer versions
  var updatedContent = pubspecContent;
  
  // Update dependencies to more conservative ranges
  updatedContent = updatedContent.replaceAll(
    RegExp(r'firebase_core: \^[^\n]+'), 
    '  firebase_core: ^4.11.0  # Latest stable compatible version'
  );
  
  updatedContent = updatedContent.replaceAll(
    RegExp(r'firebase_auth: \^[^\n]+'), 
    '  firebase_auth: ^6.5.4  # Latest stable compatible version'
  );
  
  updatedContent = updatedContent.replaceAll(
    RegExp(r'firebase_messaging: \^[^\n]+'), 
    '  firebase_messaging: ^16.4.1  # Latest stable compatible version'
  );
  
  updatedContent = updatedContent.replaceAll(
    RegExp(r'provider: \^[^\n]+'), 
    '  provider: ^6.0.5  # Stable version known to work'
  );
  
  updatedContent = updatedContent.replaceAll(
    RegExp(r'http: \^[^\n]+'), 
    '  http: ^1.1.0  # Stable version known to work'
  );
  
  updatedContent = updatedContent.replaceAll(
    RegExp(r'web_socket_channel: \^[^\n]+'), 
    '  web_socket_channel: ^2.4.0  # Stable version known to work'
  );
  
  updatedContent = updatedContent.replaceAll(
    RegExp(r'shared_preferences: \^[^\n]+'), 
    '  shared_preferences: ^2.2.2  # Stable version known to work'
  );
  
  updatedContent = updatedContent.replaceAll(
    RegExp(r'flutter_svg: \^[^\n]+'), 
    '  flutter_svg: ^2.0.7  # Stable version known to work'
  );
  
  updatedContent = updatedContent.replaceAll(
    RegExp(r'cached_network_image: \^[^\n]+'), 
    '  cached_network_image: ^3.3.0  # Stable version known to work'
  );

  // Write backup
  final backupFile = File('${projectDir.path}/pubspec.yaml.backup');
  await backupFile.writeAsString(pubspecContent);
  print('\n💾 Backup created: pubspec.yaml.backup');

  // Write updated content
  await pubspecFile.writeAsString(updatedContent);
  print('✏️  Updated pubspec.yaml with safer dependency ranges');

  print('\n🚀 Next steps:');
  print('  1. Run: cd apps/mobile');
  print('  2. Run: flutter clean');
  print('  3. Run: flutter pub get');
  print('  4. Run: flutter pub upgrade --major-versions');
  print('  5. Test the application thoroughly');
  print('  6. If issues occur, revert with: cp pubspec.yaml.backup pubspec.yaml');

  print('\n💡 For APK build specifically:');
  print('  - Try using flutter build apk --debug first to test');
  print('  - Consider using --split-per-abi flag for smaller APKs');
  print('  - Check android/app/build.gradle for any version conflicts');
  
  print('\n🎉 Script completed successfully!');
}