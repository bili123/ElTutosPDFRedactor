"""
El Tutos PDF Redactor
Copyright (C) 2025 Mirco Lang

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, version 3.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY.
See the GNU Affero General Public License for more details.
"""


import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
try:
    import pymupdf as pymupdf  # newer name (pip installs)
except ImportError:
    import fitz as pymupdf     # Ubuntu/Debian package name



APP_TITLE = "El Tutos PDF Redactor"
GITHUB_URL = "https://github.com/bili123/ElTutosPDFRedactor"


class PDFRedactorGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)

        # --- Icon (Windows) ---
        self._set_window_icon()

        # --- Theme ---
        self.theme = "dark"
        self.themes = {
            "dark": {
                "canvas_bg": "gray20",
                "page_border": "gray60",
                "ui_bg": None,     # let tk default
                "ui_fg": None,
            },
            "light": {
                "canvas_bg": "white",
                "page_border": "gray50",
                "ui_bg": None,
                "ui_fg": None,
            }
        }

        # --- State ---
        self.doc = None
        self.pdf_path = None
        self.zoom = 2.0
        self.redactions = {}  # {page_index: [fitz.Rect, ...]}

        # Rendered pages
        self.page_imgs = []    # ImageTk references
        self.page_sizes = []   # (w, h) in px
        self.page_scales = []  # px per PDF unit

        # Layout positions per page in canvas px
        self.page_pos = []     # [(x, y), ...]
        self.current_page = 0

        # Drawing state
        self.drag_start = None   # (x, y) canvas coords
        self.drag_page = None    # page index
        self.current_rect_item = None

        # Resize debounce
        self._resize_after_id = None

        self._build_ui()
        self._apply_theme()

    # ---------------- UI ----------------
    def _build_ui(self):
        # Two-row toolbar so buttons never disappear on small windows
        bar = tk.Frame(self.root)
        bar.pack(side=tk.TOP, fill=tk.X)
        
        row1 = tk.Frame(bar)
        row1.pack(side=tk.TOP, fill=tk.X)
        
        row2 = tk.Frame(bar)
        row2.pack(side=tk.TOP, fill=tk.X)
        
        # --- Row 1: core navigation/edit buttons ---
        tk.Button(row1, text="Open PDF…", command=self.open_pdf).pack(side=tk.LEFT, padx=4, pady=4)
        tk.Button(row1, text="Prev", command=self.prev_page).pack(side=tk.LEFT, padx=4, pady=4)
        tk.Button(row1, text="Next", command=self.next_page).pack(side=tk.LEFT, padx=4, pady=4)
        
        tk.Button(row1, text="Undo last (page)", command=self.undo_last).pack(side=tk.LEFT, padx=10, pady=4)
        tk.Button(row1, text="Clear page", command=self.clear_page).pack(side=tk.LEFT, padx=4, pady=4)
        
        # --- Row 2: search + actions (includes Save/Info/Theme, always visible) ---
        sf = tk.Frame(row2)
        sf.pack(side=tk.LEFT, padx=4, pady=4)
        
        tk.Label(sf, text="Find:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(sf, textvariable=self.search_var, width=28)
        self.search_entry.pack(side=tk.LEFT, padx=4)
        
        self.regex_var = tk.BooleanVar(value=False)
        tk.Checkbutton(sf, text="Regex", variable=self.regex_var).pack(side=tk.LEFT, padx=6)
        
        tk.Button(sf, text="Redact matches", command=self.redact_matches).pack(side=tk.LEFT, padx=4)
        
        # Put these on row 2 so they never get pushed off-screen
        tk.Button(row2, text="Save as…", command=self.save_as).pack(side=tk.LEFT, padx=10)
        tk.Button(row2, text="Info", command=self.show_info).pack(side=tk.LEFT, padx=6)
        tk.Button(row2, text="Theme", command=self.toggle_theme).pack(side=tk.LEFT, padx=6)
        
        # Page label on the right of row 2
        self.page_label = tk.Label(row2, text="No document loaded")
        self.page_label.pack(side=tk.RIGHT, padx=10)
        
        # --- Canvas area (unchanged) ---
        frame = tk.Frame(self.root)
        frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(frame)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        vbar = tk.Scrollbar(frame, orient=tk.VERTICAL, command=self.canvas.yview)
        # hbar = tk.Scrollbar(frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vbar.set)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        #hbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<ButtonPress-3>", self.on_right_click_delete)
        self.canvas.bind_all("<MouseWheel>", self.on_mousewheel)
        self.canvas.bind("<Configure>", self.on_canvas_configure)
        
        self.search_entry.bind("<Return>", lambda _e: self.redact_matches())
        
        # Mouse wheel scrolling (cross-platform)
        self.canvas.bind("<Enter>", lambda e: self.canvas.focus_set())
        
        # Windows / macOS
        self.canvas.bind("<MouseWheel>", self._on_mousewheel_windows)
        
        # Linux (X11)
        self.canvas.bind("<Button-4>", self._on_mousewheel_linux)
        self.canvas.bind("<Button-5>", self._on_mousewheel_linux)

    def _on_mousewheel_windows(self, event):
    # event.delta is typically +/-120
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_mousewheel_linux(self, event):
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")  # scroll up
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")   # scroll down


    def _apply_theme(self):
        t = self.themes[self.theme]
        self.canvas.configure(bg=t["canvas_bg"])
        self._redraw_everything()

    def toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"
        self._apply_theme()

    def _set_window_icon(self):
        try:
            base = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(base, "tuto-icon.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception:
            # non-Windows or icon issues: ignore
            pass

    # ---------------- Info dialog ----------------
    def show_info(self):
        win = tk.Toplevel(self.root)
        win.title(f"{APP_TITLE} – Info")
        try:
            # try to set same icon for info window too
            base = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(base, "tuto-icon.ico")
            if os.path.exists(icon_path):
                win.iconbitmap(icon_path)
        except Exception:
            pass

        win.geometry("520x360")

        txt = tk.Text(win, wrap="word", height=18)
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        info = (
            f"{APP_TITLE}\n\n"
            "A minimal, secure PDF redaction tool.\n\n"
            "Usage:\n"
            "• Open a PDF\n"
            "• Draw black rectangles to mark redactions\n"
            "• Rectangles can be removed via right-click\n"
            "• Or search text / regex and redact matches\n"
            "• Save to permanently remove redacted content\n\n"
            "Notes:\n"
            "• Redaction removes underlying text and images\n"
            "• Content outside rectangles remains searchable/selectable\n\n"
            f"GitHub: {GITHUB_URL}\n\n"
            "Copyright © Mirco Lang\n"
            "License: AGPLv3 (see LICENSE.txt in the project distribution)\n"
            "Powered by PyMuPDF\n"
        )

        txt.insert("1.0", info)
        txt.configure(state="disabled")

        btns = tk.Frame(win)
        btns.pack(fill=tk.X, padx=10, pady=(0, 10))

        def copy_url():
            self.root.clipboard_clear()
            self.root.clipboard_append(GITHUB_URL)
            messagebox.showinfo("Copied", "GitHub URL copied to clipboard.")

        tk.Button(btns, text="Copy GitHub URL", command=copy_url).pack(side=tk.LEFT)
        tk.Button(btns, text="Close", command=win.destroy).pack(side=tk.RIGHT)

    # ---------------- Basics ----------------
    def _ensure_loaded(self):
        if not self.doc:
            messagebox.showinfo(APP_TITLE, "Open a PDF first.")
            return False
        return True

    def on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def on_canvas_configure(self, _event):
        # Debounce: layout can be expensive
        if self._resize_after_id is not None:
            self.root.after_cancel(self._resize_after_id)
        self._resize_after_id = self.root.after(150, self._relayout_only)

    # ---------------- Open / Render / Layout ----------------
    def open_pdf(self):
        path = filedialog.askopenfilename(title="Open PDF", filetypes=[("PDF files", "*.pdf")])
        if not path:
            return

        try:
            self.doc = pymupdf.open(path)
        except Exception as e:
            messagebox.showerror("Open failed", str(e))
            return

        self.pdf_path = path
        self.redactions = {}
        self.current_page = 0
        self._render_all_pages()
        self._relayout_only()
        self._scroll_to_page(0)

    def _render_all_pages(self):
        """Render pixmaps once; layout is done separately."""
        self.page_imgs = []
        self.page_sizes = []
        self.page_scales = []

        for i in range(len(self.doc)):
            page = self.doc[i]
            mat = pymupdf.Matrix(self.zoom, self.zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            tk_img = ImageTk.PhotoImage(img)

            self.page_imgs.append(tk_img)
            self.page_sizes.append((pix.width, pix.height))
            self.page_scales.append(pix.width / float(page.rect.width))

    def _relayout_only(self):
        """Recompute page positions and redraw canvas items without re-rendering pixmaps."""
        if not self.doc or not self.page_imgs:
            return

        self.canvas.delete("all")
        self.page_pos = []

        spacing = 16
        border = 1

        # current canvas width (fallback if not ready)
        canvas_w = max(400, self.canvas.winfo_width())

        x = 0
        y = 0
        row_h = 0
        max_x = 0

        for i, (w, h) in enumerate(self.page_sizes):
            # new row if doesn't fit
            if x > 0 and x + w > canvas_w:
                x = 0
                y += row_h + spacing
                row_h = 0

            self.page_pos.append((x, y))

            # page image
            self.canvas.create_image(x, y, image=self.page_imgs[i], anchor="nw", tags=("pageimg", f"p{i}"))

            # border
            self.canvas.create_rectangle(
                x, y, x + w, y + h,
                outline=self.themes[self.theme]["page_border"],
                width=border,
                tags=("pageborder",)
            )

            x = x + w + spacing
            row_h = max(row_h, h)
            max_x = max(max_x, x)

        total_h = y + row_h + spacing
        self.canvas.config(scrollregion=(0, 0, max_x, total_h))

        self._redraw_all_redactions()
        self._update_page_label()

    def _redraw_everything(self):
        # used on theme change
        if not self.doc:
            return
        self._relayout_only()

    def _update_page_label(self):
        if self.doc:
            self.page_label.config(text=f"Page {self.current_page + 1} / {len(self.doc)}")
        else:
            self.page_label.config(text="No document loaded")

    def _scroll_to_page(self, page_index):
        if not self.doc:
            return
        page_index = max(0, min(page_index, len(self.doc) - 1))
        self.current_page = page_index
        self._update_page_label()

        if not self.page_pos:
            return

        _, y = self.page_pos[page_index]

        sr = self.canvas.cget("scrollregion")
        if not sr:
            return
        x0, y0, x1, y1 = map(float, sr.split())
        total_h = max(1.0, y1 - y0)
        self.canvas.yview_moveto(y / total_h)

    def prev_page(self):
        if self._ensure_loaded():
            self._scroll_to_page(self.current_page - 1)

    def next_page(self):
        if self._ensure_loaded():
            self._scroll_to_page(self.current_page + 1)

    # ---------------- Redaction overlay rendering ----------------
    def _redraw_all_redactions(self):
        self.canvas.delete("redaction")

        if not self.page_pos:
            return

        for page_index, rects in self.redactions.items():
            if not rects:
                continue

            px, py = self.page_pos[page_index]
            scale = self.page_scales[page_index]

            for idx, r in enumerate(rects):
                x0 = px + (r.x0 * scale)
                y0 = py + (r.y0 * scale)
                x1 = px + (r.x1 * scale)
                y1 = py + (r.y1 * scale)

                self.canvas.create_rectangle(
                    x0, y0, x1, y1,
                    outline="red", width=2,
                    fill="black", stipple="gray50",
                    tags=("redaction", f"p{page_index}", f"idx{idx}")
                )

    def _page_at_canvas_xy(self, x, y):
        """Find which page (if any) the point is inside."""
        for i, (px, py) in enumerate(self.page_pos):
            w, h = self.page_sizes[i]
            if px <= x <= px + w and py <= y <= py + h:
                return i
        return None

    def _canvas_rect_to_pdf_rect(self, page_index, x0, y0, x1, y1):
        """Convert a drawn rect in canvas coords to PDF coords for the given page."""
        scale = self.page_scales[page_index]
        page = self.doc[page_index]
        page_rect = page.rect

        px, py = self.page_pos[page_index]

        # canvas -> page-local px
        lx0 = min(x0, x1) - px
        lx1 = max(x0, x1) - px
        ly0 = min(y0, y1) - py
        ly1 = max(y0, y1) - py

        # clamp to page bounds in px
        w_px, h_px = self.page_sizes[page_index]
        lx0 = max(0, min(lx0, w_px))
        lx1 = max(0, min(lx1, w_px))
        ly0 = max(0, min(ly0, h_px))
        ly1 = max(0, min(ly1, h_px))

        if abs(lx1 - lx0) < 3 or abs(ly1 - ly0) < 3:
            return None

        # page-local px -> PDF units
        rx0 = lx0 / scale
        rx1 = lx1 / scale
        ry0 = ly0 / scale
        ry1 = ly1 / scale

        # clamp to PDF page
        rx0 = max(0, min(rx0, page_rect.width))
        rx1 = max(0, min(rx1, page_rect.width))
        ry0 = max(0, min(ry0, page_rect.height))
        ry1 = max(0, min(ry1, page_rect.height))

        return pymupdf.Rect(rx0, ry0, rx1, ry1)

    # ---------------- Rectangle actions ----------------
    def undo_last(self):
        if not self._ensure_loaded():
            return
        rects = self.redactions.get(self.current_page, [])
        if rects:
            rects.pop()
            self.redactions[self.current_page] = rects
            self._redraw_all_redactions()

    def clear_page(self):
        if not self._ensure_loaded():
            return
        self.redactions[self.current_page] = []
        self._redraw_all_redactions()

    def on_right_click_delete(self, event):
        """Right-click a rectangle to delete it."""
        if not self._ensure_loaded():
            return

        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)

        item = self.canvas.find_closest(x, y)
        if not item:
            return
        tags = self.canvas.gettags(item[0])
        if "redaction" not in tags:
            return

        page_tag = next((t for t in tags if t.startswith("p") and t[1:].isdigit()), None)
        idx_tag = next((t for t in tags if t.startswith("idx") and t[3:].isdigit()), None)
        if not page_tag or not idx_tag:
            return

        p = int(page_tag[1:])
        idx = int(idx_tag[3:])

        rects = self.redactions.get(p, [])
        if 0 <= idx < len(rects):
            rects.pop(idx)
            self.redactions[p] = rects
            self._redraw_all_redactions()

    # ---------------- Drawing ----------------
    def on_mouse_down(self, event):
        if not self._ensure_loaded():
            return
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)

        p = self._page_at_canvas_xy(x, y)
        if p is None:
            return

        self.current_page = p
        self._update_page_label()

        self.drag_start = (x, y)
        self.drag_page = p

        self.current_rect_item = self.canvas.create_rectangle(
            x, y, x, y,
            outline="red", width=2,
            fill="black", stipple="gray50",
            tags=("redaction",)
        )

    def on_mouse_drag(self, event):
        if not self.drag_start or not self.current_rect_item:
            return
        x0, y0 = self.drag_start
        x1 = self.canvas.canvasx(event.x)
        y1 = self.canvas.canvasy(event.y)
        self.canvas.coords(self.current_rect_item, x0, y0, x1, y1)

    def on_mouse_up(self, event):
        if not self.drag_start or not self.current_rect_item or self.drag_page is None:
            return

        x0, y0 = self.drag_start
        x1 = self.canvas.canvasx(event.x)
        y1 = self.canvas.canvasy(event.y)

        r = self._canvas_rect_to_pdf_rect(self.drag_page, x0, y0, x1, y1)

        self.canvas.delete(self.current_rect_item)
        self.drag_start = None
        self.drag_page = None
        self.current_rect_item = None

        if r is None:
            return

        self.redactions.setdefault(self.current_page, []).append(r)
        self._redraw_all_redactions()

    # ---------------- Search / Regex redaction (tight boxes) ----------------
    def _tight_rect(self, page_index, r, pad_y_px=0):
        """
        pad_y_px > 0  -> expand vertically
        pad_y_px < 0  -> shrink vertically
        """
        if pad_y_px == 0:
            return r
        
        scale = self.page_scales[page_index]
        dy = abs(pad_y_px) / scale
        
        rr = pymupdf.Rect(r)
        
        if pad_y_px > 0:
            rr.y0 -= dy
            rr.y1 += dy
        else:
            # shrink, but don't invert
            rr.y0 += dy
            rr.y1 -= dy
            if rr.y1 <= rr.y0:
                return r  # fallback
        
        return rr


    def _line_matches_to_rects(self, words, line_text, matches):
        spans = []
        pos = 0
        for w in words:
            token = w[4]
            start = pos
            end = pos + len(token)
            spans.append((start, end, w))
            pos = end + 1  # one space in reconstructed line_text

        rects = []
        for m0, m1 in matches:
            covered = []
            for s0, s1, w in spans:
                if not (m1 <= s0 or m0 >= s1):  # overlap
                    covered.append(w)

            if covered:
                r = pymupdf.Rect(covered[0][0:4])
                for w in covered[1:]:
                    r |= pymupdf.Rect(w[0:4])
                rects.append(r)

        return rects

    def redact_matches(self):
        if not self._ensure_loaded():
            return
        q = self.search_var.get().strip()
        if not q:
            messagebox.showinfo("Redact matches", "Enter a search string / regex first.")
            return

        do_regex = self.regex_var.get()
        added = 0

        try:
            pattern = re.compile(q) if do_regex else None

            for i in range(len(self.doc)):
                page = self.doc[i]
                words = page.get_text("words")  # (x0,y0,x1,y1,"word",block,line,word_no)

                lines = {}
                for w in words:
                    key = (w[5], w[6])  # (block, line)
                    lines.setdefault(key, []).append(w)

                for lw in lines.values():
                    lw.sort(key=lambda t: t[7])
                    line_text = " ".join(w[4] for w in lw)

                    if do_regex:
                        ms = [(m.start(), m.end()) for m in pattern.finditer(line_text)]
                    else:
                        ms = []
                        start = 0
                        while True:
                            j = line_text.find(q, start)
                            if j < 0:
                                break
                            ms.append((j, j + len(q)))
                            start = j + max(1, len(q))

                    if not ms:
                        continue

                    rects = self._line_matches_to_rects(lw, line_text, ms)

                    # keep tight; if needed change to pad_y_px=+1
                    for r in rects:
                        r2 = self._tight_rect(i, r, pad_y_px=-2)
                        self.redactions.setdefault(i, []).append(r2)
                        added += 1

        except re.error as e:
            messagebox.showerror("Regex error", f"Invalid regex:\n{e}")
            return
        except Exception as e:
            messagebox.showerror("Search error", str(e))
            return

        if added == 0:
            messagebox.showinfo("Redact matches", "No matches found.")
        else:
            self._redraw_all_redactions()
            messagebox.showinfo("Redact matches", f"Added {added} redaction rectangle(s).")

    # ---------------- Save ----------------
    def save_as(self):
        if not self._ensure_loaded():
            return

        if not any(self.redactions.get(i) for i in range(len(self.doc))):
            if not messagebox.askyesno("Save", "No rectangles drawn. Save anyway?"):
                return

        out = filedialog.asksaveasfilename(
            title="Save redacted PDF as…",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")]
        )
        if not out:
            return

        try:
            doc = pymupdf.open(self.pdf_path)

            for i in range(len(doc)):
                rects = self.redactions.get(i, [])
                if not rects:
                    continue
                page = doc[i]
                for r in rects:
                    page.add_redact_annot(r, fill=(0, 0, 0))
                page.apply_redactions()

            doc.save(out, garbage=4, deflate=True)
            doc.close()

            messagebox.showinfo("Saved", f"Redacted PDF saved:\n{out}")
        except Exception as e:
            messagebox.showerror("Save failed", str(e))


def main():
    root = tk.Tk()
    root.geometry("1100x800")
    PDFRedactorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

