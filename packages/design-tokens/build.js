import StyleDictionary from 'style-dictionary';
import fs from 'fs';
import path from 'path';

// Register a custom transform for Dart (Flutter)
StyleDictionary.registerTransform({
  name: 'size/flutter/sp',
  type: 'value',
  filter: function(prop) {
    return prop.attributes.category === 'font' && prop.attributes.type === 'size';
  },
  transform: function(prop) {
    return parseFloat(prop.original.value) + '.sp';
  }
});

StyleDictionary.registerFormat({
  name: 'vscode/theme',
  format: function({ dictionary }) {
    const colors = {};
    dictionary.allTokens.forEach(token => {
      // Map token to VS Code color key, assuming we structure it appropriately
      // For simplicity, we just dump them flat for testing, or map specific ones
      // E.g., `vscode.editor.background`
      if (token.path[0] === 'vscode') {
        const key = token.path.slice(1).join('.');
        colors[key] = token.value;
      }
    });

    return JSON.stringify({
      name: "SupremeAI Theme",
      type: "dark",
      colors: colors,
      tokenColors: []
    }, null, 2);
  }
});

StyleDictionary.registerFormat({
  name: 'flutter/custom',
  format: function({ dictionary }) {
    let output = "import 'dart:ui';\n\nclass AppColors {\n  AppColors._();\n\n";
    dictionary.allTokens.forEach(token => {
      if (token.path[0] !== 'vscode') {
        const name = token.name;
        // Convert hex #RRGGBB to 0xFFRRGGBB
        let value = token.value;
        if (typeof value === 'string' && value.startsWith('#')) {
          value = `Color(0xFF${value.substring(1)})`;
        }
        output += `  static const ${name} = ${value};\n`;
      }
    });
    output += "}\n";
    return output;
  }
});

const sd = new StyleDictionary({
  source: ['tokens/**/*.json'],
  platforms: {
    css: {
      transformGroup: 'css',
      buildPath: 'outputs/css/',
      files: [{
        destination: 'variables.css',
        format: 'css/variables'
      }]
    },
    json: {
      transformGroup: 'web',
      buildPath: 'outputs/json/',
      files: [{
        destination: 'tokens.json',
        format: 'json/flat'
      }]
    },
    flutter: {
      transformGroup: 'flutter',
      buildPath: 'outputs/flutter/',
      files: [{
        destination: 'colors.dart',
        format: 'flutter/custom'
      }]
    },
    vscode: {
      transformGroup: 'web',
      buildPath: 'outputs/vscode/',
      files: [{
        destination: 'supremeai-theme.json',
        format: 'vscode/theme'
      }]
    }
  }
});

sd.buildAllPlatforms();
console.log('Design tokens generated successfully!');
