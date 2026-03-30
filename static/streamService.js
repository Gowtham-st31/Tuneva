(function (global) {

    function isMobileUA() {
        try {
            // If running inside Android app WebView,
            // do NOT treat as normal mobile browser
            if (window.Android && typeof window.Android.getLocalUrl === "function") {
                return false;
            }

            if (navigator.userAgentData && navigator.userAgentData.mobile !== undefined) {
                return !!navigator.userAgentData.mobile;
            }
        } catch (e) {}

        const ua = (navigator.userAgent || '').toLowerCase();
        return /mobi|android|iphone|ipad|ipod|phone|mobile/.test(ua);
    }

    function isAndroidWebViewBridge() {
        try {
            return !!(
                window.Android &&
                typeof window.Android.getLocalUrl === "function"
            );
        } catch (e) {
            return false;
        }
    }

    function sanitizeBaseUrl(value) {
        const raw = String(value || '').trim();
        if (!raw) {
            return null;
        }

        const cleaned = raw.replace(/\/+$/, '');
        if (!/^https?:\/\/[a-z0-9.:-]+$/i.test(cleaned)) {
            return null;
        }

        return cleaned;
    }

    const StreamService = {
        _isMobile: isMobileUA(),
        _isAndroidWebView: isAndroidWebViewBridge(),
        _localAvailable: false,
        _cachedBridgeBase: null,
        _statusListeners: [],

        init() {
            this._cachedBridgeBase = this._readAndroidLocalBase();
            this.checkLocalEngine();

            // Auto refresh status while app is active.
            setInterval(() => {
                this.checkLocalEngine();
            }, 3000);
        },

        _readAndroidLocalBase() {
            if (!this._isAndroidWebView) {
                return null;
            }

            try {
                return sanitizeBaseUrl(global.Android.getLocalUrl());
            } catch (e) {
                return null;
            }
        },

        _resolveLocalBase() {
            if (this._isAndroidWebView) {
                const bridgeBase = this._readAndroidLocalBase() || this._cachedBridgeBase;
                if (bridgeBase) {
                    this._cachedBridgeBase = bridgeBase;
                    return bridgeBase;
                }
                return 'http://127.0.0.1:5001';
            }

            if (this._isMobile) {
                return 'http://10.0.2.2:5001';
            }

            return 'http://127.0.0.1:5001';
        },

        _buildLocalStreamUrl(url, title) {
            const localBase = this._resolveLocalBase();
            return `${localBase}/local-stream?url=${encodeURIComponent(url)}&title=${encodeURIComponent(title)}`;
        },

        async _fetchStream(streamEndpoint) {
            try {
                const res = await fetch(streamEndpoint);

                if (!res || !res.ok) {
                    return null;
                }

                const data = await res.json();

                if (
                    !data ||
                    !data.stream_url ||
                    data.stream_url === '' ||
                    data.stream_url === 'test' ||
                    !String(data.stream_url).startsWith('http')
                ) {
                    return null;
                }

                return data;
            } catch (e) {
                return null;
            }
        },

        async checkLocalEngine() {
            let success = false;

            try {
                const localBase = this._resolveLocalBase();
                const res = await fetch(`${localBase}/local-stream?url=test`);

                if (res && res.ok) {
                    success = true;
                }
            } catch (e) {
                success = false;
            }

            this._localAvailable = success;
            this.localAvailable = success;
            this._emitStatus();

            return success;
        },

        onStatusChange(fn) {
            if (typeof fn === 'function') this._statusListeners.push(fn);
        },

        _emitStatus() {
            const st = this.getStatus();
            this._statusListeners.forEach(fn => {
                try { fn(st); } catch (e) {}
            });
        },

        getStatus() {
            if (this._isAndroidWebView) {
                return {
                    device: "android-webview",
                    local: this._localAvailable,
                    message: this._localAvailable
                        ? "Local Engine Connected ✅"
                        : "Starting local engine..."
                };
            }

            if (this._isMobile) {
                return {
                    device: 'mobile',
                    local: false,
                    message: 'Install Tuneva App for best experience'
                };
            }

            return {
                device: 'desktop',
                local: this._localAvailable,
                message: this._localAvailable
                    ? 'Local Engine Connected'
                    : 'Local Engine Not Running'
            };
        },

        async getStream(url, title = "") {

            if (!url) return null;

            const localUrl = this._buildLocalStreamUrl(url, title);

            if (this._isAndroidWebView) {
                // Android app playback must stay local-only.
                return await this._fetchStream(localUrl);
            }

            if (this.localAvailable) {
                const localData = await this._fetchStream(localUrl);
                if (localData) {
                    return localData;
                }
            }

            const remoteLocalRoute = `/local-stream?url=${encodeURIComponent(url)}&title=${encodeURIComponent(title)}`;
            return await this._fetchStream(remoteLocalRoute);
        }
    };

    global.StreamService = StreamService;

    try {
        StreamService.init();
    } catch (e) {}

})(window);