Tuneva Android APK build instructions

This project does not include a prebuilt APK. Building an Android APK requires Android SDK/NDK and Android Studio.

Options to build an Android app that opens the site in a WebView:

1) Android Studio (recommended)
   - Create a new "Empty Activity" project.
   - Add an activity layout with a WebView and request INTERNET permission in AndroidManifest.xml.
   - In the activity use WebView.loadUrl("https://your-site.example.com") or `http://your-railway-or-public-host`.
   - Build > Build Bundle(s) / APK(s) > Build APK(s).
   - Rename the output to `Tuneva.apk` and place it in `static/downloads/`.

2) Use Cordova (quick WebView wrapper)
   - Install Node.js and Cordova: `npm install -g cordova`
   - Create app: `cordova create tuneva com.tuneva.app Tuneva`
   - Add Android platform: `cd tuneva && cordova platform add android`
   - Replace `www/index.html` to redirect to your web player or use the InAppBrowser plugin.
   - Build: `cordova build android --release`
   - Sign the APK and rename to `Tuneva.apk` then move to `static/downloads/`.

3) CI build (recommended for automation)
   - Use GitHub Actions with `macos` or `ubuntu` runners configured with the Android SDK.
   - Add a dedicated `android/` project in this repo and run `./gradlew assembleRelease` in the workflow.

Notes on integrating yt-dlp on Android (advanced/optional):
 - Use Chaquopy to run Python and yt-dlp inside the app, or include a native yt-dlp binary; both are advanced and out of scope for this quick wrapper.
 - Prefer using the native player (ExoPlayer) in the app and fetch a stream URL from your server when possible.

Automation suggestion (minimal):
 - Add an `android/` folder with a full Android Studio project.
 - Add a GitHub Actions workflow to build and upload the `Tuneva.apk` artifact.

If you'd like, I can scaffold a minimal Android Studio WebView project in `android/` and add CI steps to build the APK on push. Building the APK and producing a signed release will still require secrets for signing or manual signing steps.
