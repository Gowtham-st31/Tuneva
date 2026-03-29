package com.tuneva.app

import android.annotation.SuppressLint
import android.os.Bundle
import android.util.Log
import android.webkit.CookieManager
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
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
        setContentView(R.layout.activity_main)

        webView = findViewById(R.id.tunevaWebView)

        startLocalPythonServer()
        configureWebView()
        configureBackNavigation()

        webView.loadUrl(RAILWAY_URL)
    }

    private fun startLocalPythonServer() {
        if (!serverBootRequested.compareAndSet(false, true)) {
            return
        }

        val activityRef = WeakReference(this)

        Thread(
            {
                try {
                    val activity = activityRef.get() ?: return@Thread
                    if (!Python.isStarted()) {
                        Python.start(AndroidPlatform(activity.applicationContext))
                    }
                    val py = Python.getInstance()
                    val module = py.getModule("local_server")
                    module.callAttr("start_server", LOCAL_HOST, LOCAL_PORT)
                    Log.i(TAG, "Local Python server start requested on $LOCAL_HOST:$LOCAL_PORT")
                } catch (error: Throwable) {
                    Log.e(TAG, "Failed to start local Python server", error)
                }
            },
            "tuneva-local-server-bootstrap"
        ).start()
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun configureWebView() {
        val settings = webView.settings
        settings.javaScriptEnabled = true
        settings.domStorageEnabled = true
        settings.mediaPlaybackRequiresUserGesture = false
        settings.allowContentAccess = true
        settings.allowFileAccess = true
        settings.mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
        settings.userAgentString = "${settings.userAgentString} TunevaAndroidWebView/1.0"

        val cookieManager = CookieManager.getInstance()
        cookieManager.setAcceptCookie(true)
        cookieManager.setAcceptThirdPartyCookies(webView, true)

        webView.addJavascriptInterface(AndroidBridge(), "Android")
        webView.webViewClient = WebViewClient()
        webView.webChromeClient = WebChromeClient()
    }

    private fun configureBackNavigation() {
        backPressedCallback = object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.canGoBack()) {
                    webView.goBack()
                    return
                }
                isEnabled = false
                onBackPressedDispatcher.onBackPressed()
            }
        }
        onBackPressedDispatcher.addCallback(this, backPressedCallback)
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
        fun getLocalUrl(): String = "http://$LOCAL_HOST:$LOCAL_PORT"

        @JavascriptInterface
        fun isAndroidWebView(): Boolean = true
    }

    companion object {
        private const val TAG = "TunevaMainActivity"
        private const val RAILWAY_URL = "https://tuneva.up.railway.app"
        private const val LOCAL_HOST = "127.0.0.1"
        private const val LOCAL_PORT = 5001
    }
}
