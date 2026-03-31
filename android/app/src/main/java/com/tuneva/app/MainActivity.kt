package com.tuneva.app

import android.annotation.SuppressLint
import android.os.Bundle
import android.util.Log
import android.webkit.CookieManager
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.lang.ref.WeakReference
import java.util.concurrent.atomic.AtomicBoolean

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var backPressedCallback: OnBackPressedCallback
    private val serverBootRequested = AtomicBoolean(false)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Create WebView safely
        webView = WebView(this)
        setContentView(webView)

        configureWebView()
        configureBackNavigation()

        // Load UI first
        webView.loadUrl(RAILWAY_URL)

        // Start local python server after UI
        startLocalPythonServer()
    }

    private fun startLocalPythonServer() {
        if (!serverBootRequested.compareAndSet(false, true)) {
            return
        }

        val activityRef = WeakReference(this)

        Thread({
            try {
                val activity = activityRef.get() ?: return@Thread

                Log.d(TAG, "Starting Python runtime")

                if (!Python.isStarted()) {
                    Python.start(
                        AndroidPlatform(
                            activity.applicationContext
                        )
                    )
                }

                val py = Python.getInstance()

                Log.d(TAG, "Loading local_server module")

                val module = py.getModule("local_server")

                module.callAttr("start_server")

                Log.d(TAG, "Local python server started on 127.0.0.1:5001")

            } catch (e: Exception) {
                Log.e(TAG, "PYTHON ERROR", e)
            } catch (t: Throwable) {
                Log.e(TAG, "FATAL ERROR", t)
            }
        }, "tuneva-python-server").start()
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun configureWebView() {
        val settings = webView.settings

        settings.javaScriptEnabled = true
        settings.domStorageEnabled = true
        settings.databaseEnabled = true
        settings.allowContentAccess = true
        settings.allowFileAccess = true
        settings.loadsImagesAutomatically = true
        settings.mediaPlaybackRequiresUserGesture = false
        settings.mixedContentMode =
            WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
        settings.javaScriptCanOpenWindowsAutomatically = true

        settings.userAgentString =
            settings.userAgentString + " TunevaAndroidWebView/1.0"

        val cookieManager = CookieManager.getInstance()
        cookieManager.setAcceptCookie(true)
        cookieManager.setAcceptThirdPartyCookies(webView, true)

        webView.addJavascriptInterface(
            AndroidBridge(),
            "Android"
        )

        webView.webViewClient = object : WebViewClient() {

            override fun onPageFinished(
                view: WebView?,
                url: String?
            ) {
                super.onPageFinished(view, url)
                Log.d(TAG, "PAGE LOADED: $url")
            }

            override fun onReceivedError(
                view: WebView,
                request: WebResourceRequest,
                error: WebResourceError
            ) {
                Log.e(
                    TAG,
                    "WEBVIEW ERROR: ${error.description}"
                )
            }
        }

        webView.webChromeClient = WebChromeClient()
    }

    private fun configureBackNavigation() {
        backPressedCallback =
            object : OnBackPressedCallback(true) {
                override fun handleOnBackPressed() {
                    if (webView.canGoBack()) {
                        webView.goBack()
                    } else {
                        isEnabled = false
                        onBackPressedDispatcher.onBackPressed()
                    }
                }
            }

        onBackPressedDispatcher.addCallback(
            this,
            backPressedCallback
        )
    }

    override fun onDestroy() {
        if (::backPressedCallback.isInitialized) {
            backPressedCallback.remove()
        }

        if (::webView.isInitialized) {
            webView.stopLoading()
            webView.destroy()
        }

        super.onDestroy()
    }

    private inner class AndroidBridge {

        @JavascriptInterface
        fun getLocalUrl(): String {
            return "http://127.0.0.1:5001"
        }

        @JavascriptInterface
        fun isAndroidWebView(): Boolean {
            return true
        }
    }

    companion object {
        private const val TAG = "Tuneva"
        private const val RAILWAY_URL =
            "https://tuneva.onrender.com"
    }
}