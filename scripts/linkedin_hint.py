"""
linkedin_hint.py
A small, dismissible banner shown ONLY inside LinkedIn's in-app browser.

Why: LinkedIn's built-in browser ignores target="_blank", so a reader who taps a
source citation loses the article and has to tap back. A page cannot change that,
but it can tell the reader how to escape the in-app viewer. Everyone else
(Safari, Chrome, desktop) never sees this: it stays hidden unless the user agent
contains "LinkedInApp".

Single source of truth: renderer.py inserts LINKEDIN_HINT into every new post,
and add_linkedin_hint.py inserts the same block into already-published posts.
The id="li-hint" marker is what makes the patch idempotent.

Raw string on purpose: the JavaScript uses backslash escapes that Python must
not interpret.
"""

LINKEDIN_HINT = r"""
    <style>
        #li-hint { display: none; position: relative; text-align: center; background: #eff6ff; border-bottom: 1px solid #bfdbfe; color: #1e3a8a; font: 500 13px/1.45 Inter, -apple-system, system-ui, sans-serif; padding: 10px 44px 10px 16px; }
        #li-hint.show { display: block; }
        #li-hint-close { position: absolute; right: 6px; top: 50%; transform: translateY(-50%); background: none; border: 0; color: #1e3a8a; font-size: 22px; line-height: 1; padding: 6px 12px; cursor: pointer; }
    </style>
    <div id="li-hint" role="note"><span id="li-hint-text"></span><button type="button" id="li-hint-close" aria-label="Dismiss tip">&times;</button></div>
    <script>
    (function () {
        try {
            var ua = navigator.userAgent || '';
            if (!/LinkedInApp/i.test(ua)) return;
            var el = document.getElementById('li-hint');
            if (!el) return;
            try { if (sessionStorage.getItem('li-hint-closed')) return; } catch (e) {}
            var ios = /iPhone|iPad|iPod/i.test(ua);
            document.getElementById('li-hint-text').textContent =
                'Tip: for the best reading experience, tap the \u2022\u2022\u2022 menu and choose \u201c' +
                (ios ? 'Open in Safari' : 'Open in browser') +
                '\u201d. Source links will then open in a new tab.';
            el.className = 'show';
            document.getElementById('li-hint-close').addEventListener('click', function () {
                el.className = '';
                try { sessionStorage.setItem('li-hint-closed', '1'); } catch (e) {}
            });
            if (typeof gtag === 'function') { gtag('event', 'linkedin_inapp_hint_shown'); }
        } catch (e) {}
    })();
    </script>
"""
