plugins {
    id("com.android.application")
    id("kotlin-android")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.example.supremeai"
    // বাংলা মন্তব্য: androidx.core-ktx 1.18.0 এর জন্য Android SDK 36 এ কম্পাইল করা আবশ্যক
    compileSdk = 36
    ndkVersion = "27.0.12077973"

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
        isCoreLibraryDesugaringEnabled = true
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_17.toString()
    }

    defaultConfig {
        applicationId = "com.example.supremeai"
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
        
        // Performance optimizations for Flutter
        // ABI filters are managed by Flutter splits (--split-per-abi) in CI
        // ndk {
        //     abiFilters += listOf("armeabi-v7a", "arm64-v8a", "x86_64")
        // }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("debug")
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
        debug {
            isMinifyEnabled = false
        }
    }
    
    buildFeatures {
        buildConfig = true
    }
    
    packagingOptions {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

flutter {
    source = "../.."
}

dependencies {
    // বাংলা মন্তব্য: flutter_local_notifications এর রিকোয়ারমেন্ট অনুযায়ী desugar_jdk_libs আপডেট করা হলো
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.4")
}
