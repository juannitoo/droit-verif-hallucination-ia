"""The window, in three tabs: "check" (pick a document, read the report), "keys" (enter your
access keys once) and "scope" (what is checked, and what is not). On first launch, with no
key saved, it opens on the keys tab.

customtkinter, on top of the tkinter that ships with Python, with the voice assistant's look
(theme.py, assets/theme.json). The check runs in a separate thread so the window does not
freeze during network calls.
"""
import queue
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from . import annotate, keys, output, reader, report, report_pdf, theme
from .countries import COUNTRIES, DEFAULT
from .engine import check_document, valid_date
from .locales import t

# Before any widget: customtkinter widgets read the theme when they are built.
theme.apply()
C = theme.COLORS
XS, SM, MD, LG = (theme.SPACING[k] for k in ("xs", "sm", "md", "lg"))
WRAP = 820          # px: help texts wrap at the width of the tab


class Window:
    def __init__(self, root):
        self.root = root
        self.country = COUNTRIES[DEFAULT]
        self.document = None    # le fichier choisi
        # Le fichier dont `last` est le rapport, figé au lancement de la vérification : un
        # autre peut être choisi ensuite, les enregistrements visent toujours celui-ci (audit
        # du 01/10/2026).
        self.checked = None
        self.last = None
        self.queue = queue.Queue()
        self.f_small = theme.font("small")
        self.f_body = theme.font("body")
        self.f_bold = theme.font("body", "bold")
        self.f_title = theme.font("title", "bold")
        self.f_mono = ctk.CTkFont(family="Consolas", size=theme.FONT_SIZES["body"] - 1)
        root.title(t.TITLE)
        self._set_icon()
        root.geometry("960x700")
        root.minsize(640, 480)
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)

        self.tabs = ctk.CTkTabview(root)
        self.tabs.grid(row=0, column=0, padx=SM, pady=SM, sticky="nsew")
        for name in (t.TAB_CHECK, t.TAB_KEYS, t.TAB_SCOPE):
            self.tabs.add(name)
        self.tabs._segmented_button.configure(font=self.f_title)
        # CTkTabview has no option for the room around a tab's name: it goes on the label.
        for button in self.tabs._segmented_button._buttons_dict.values():
            button._text_label.configure(
                padx=button._apply_widget_scaling(theme.PADDINGS["onglets_menu"]))
        self.check_tab = self.tabs.tab(t.TAB_CHECK)
        self.keys_tab = self.tabs.tab(t.TAB_KEYS)
        self.scope_tab = self.tabs.tab(t.TAB_SCOPE)

        self._build_check_tab()
        self._build_keys_tab()
        self._build_scope_tab()
        self.show_key_status()
        if not self._all_keys_present():
            self.tabs.set(t.TAB_KEYS)

    def _set_icon(self):
        """The blue scales (assets/make_icon.py), instead of customtkinter's own square. A
        .ico on Windows, sharp at every size; a PNG elsewhere."""
        try:
            if sys.platform == "win32":
                self.root.iconbitmap(str(theme.ASSETS / "icon.ico"))
                # Tk takes the 16-px image and Windows enlarges it: blurred at 200 %.
                # Once the window exists, hand Windows the sizes it asks for on this screen.
                self.root.after(300, self._win_icon_exact)
            else:
                self._icon = tk.PhotoImage(master=self.root, file=str(theme.ASSETS / "icon.png"))
                self.root.iconphoto(True, self._icon)
        except tk.TclError:
            pass            # no icon is better than no window

    def _win_icon_exact(self):
        import ctypes
        user32 = ctypes.windll.user32
        user32.LoadImageW.restype = ctypes.c_void_p
        user32.GetParent.restype = ctypes.c_void_p
        user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p,
                                        ctypes.c_void_p]
        try:
            hwnd = user32.GetParent(self.root.winfo_id())
            dpi = user32.GetDpiForWindow(ctypes.c_void_p(hwnd)) or 96
            path = str(theme.ASSETS / "icon.ico")
            # WM_SETICON, ICON_SMALL (title bar) then ICON_BIG (taskbar, Alt+Tab)
            for kind, metric in ((0, 49), (1, 11)):     # SM_CXSMICON, SM_CXICON
                size = user32.GetSystemMetricsForDpi(metric, dpi)
                handle = user32.LoadImageW(None, path, 1, size, size, 0x10)  # LR_LOADFROMFILE
                if handle:
                    user32.SendMessageW(ctypes.c_void_p(hwnd), 0x80, ctypes.c_void_p(kind),
                                        ctypes.c_void_p(handle))
        except (AttributeError, OSError):
            pass            # Windows older than 10: Tk's icon stays

    # Small helpers, in the voice assistant's vocabulary

    def _hint(self, parent, text, **kw):
        """Grey help text under a field."""
        return ctk.CTkLabel(parent, text=text, font=self.f_small, text_color=C["text_muted"],
                            wraplength=WRAP, justify="left", anchor="w", **kw)

    def _neutral(self, parent, text="", icon=None, **kw):
        """Secondary button, grey: the accent colour is kept for the main actions."""
        kw.setdefault("fg_color", C["neutral"])
        kw.setdefault("hover_color", C["neutral_hover"])
        kw.setdefault("height", 32)
        if icon:
            kw.update(image=theme.icon(self.root, icon), compound="left")
        return ctk.CTkButton(parent, text=text, font=self.f_body, **kw)

    def _link(self, parent, text, command):
        label = ctk.CTkLabel(parent, text=text, font=theme.font("body", underline=True),
                             text_color=C["accent_text"], cursor="hand2")
        label.bind("<Button-1>", lambda e: command())
        return label

    def _separator(self, parent, row):
        # A plain tk Frame: a 1-px CTkFrame draws nothing (its canvas needs room to round).
        tk.Frame(parent, height=1, bg=C["border"]).grid(
            row=row, column=0, columnspan=4, sticky="ew", padx=SM, pady=(LG, 0))

    # Tab "check"

    def _build_check_tab(self):
        tab = self.check_tab
        tab.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(tab, text=t.DOCUMENT, font=self.f_bold).grid(
            row=0, column=0, sticky="w", padx=(SM, 0), pady=(SM, 0))
        self.doc_label = ctk.CTkLabel(tab, text=t.NO_DOCUMENT, text_color=C["text_muted"],
                                      anchor="w")
        self.doc_label.grid(row=0, column=1, sticky="ew", padx=SM, pady=(SM, 0))
        self.b_choose = self._neutral(tab, t.CHOOSE, icon="folder-open", command=self.choose)
        self.b_choose.grid(row=0, column=2, padx=(0, SM), pady=(SM, 0))

        ctk.CTkLabel(tab, text=t.REFERENCE_DATE, font=self.f_bold).grid(
            row=1, column=0, sticky="w", padx=(SM, 0), pady=(MD, 0))
        self.reference = ctk.CTkEntry(tab, width=130, placeholder_text="AAAA-MM-JJ")
        self.reference.grid(row=1, column=1, sticky="w", padx=SM, pady=(MD, 0))
        self._hint(tab, t.REFERENCE_HINT).grid(row=2, column=1, columnspan=2, sticky="w",
                                               padx=SM)
        ctk.CTkLabel(tab, text=t.IDCC, font=self.f_bold).grid(
            row=3, column=0, sticky="w", padx=(SM, 0), pady=(SM, 0))
        self.idcc = ctk.CTkEntry(tab, width=130)
        self.idcc.grid(row=3, column=1, sticky="w", padx=SM, pady=(SM, 0))
        self._hint(tab, t.IDCC_HINT).grid(row=4, column=1, columnspan=2, sticky="w", padx=SM)

        # The yellow banner of the voice assistant, clickable: it leads to the keys tab.
        self.key_warning = ctk.CTkFrame(tab, fg_color=C["warning_bg"])
        self.key_warning.grid(row=5, column=0, columnspan=3, sticky="ew", padx=SM,
                              pady=(MD, 0))
        banner = ctk.CTkLabel(self.key_warning, text=t.KEYS_MISSING_WARNING,
                              text_color=C["warning_text"], wraplength=WRAP, justify="left",
                              anchor="w", cursor="hand2")
        banner.pack(fill="x", padx=MD, pady=SM)
        banner.bind("<Button-1>", lambda e: self.tabs.set(t.TAB_KEYS))

        self.button = ctk.CTkButton(tab, text=t.CHECK, font=self.f_bold, height=36,
                                    width=200, command=self.check)
        self._ready(False)
        self.button.grid(row=6, column=0, columnspan=3, pady=MD)

        # Sans retour à la ligne automatique : il casserait le tableau du rapport.
        self.output = ctk.CTkTextbox(tab, wrap="none", font=self.f_mono, state="disabled")
        self.output.grid(row=7, column=0, columnspan=3, sticky="nsew", padx=SM)
        tab.grid_rowconfigure(7, weight=1)

        bottom = ctk.CTkFrame(tab, fg_color="transparent")
        bottom.grid(row=8, column=0, columnspan=3, sticky="ew", padx=SM, pady=(SM, 0))
        self.b_txt = self._neutral(bottom, t.SAVE_TXT, state="disabled",
                                   command=lambda: self.save("txt"))
        self.b_report_pdf = self._neutral(bottom, t.SAVE_REPORT_PDF, state="disabled",
                                          command=lambda: self.save("pdf"))
        self.b_json = self._neutral(bottom, t.SAVE_JSON, state="disabled",
                                    command=lambda: self.save("json"))
        # Le PDF annoté : le document lui-même, surligné. Pour un PDF seulement.
        self.b_pdf = self._neutral(bottom, t.SAVE_PDF, state="disabled",
                                   command=self.save_pdf)
        ctk.CTkLabel(bottom, text=t.SAVE, font=self.f_bold).pack(side="left", padx=(0, SM))
        self.b_txt.pack(side="left", padx=(0, SM))
        self.b_report_pdf.pack(side="left", padx=(0, SM))
        self.b_json.pack(side="left", padx=(0, SM))
        self.b_pdf.pack(side="left")
        # Checked by default: a saved report travels, often to an online AI.
        self.no_excerpts = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(tab, text=t.NO_EXCERPTS, variable=self.no_excerpts,
                        font=self.f_body).grid(row=9, column=0, columnspan=3, sticky="w",
                                               padx=SM, pady=(SM, 0))
        self._hint(tab, t.NO_EXCERPTS_HINT).grid(row=10, column=0, columnspan=3, sticky="w",
                                                 padx=SM, pady=(XS, SM))

    # Tab "keys"

    def _build_keys_tab(self):
        tab = self.keys_tab
        tab.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(tab, text=t.KEYS_EXPLANATION, wraplength=WRAP, justify="left",
                     anchor="w").grid(row=0, column=0, columnspan=4, sticky="w", padx=SM,
                                      pady=(SM, MD))

        self.fields = {}
        row = 1
        for name, label in self.country.KEYS.items():
            ctk.CTkLabel(tab, text=label, font=self.f_bold).grid(
                row=row, column=0, sticky="w", padx=(SM, 0), pady=(SM, 0))
            field = ctk.CTkEntry(tab, show="●")
            field.grid(row=row, column=1, sticky="ew", padx=SM, pady=(SM, 0))
            buttons = ctk.CTkFrame(tab, fg_color="transparent")
            buttons.grid(row=row, column=2, sticky="w", padx=(0, SM), pady=(SM, 0))
            self._reveal(buttons, field).pack(side="left", padx=(0, XS))
            ctk.CTkButton(buttons, text=t.KEY_SAVE, font=self.f_body, height=32,
                          command=lambda n=name: self.save_key(n)).pack(side="left",
                                                                        padx=(0, XS))
            self._neutral(buttons, icon="trash", width=36, hover_color=C["danger"],
                          command=lambda n=name: self.delete_key(n)).pack(side="left")
            status = ctk.CTkLabel(tab, text="", font=self.f_small, anchor="w")
            status.grid(row=row + 1, column=1, sticky="w", padx=SM)
            self.fields[name] = (field, status)
            row += 2

        self._link(tab, t.KEY_HELP, lambda: webbrowser.open(self.country.KEY_HELP_URL)).grid(
            row=row, column=1, sticky="w", padx=SM, pady=(MD, 0))
        row += 1

        # Optional settings (a local database's address): not secret, shown in clear.
        self.settings = {}
        for name, label in getattr(self.country, "SETTINGS", {}).items():
            self._separator(tab, row)
            ctk.CTkLabel(tab, text=label, font=self.f_bold, text_color=C["accent_text"],
                         wraplength=260, justify="left").grid(
                row=row + 1, column=0, sticky="w", padx=(SM, 0), pady=(MD, 0))
            field = ctk.CTkEntry(tab, placeholder_text="https://…")
            field.insert(0, keys.get(name) or "")
            field.grid(row=row + 1, column=1, sticky="ew", padx=SM, pady=(MD, 0))
            buttons = ctk.CTkFrame(tab, fg_color="transparent")
            buttons.grid(row=row + 1, column=2, sticky="w", padx=(0, SM), pady=(MD, 0))
            ctk.CTkButton(buttons, text=t.SETTING_SAVE, font=self.f_body, height=32,
                          command=lambda n=name: self.save_setting(n)).pack(side="left",
                                                                            padx=(0, XS))
            self._neutral(buttons, icon="trash", width=36, hover_color=C["danger"],
                          command=lambda n=name: self.delete_setting(n)).pack(side="left")
            status = ctk.CTkLabel(tab, text="", font=self.f_small, anchor="w",
                                  wraplength=WRAP - 260, justify="left")
            status.grid(row=row + 2, column=1, columnspan=2, sticky="w", padx=SM)
            self._hint(tab, self.country.SETTINGS_HELP.get(name, "")).grid(
                row=row + 3, column=0, columnspan=4, sticky="w", padx=SM, pady=(SM, 0))
            self.settings[name] = (field, status)
            row += 4

    def _ready(self, on):
        """The Vérifier button: blue with white text when it can be clicked, all grey when
        it cannot (customtkinter only greys the text, which looked like a bug on blue)."""
        self.button.configure(state="normal" if on else "disabled",
                              fg_color=C["accent"] if on else C["neutral"])

    def _highlight(self, button, on):
        """Rapport PDF et PDF annoté, le gros du programme : en bleu dès qu'ils servent,
        comme Vérifier. Gris, et inactifs, sinon."""
        button.configure(state="normal" if on else "disabled",
                         fg_color=C["accent"] if on else C["neutral"],
                         hover_color=C["accent_hover"] if on else C["neutral_hover"],
                         text_color=C["text_on_accent"] if on else C["text"])

    def _reveal(self, parent, entry):
        """The eye button of a secret field: shows or hides what was typed."""
        shown = [False]

        def toggle():
            shown[0] = not shown[0]
            entry.configure(show="" if shown[0] else "●")
            button.configure(image=theme.icon(self.root, "eye-off" if shown[0] else "eye"))
        button = self._neutral(parent, icon="eye", width=36, command=toggle)
        return button

    # Tab "scope": generated from the country's own lists, so it cannot promise more
    # than the program does.

    def _build_scope_tab(self):
        box = ctk.CTkTextbox(self.scope_tab, wrap="word", font=self.f_body)
        box.pack(fill="both", expand=True, padx=SM, pady=SM)
        # CTkTextbox refuses a font on a tag (it could not rescale it): the tag goes on the
        # tk Text inside.
        box._textbox.tag_configure("heading", font=self.f_title, foreground=C["accent_text"],
                                   spacing1=MD, spacing3=XS)
        # A long line wraps under its own text, not under the bullet.
        box._textbox.tag_configure("item", lmargin1=SM, spacing3=XS,
                                   lmargin2=SM + self.f_body.measure("•  "))
        for heading, lines in self.country.scope():
            box.insert("end", heading + "\n", "heading")
            for line in lines:
                box.insert("end", f"•  {line}\n", "item")
        box.configure(state="disabled")

    def _all_keys_present(self):
        return all(keys.get(name) for name in self.country.KEYS)

    def show_key_status(self):
        for name, (field, status) in self.fields.items():
            present = keys.get(name)
            status.configure(text=t.KEY_PRESENT if present else t.KEY_MISSING,
                             text_color=C["success_text"] if present else C["text_muted"])
        if self._all_keys_present():
            self.key_warning.grid_remove()
        else:
            self.key_warning.grid()

    def save_key(self, name):
        field, status = self.fields[name]
        value = field.get().strip()
        if not value:
            return
        if not keys.looks_like_key(value):
            status.configure(text=t.KEY_NOT_A_KEY, text_color=C["danger_text"])
            return
        field.delete(0, "end")
        if keys.save(name, value):
            self.show_key_status()
        else:
            status.configure(text=t.KEY_NO_KEYRING, text_color=C["danger_text"])

    def delete_key(self, name):
        keys.delete(name)
        self.show_key_status()

    def save_setting(self, name):
        field, status = self.settings[name]
        value = field.get().strip()
        check = getattr(self.country, "SETTINGS_CHECK", {}).get(name)
        problem = value and (check(value) if check else
                             None if value.startswith("https://") else t.SETTING_BAD_URL)
        if problem:
            status.configure(text=problem, text_color=C["danger_text"])
            return
        if not value:
            return self.delete_setting(name)
        saved = keys.save(name, value)
        status.configure(text=t.SETTING_SAVED if saved else t.SETTING_NO_KEYRING,
                         text_color=C["success_text"] if saved else C["danger_text"])

    def delete_setting(self, name):
        field, status = self.settings[name]
        keys.delete(name)
        field.delete(0, "end")
        status.configure(text=t.SETTING_EMPTY, text_color=C["text_muted"])

    # Checking

    def choose(self):
        path = filedialog.askopenfilename(filetypes=[
            (t.FORMATS, "*.pdf *.docx *.odt *.txt *.md")])
        if path:
            self.document = path
            self.doc_label.configure(text=path, text_color=C["text"])
            self._ready(True)

    def write(self, text, clear=False):
        self.output.configure(state="normal")
        if clear:
            self.output.delete("1.0", "end")
        self.output.insert("end", text)
        self.output.see("end")
        self.output.configure(state="disabled")

    def check(self):
        reference = self.reference.get().strip() or None
        if reference and not valid_date(reference):
            self.write(t.REFERENCE_INVALID + "\n", clear=True)
            return
        idcc = self.idcc.get().strip() or None
        if idcc and not idcc.isdigit():
            self.write(t.IDCC_INVALID + "\n", clear=True)
            return
        self._ready(False)
        self.b_choose.configure(state="disabled")
        document = self.document
        for b in (self.b_txt, self.b_json):
            b.configure(state="disabled")
        for b in (self.b_report_pdf, self.b_pdf):
            self._highlight(b, False)
        self.write(t.IN_PROGRESS + "\n\n", clear=True)

        def work():
            try:
                r = check_document(document, log=lambda s: self.queue.put(("line", s)),
                                   options={"reference_date": reference, "idcc": idcc})
                self.queue.put(("done", (document, r)))
            except reader.Unreadable as e:
                self.queue.put(("error", str(e)))
            except Exception as e:
                self.queue.put(("error", f"{type(e).__name__} : {e}"))

        threading.Thread(target=work, daemon=True).start()
        self.root.after(100, self.poll)

    def poll(self):
        try:
            while True:
                kind, content = self.queue.get_nowait()
                if kind == "line":
                    self.write(content + "\n")
                elif kind == "pdf":
                    self.write("\n" + content + "\n")
                    self._highlight(self.b_pdf, True)
                    return
                elif kind == "error":
                    self.write("\n" + content + "\n")
                    self._ready(True)
                    self.b_choose.configure(state="normal")
                    return
                else:
                    self.checked, self.last = content
                    self.write(report.to_text(self.last), clear=True)
                    self.output.see("1.0")         # le tableau d'abord
                    self._ready(True)
                    self.b_choose.configure(state="normal")
                    for b in (self.b_txt, self.b_json):
                        b.configure(state="normal")
                    self._highlight(self.b_report_pdf, True)
                    self._highlight(self.b_pdf,
                                    Path(self.checked).suffix.lower() == ".pdf")
                    return
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def save(self, kind):
        without = self.no_excerpts.get()
        initial = (report_pdf.output_name(self.checked, without) if kind == "pdf"
                   else f"{t.REPORT_FILE}.{kind}")
        path = filedialog.asksaveasfilename(defaultextension=f".{kind}", initialfile=initial)
        if not path:
            return
        r = report.without_excerpts(self.last) if without else self.last
        try:
            if kind == "pdf":
                report_pdf.write(r, path, document=self.checked)
            else:
                output.write(path, report.to_json(r) if kind == "json" else report.to_text(r),
                             document=self.checked)
        except output.OverDocument as e:
            self.write("\n" + str(e) + "\n")

    def save_pdf(self):
        source = Path(self.checked)
        default = annotate.output_name(source)
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf", initialdir=str(default.parent),
            initialfile=default.name, filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        if output.same_file(path, source):
            self.write("\n" + t.PDF_NOT_OVER_ORIGINAL + "\n")
            return
        self._highlight(self.b_pdf, False)
        self.write("\n" + t.PDF_IN_PROGRESS + "\n")
        report_ = self.last

        def work():
            try:
                placed, missed = annotate.annotate(source, path, report_)
                done = t.PDF_SAVED.format(path=path, placed=placed)
                self.queue.put(("pdf", done + (t.PDF_MISSED.format(n=missed) if missed else "")))
            except Exception as e:
                said = isinstance(e, (annotate.TooHeavy, output.OverDocument))
                why = str(e) if said else f"{type(e).__name__} : {e}"
                self.queue.put(("pdf", t.PDF_FAILED_ANNOTATE.format(error=why)))

        threading.Thread(target=work, daemon=True).start()
        self.root.after(100, self.poll)


def run():
    root = ctk.CTk()
    Window(root)
    root.mainloop()
    return 0
