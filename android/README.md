# Tuneva Android App

Android app architecture in this folder:

- WebView loads the hosted UI: https://tuneva.up.railway.app
- Embedded Python (Chaquopy) starts a local Flask server on app start
- Local server binds to http://127.0.0.1:5001
- Frontend stream logic uses Android bridge (window.Android.getLocalUrl())
- Android app playback is local-only via /local-stream on localhost

## Project files

- Activity: app/src/main/java/com/tuneva/app/MainActivity.kt
- WebView layout: app/src/main/res/layout/activity_main.xml
- Embedded server: app/src/main/python/local_server.py
- Stream extraction stack: app/src/main/python/stream_cache.py and app/src/main/python/stream_extractor.py
- Android manifest/WebView cleartext config: app/src/main/AndroidManifest.xml

## Prerequisites

- Android Studio (Hedgehog or newer)
- Android SDK 34
- JDK 17
- Python installed on build machine (used by Chaquopy during build)

## Build APK (Android Studio)

1. Open the android folder in Android Studio.
2. Wait for Gradle sync to finish and Chaquopy to install Python packages.
3. Build > Build Bundle(s) / APK(s) > Build APK(s).
4. Release APK path:
   app/build/outputs/apk/release/app-release.apk

## Build APK (command line)

1. Open terminal in android folder.
2. Run:

```bat
gradlew.bat clean assembleRelease
```

3. Output:

```text
android/app/build/outputs/apk/release/app-release.apk
```

## Copy APK into Flask static downloads

Run from repository root:

```bat
cd android
build_apk.bat
```

This copies the APK to:

```text
static/downloads/Tuneva.apk
```

## Runtime behavior notes

- Backend Flask app.py routes are unchanged.
- Desktop local engine behavior (127.0.0.1:5001) is unchanged.
- In Android WebView, streaming requests resolve through the in-app local Flask server.
