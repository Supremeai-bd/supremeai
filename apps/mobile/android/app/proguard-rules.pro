# Flutter optimization rules
-keep class io.flutter.** { *; }
-keep class androidx.lifecycle.** { *; }
-dontwarn androidx.lifecycle.**
-keep class com.google.firebase.** { *; }
-dontwarn com.google.firebase.**
-assumenosideeffects class io.flutter.util.Trace { *; }

# Google Play Core rules to resolve R8 missing class errors
-keep class com.google.android.play.core.** { *; }
-dontwarn com.google.android.play.core.**