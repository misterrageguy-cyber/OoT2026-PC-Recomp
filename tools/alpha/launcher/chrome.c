/* The launcher window's frame without Windows' caption (ocr_chrome.dll, loaded by ui.py).

   The frame's window procedure has to run outside Python: Windows calls it inside its own move and size loops, and Tk runs
   its Python callbacks (the build screen's animation, a resize) from inside it. A Python window procedure there means Python
   inside Python on one thread, which Python ends with abort(). This one never calls Python:
     WM_NCCALCSIZE  the client area takes the caption's place; the frame's left, right and bottom stay (resize edges, snap,
                    shadow); maximised, the top too (the window overhangs the screen by the frame)
     WM_DPICHANGED  the size Windows suggests for the new screen's scaling
     WM_DROPFILES   the dropped paths kept here; ui.py takes them from a Tk timer (ocr_chrome_take_drop)
   Build: clang -O2 -shared chrome.c -o ocr_chrome.dll -lcomctl32 -lshell32 -luser32 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <commctrl.h>
#include <shellapi.h>
#include <wchar.h>

#define DROP_MAX 32768
static wchar_t drop_buf[DROP_MAX];   /* the dropped paths, each ended by '\n'; empty: none waiting */
static volatile LONG drop_ready;
#define WM_OCR_FRAME (WM_APP + 77)   /* the frame changed: posted at install, done from the window's own message loop */

static int frame_x(HWND h) {
    UINT dpi = GetDpiForWindow(h);
    return GetSystemMetricsForDpi(SM_CXSIZEFRAME, dpi) + GetSystemMetricsForDpi(SM_CXPADDEDBORDER, dpi);
}
static int frame_y(HWND h) {
    UINT dpi = GetDpiForWindow(h);
    return GetSystemMetricsForDpi(SM_CYSIZEFRAME, dpi) + GetSystemMetricsForDpi(SM_CXPADDEDBORDER, dpi);
}

static LRESULT CALLBACK proc(HWND h, UINT msg, WPARAM wp, LPARAM lp, UINT_PTR id, DWORD_PTR data) {
    (void)id, (void)data;
    switch (msg) {
    case WM_NCCALCSIZE:
        if (wp) {
            NCCALCSIZE_PARAMS* p = (NCCALCSIZE_PARAMS*)lp;
            const int fx = frame_x(h), fy = frame_y(h);
            p->rgrc[0].left += fx;
            p->rgrc[0].right -= fx;
            p->rgrc[0].bottom -= fy;
            if (IsZoomed(h)) p->rgrc[0].top += fy;
            return 0;
        }
        break;
    case WM_DPICHANGED: {
        const RECT* r = (const RECT*)lp;
        SetWindowPos(h, NULL, r->left, r->top, r->right - r->left, r->bottom - r->top, SWP_NOZORDER | SWP_NOACTIVATE);
        return 0;
    }
    case WM_DROPFILES: {
        HDROP d = (HDROP)wp;
        UINT n = DragQueryFileW(d, 0xFFFFFFFF, NULL, 0);
        size_t used = 0;
        drop_buf[0] = 0;
        for (UINT i = 0; i < n; i++) {
            wchar_t path[MAX_PATH * 4];
            UINT len = DragQueryFileW(d, i, path, (UINT)(sizeof path / sizeof path[0]));
            if (len && used + len + 2 < DROP_MAX) {
                wmemcpy(drop_buf + used, path, len);
                used += len;
                drop_buf[used++] = L'\n';
                drop_buf[used] = 0;
            }
        }
        DragFinish(d);
        if (used) InterlockedExchange(&drop_ready, 1);
        return 0;
    }
    case WM_OCR_FRAME:
        SetWindowPos(h, NULL, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED);
        return 0;
    case WM_NCDESTROY:
        RemoveWindowSubclass(h, proc, 1);
        break;
    }
    return DefSubclassProc(h, msg, wp, lp);
}

/* installs the frame on the Tk window's wrapper; 1 when it took */
__declspec(dllexport) int ocr_chrome_install(HWND h) {
    if (!SetWindowSubclass(h, proc, 1, 0)) return 0;
    DragAcceptFiles(h, TRUE);
    /* (posted, not done here: done here, Windows would call Tk's window procedure from inside this call, Tk would run Python
       callbacks while Python waits in ctypes, and Python ends that with abort()) */
    PostMessageW(h, WM_OCR_FRAME, 0, 0);
    return 1;
}

/* starts Windows' own move (HTCAPTION) or size (HTTOP...) of the window, posted for the same reason */
__declspec(dllexport) void ocr_chrome_begin(HWND h, int hit) {
    ReleaseCapture();
    PostMessageW(h, WM_NCLBUTTONDOWN, (WPARAM)hit, 0);
}

/* a window class for the fairy whose procedure is Windows' own (no Python window procedure) */
__declspec(dllexport) ATOM ocr_plain_class(const wchar_t* name) {
    WNDCLASSEXW wc = {sizeof wc};
    wc.lpfnWndProc = DefWindowProcW;
    wc.hInstance = GetModuleHandleW(NULL);
    wc.lpszClassName = name;
    return RegisterClassExW(&wc);
}

/* the paths dropped since the last call, '\n' after each, into out (cap characters); their length, 0 when none */
__declspec(dllexport) int ocr_chrome_take_drop(wchar_t* out, int cap) {
    if (!InterlockedExchange(&drop_ready, 0)) return 0;
    int n = (int)wcslen(drop_buf);
    if (n >= cap) n = cap - 1;
    wmemcpy(out, drop_buf, n);
    out[n] = 0;
    return n;
}
