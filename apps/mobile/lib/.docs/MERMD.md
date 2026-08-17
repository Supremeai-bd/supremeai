# MERMD - SupremeAI Flutter App

## Overview

Flutter mobile application for the SupremeAI platform.

## How It Works

### Architecture Flow

```
User → Flutter UI → API Service → Backend → Response
```

## Structure

### Key Directories

| Directory        | Purpose                |
| ---------------- | ---------------------- |
| `lib/main.dart`  | App entry point        |
| `lib/screens/`   | Screen pages           |
| `lib/widgets/`   | Reusable widgets       |
| `lib/services/`  | API and business logic |
| `lib/providers/` | State management       |
| `lib/theme/`     | App theming            |

## Main Screens

| Screen                  | Purpose              |
| ----------------------- | -------------------- |
| `home_screen.dart`      | Main dashboard       |
| `login_screen.dart`     | Authentication       |
| `analytics_screen.dart` | Analytics view       |
| `consensus_screen.dart` | AI consensus results |
| `learning_screen.dart`  | Learning system      |
| `vpn_screen.dart`       | VPN management       |
| `api_keys_screen.dart`  | API key management   |
| `settings_screen.dart`  | App settings         |
| `quota_screen.dart`     | Quota view           |

## Services

| Service                     | Purpose                 |
| --------------------------- | ----------------------- |
| `api_service.dart`          | HTTP client for backend |
| `localization_service.dart` | i18n support            |

## Providers (State Management)

| Provider                      | Purpose                |
| ----------------------------- | ---------------------- |
| `auth_provider.dart`          | Authentication state   |
| `settings_provider.dart`      | App settings           |
| `orchestration_provider.dart` | AI orchestration state |

## Theme

- `app_theme.dart` - Theme configuration
- `theme_provider.dart` - Theme switching

## Generated Code

- `dataconnect_generated/` - Firebase DataConnect generated code
