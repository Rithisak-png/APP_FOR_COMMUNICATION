[app]

# ── Identity ──────────────────────────────────────────────────────────
title           = WalkieTalkie
package.name    = walkietalkie
package.domain  = org.example
version         = 1.0.0

# ── Source ────────────────────────────────────────────────────────────
source.dir       = .
source.include_exts = py,kv,png,jpg,ttf,opus

# Entry point
entrypoint = main.py

# ── Requirements ──────────────────────────────────────────────────────
# List every Python package the app imports.
# opuslib needs the native libopus – handled via android.add_aars or
# a pre-built .so; see the note below the file.
requirements = python3==3.7.6,hostpython3==3.7.6, kivy, pillow
    kivy==2.3.0,
    numpy,
    sounddevice,
    zeroconf,
    opuslib

# ── Android permissions ───────────────────────────────────────────────
android.permissions =
    RECORD_AUDIO,
    INTERNET,
    ACCESS_NETWORK_STATE,
    ACCESS_WIFI_STATE,
    CHANGE_WIFI_STATE,
    CHANGE_WIFI_MULTICAST_STATE,
    ACCESS_FINE_LOCATION,
    ACCESS_COARSE_LOCATION,
    FOREGROUND_SERVICE

# ── Android build settings ────────────────────────────────────────────
android.api         = 33
android.minapi      = 24
android.ndk         = 25b
android.sdk         = 33
android.ndk_api     = 24

# ABIs to build (arm64-v8a covers most modern phones;
# add armeabi-v7a if you still need 32-bit devices)
android.archs = arm64-v8a, armeabi-v7a

# Keep Java source for debugging; set to 0 for release
android.copy_libs = 1

# Gradle extras – lets multicast sockets work on Android
android.gradle_dependencies =
    androidx.core:core:1.10.1

# Add this so the app can acquire a MulticastLock at runtime
android.add_activites =

# Application theme (fullscreen, no title bar)
android.presplash_color = #F2F2F7
android.presplash.filename = %(source.dir)s/presplash.png

android.icon.filename = %(source.dir)s/icon.png

# Orientation – portrait only (change to landscape if needed)
orientation = portrait

# Fullscreen (removes the Android status bar)
fullscreen = 0

# ── Android manifest extras ───────────────────────────────────────────
# Declare a foreground service so audio keeps running when screen locks
android.manifest.intent_filters =

android.meta_data =

# ── iOS settings ──────────────────────────────────────────────────────
ios.kivy_ios_url   = https://github.com/kivy/kivy-ios
ios.kivy_ios_branch = master

# iOS privacy usage strings (required by App Store review)
ios.info_plist =
    NSMicrophoneUsageDescription : This app uses the microphone for Push-to-Talk voice transmission.
    NSLocalNetworkUsageDescription : This app communicates with nearby peers over your local Wi-Fi network.
    NSBonjourServices : _walkietalkie._udp

# ── Buildozer / build config ──────────────────────────────────────────
[buildozer]

# Directory where Buildozer stores its build cache
build_dir = ./.buildozer

# Where the finished APK / IPA lands
bin_dir = ./bin

# Set to 2 for verbose output while debugging, 1 for normal
log_level = 2

# Warn before running as root (leave at 1)
warn_on_root = 1
